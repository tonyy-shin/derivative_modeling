
import pandas as pd
from dataclasses import dataclass

# Error handling -----------------------------------------------------------------
class TransformError(Exception):
    """Base class for all transform errors"""

class TransformCleaningError(TransformError):
    """Cleaning 단계에서 계약 값을 깨끗하게 정규화할 수 없을 때 발생.

    예: coerce 이후에도 파싱 불가능한 날짜(NaT), 12를 나누어떨어지지 않는 연간결제횟수.
    architecture.md §3.1.1 상 이는 행 단위 skip이 아니라 구조적 실패 → fail-fast.
    어떤 계약ID/컬럼/값이 원인인지 속성으로 노출해 pipeline이 fail-fast 카테고리로 로깅하게 한다.
    """
    def __init__(self, message: str, 계약ID, column: str, value):
        super().__init__(message)
        self.계약ID = 계약ID
        self.column = column
        self.value = value
    


# Functions ----------------------------------------------------------------------

def clean_contract_df(contract_df: pd.DataFrame) -> pd.DataFrame:
    """계약 df를 방어적으로 재정규화한 새 df를 반환한다 (입력은 변형하지 않음).

    - 시작일/만기일을 tz-naive pd.Timestamp(자정 정규화)로 표준화.
    - 스케줄 전개 전제조건(12 % 연간결제횟수 == 0) 확인.
    정규화 불가능한 값은 TransformCleaningError로 fail-fast.
    """
    df = contract_df.copy()
    for col in {"시작일", "만기일"}:
        df[col] = _normalize_date_column(df, col)
    _check_payment_frequency(df)
    return df

    


def _normalize_date_column(df: pd.DataFrame, column: str) -> pd.Series:
    """한 날짜 컬럼을 pd.Timestamp로 정규화한 Series 반환. 파싱 실패(NaT) 시 fail-fast."""
    normalized = pd.to_datetime(df[column], errors="coerce").dt.normalize()
    bad = normalized.isna()
    if bad.any():
        i = bad.idxmax()
        raise TransformCleaningError(
            message=f"{column} 값을 날짜로 변환할 수 없습니다: 계약ID={df.loc[i, '계약ID']}",
            계약ID=df.loc[i, "계약ID"],
            column=column,
            value=df.loc[i, column],
        )
    return normalized




def _check_payment_frequency(df: pd.DataFrame) -> None:
    """연간결제횟수가 (a) 양의 정수이고 (b) 12의 약수인지 확인. 하나라도 위반하면 fail-fast.
    부수효과 없음(검증만). 모듈로 연산 전에 양의 정수 여부를 먼저 확인해 ZeroDivisionError와
    int() 조용한 절사(예: 4.5→4)를 방지한다."""
    def _is_invalid(n):
        if pd.isna(n) or n <= 0 or float(n) != int(n):
            return True 
        return 12 % int(n) != 0

    bad = df["연간결제횟수"].apply(_is_invalid)
    if bad.any():
        i = bad.idxmax()
        n = df.loc[i, "연간결제횟수"]
        reason = "양의 정수여야 합니다" if (pd.isna(n) or n <= 0 or float(n) != int(n)) \
                 else "12를 나누어떨어져야 합니다"
        raise TransformCleaningError(
            message=f"연간결제횟수가 {reason}: 계약ID={df.loc[i,'계약ID']}, 값={n}",
            계약ID=df.loc[i, "계약ID"], column="연간결제횟수", value=n,
        )