import pandas as pd
from typing import NamedTuple
from dateutil.relativedelta import relativedelta
from src.transform.cleaning import TransformCleaningError

COLUMNS = ["계약ID","상품구분","다리구분","통화","회차","시작일","종료일",
           "연환산기간","명목원금","이자현금흐름","원금현금흐름"]
SCHEMA_DTYPES = {
"계약ID": "object",
"상품구분": "object",
"다리구분": "object",
"통화": "object",
"회차": "int64",
"시작일": "datetime64[ns]",
"종료일": "datetime64[ns]",
"연환산기간": "float64",
"명목원금": "float64",
"이자현금흐름": "float64",
"원금현금흐름": "float64",
}


def build_cashflow_mapping(contract_df: pd.DataFrame) -> pd.DataFrame:
    """정제된 계약 df → CashflowMappingSchema를 만족하는 cashflow_mapping_df.
    계약당 (리그 × 회차) 한 행씩. 입력 불변, I/O·로깅 없음."""
    records = []
    for _, row in contract_df.iterrows():
        legs = _legs_for_contract(row)
        periods = _generate_periods(row["시작일"], row["만기일"], int(row["연간결제횟수"]))
        for leg in legs:
            for i, (seg_start, seg_end) in enumerate(periods):
                yf = _year_fraction(seg_start, seg_end)
                is_final = (i == len(periods) - 1)
                다리구분 = leg.다리구분
                통화 = leg.통화
                명목원금 = leg.명목원금
                원금교환여부 = row["원금교환여부"]
                is_floating = leg.is_floating
                고정금리 = leg.고정금리
                records.append({
                    "계약ID": row["계약ID"],
                    "상품구분": row["상품구분"],
                    "다리구분": 다리구분,
                    "통화": 통화,
                    "회차": i + 1,
                    "시작일": seg_start,
                    "종료일": seg_end,
                    "연환산기간": yf,
                    "명목원금": 명목원금,
                    "이자현금흐름": _interest_cashflow(명목원금,고정금리, yf, is_floating),
                    "원금현금흐름": _principal_cashflow(명목원금, 원금교환여부, is_final)
                })

    df = pd.DataFrame.from_records(records, columns=COLUMNS)
    df = df.astype(SCHEMA_DTYPES)
    return df




# 리그 명세: (다리구분, 통화, 명목원금, 고정금리 or None, is_floating)
class LegSpec(NamedTuple):
    다리구분: str
    통화: str
    명목원금: float
    고정금리: float | None
    is_floating: bool


def _legs_for_contract(row: pd.Series) -> list[LegSpec]:
    상품구분 = row["상품구분"]
    if 상품구분 == "IRS":
        return [
            LegSpec(
                다리구분="고정",
                통화=row["자국통화"],
                명목원금=row["자국통화명목원금"],
                고정금리=row["자국통화고정금리"],
                is_floating=False,
            ),
            LegSpec(
                다리구분="변동",
                통화=row["자국통화"],
                명목원금=row["자국통화명목원금"],
                고정금리=None,
                is_floating=True,
            ),
        ]
    elif 상품구분 == "CRS":
        return [
        LegSpec(
            다리구분="자국고정",
            통화=row["자국통화"],
            명목원금=row["자국통화명목원금"],
            고정금리=row["자국통화고정금리"],
            is_floating=False,
        ),
        LegSpec(
            다리구분="외국고정",
            통화=row["외국통화"],
            명목원금=row["외국통화명목원금"],
            고정금리=row["외국통화고정금리"],
            is_floating=False,
        ),
        ]
    else:
        raise TransformCleaningError(
            message=f"상품구분이 IRS 또는 CRS가 아닙니다: 계약ID={row['계약ID']}, 값={row['상품구분']}",
            계약ID=row["계약ID"],
            column="상품구분",
            value=row["상품구분"],
        )



def _generate_periods(시작일, 만기일, 연간결제횟수) -> list[tuple]: 
    step_months = 12 // 연간결제횟수
    periods = []
    seg_start = 시작일
    n = 1
    while seg_start < 만기일:
        seg_end = 시작일 + relativedelta(months=step_months * n)
        if seg_end >= 만기일:
            seg_end = 만기일
        periods.append((seg_start, seg_end))
        seg_start = seg_end
        n += 1
    return periods

def _year_fraction(start, end) -> float: 
    return (end - start).days / 365


def _interest_cashflow(명목원금, 고정금리, 연환산기간, is_floating) -> float | None: 
    if is_floating:
        return None
    return 명목원금 * 고정금리 * 연환산기간


def _principal_cashflow(명목원금, 원금교환여부, is_final) -> float:
    if 원금교환여부 and is_final:
        return 명목원금
    return 0.0