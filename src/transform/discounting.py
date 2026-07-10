import pandas as pd
from datetime import date
from src.transform.cleaning import TransformError
import math
import bisect

COLUMNS = ["계약ID", "회차", "결제일", "통화", "평가일로부터기간_년", "적용할인율", "할인계수"]
SCHEMA_DTYPES = {
    "계약ID": "object",
    "회차": "int64",
    "결제일": "datetime64[ns]",
    "통화": "object",
    "평가일로부터기간_년": "float64",
    "적용할인율": "float64",
    "할인계수": "float64",
}

class TransformDiscountingError(TransformError):
    """행의 통화가 market_rate_df 커브에 아예 없을 때 발생 (구조적 문제, skip 아님)."""
    def __init__(self, message: str, 계약ID, 통화):
        super().__init__(message)
        self.계약ID = 계약ID
        self.통화 = 통화





def compute_discount_rates(cashflow_mapping_df, market_rate_df, evaluation_date):
    curves = _build_curve_cache(market_rate_df)

    # unique (계약ID, 통화, 회차, 결제일); 결제일 == that leg's 종료일 for the 회차.
    # drop_duplicates collapses IRS 고정+변동 (same 통화/schedule) into one row,
    # and keeps CRS's two currency legs as two rows.
    keys = (cashflow_mapping_df[["계약ID", "통화", "회차", "종료일"]]
            .drop_duplicates()
            .rename(columns={"종료일": "결제일"}))

    records = []
    for _, r in keys.iterrows():
        통화 = r["통화"]
        if 통화 not in curves:
            raise TransformDiscountingError(
                message=f"시장금리 커브에 통화가 없습니다: 계약ID={r['계약ID']}, 통화={통화}",
                계약ID=r["계약ID"], 통화=통화,
            )
        # (결제일 − evaluation_date).days / 365 ; note pd.Timestamp vs date normalization
        days = (r["결제일"].date() - evaluation_date).days
        years = days / 365
        tenors, rates = curves[통화]
        rate = _interpolate_rate(tenors, rates, years)
        factor = math.exp(-rate * years)
        records.append({
            "계약ID": r["계약ID"], "회차": r["회차"], "결제일": r["결제일"], "통화": 통화,
            "평가일로부터기간_년": years, "적용할인율": rate, "할인계수": factor,
        })

    df = pd.DataFrame.from_records(records, columns=COLUMNS)
    return df.astype(SCHEMA_DTYPES)


def _interpolate_rate(tenors: list[float], rates: list[float], x: float) -> float:
    n = len(tenors)
    if x < tenors[0]:
        i, j = 0, 1
    elif x > tenors[-1]:
        i, j = n-2, n-1
    else:
        j = bisect.bisect_left(tenors, x)
        if j == 0:
            i, j = 0, 1
        else:
            i = j - 1
    slope = (rates[j] - rates[i]) / (tenors[j] - tenors[i])
    return rates[i] + (x - tenors[i]) * slope



def _build_curve_cache(market_rate_df) -> dict[str, tuple[list[float], list[float]]]:
    cache = {}
    for 통화, g in market_rate_df.groupby("통화"):
        g = g.sort_values("만기_년")
        cache[통화] = (g["만기_년"].tolist(), g["현재금리"].tolist())
    return cache


