from typing import Any

import pandas as pd
import pandera.pandas as pa
from pandera.typing import Series


class ContractInfoSchema(pa.DataFrameModel):
    """Schema for 1_계약정보 (contract info) input CSV."""

    계약ID: Series[Any] = pa.Field(nullable=False, unique=True)
    상품구분: Series[str] = pa.Field(isin=["IRS", "CRS"])
    자국통화: Series[str] = pa.Field(nullable=False)
    외국통화: Series[str] = pa.Field(nullable=True)
    자국통화명목원금: Series[float] = pa.Field(gt=0)
    외국통화명목원금: Series[float] = pa.Field(nullable=True, gt=0)
    시작일: Series[pd.Timestamp] = pa.Field(nullable=False)
    만기일: Series[pd.Timestamp] = pa.Field(nullable=False)
    연간결제횟수: Series[int] = pa.Field(gt=0)
    자국통화고정금리: Series[float] = pa.Field(gt=0, lt=1)
    외국통화고정금리: Series[float] = pa.Field(nullable=True, gt=0, lt=1)
    원금교환여부: Series[bool] = pa.Field(nullable=False)

    class Config:
        coerce = True

    @pa.dataframe_check
    def crs_completeness(cls, df: pd.DataFrame) -> Series[bool]:
        is_crs = df["상품구분"] == "CRS"
        complete = (
            df["외국통화"].notna()
            & df["외국통화명목원금"].notna()
            & df["외국통화고정금리"].notna()
        )
        return ~is_crs | complete

    @pa.dataframe_check
    def irs_nullness(cls, df: pd.DataFrame) -> Series[bool]:
        is_irs = df["상품구분"] == "IRS"
        all_null = (
            df["외국통화"].isna()
            & df["외국통화명목원금"].isna()
            & df["외국통화고정금리"].isna()
        )
        return ~is_irs | all_null

    @pa.dataframe_check
    def maturity_after_start(cls, df: pd.DataFrame) -> Series[bool]:
        return df["만기일"] > df["시작일"]

    @pa.dataframe_check
    def principal_exchange_matches_product(cls, df: pd.DataFrame) -> Series[bool]:
        return df["원금교환여부"] == (df["상품구분"] == "CRS")


class MarketRateSchema(pa.DataFrameModel):
    """Schema for 2_시장금리입력 (market rate curve) input CSV."""

    통화: Series[str] = pa.Field(nullable=False)
    만기_년: Series[float] = pa.Field(gt=0)
    현재금리: Series[float] = pa.Field(gt=0, lt=1)

    class Config:
        coerce = True


class CashflowMappingSchema(pa.DataFrameModel):
    """Schema for 3_아웃풋1_현금흐름매핑 (cashflow mapping) output CSV."""

    계약ID: Series[Any] = pa.Field(nullable=False)
    상품구분: Series[str] = pa.Field(isin=["IRS", "CRS"])
    다리구분: Series[str] = pa.Field(isin=["고정", "변동", "자국고정", "외국고정"])
    통화: Series[str] = pa.Field(nullable=False)
    회차: Series[int] = pa.Field(gt=0)
    시작일: Series[pd.Timestamp] = pa.Field(nullable=False)
    종료일: Series[pd.Timestamp] = pa.Field(nullable=False)
    연환산기간: Series[float] = pa.Field(gt=0)
    명목원금: Series[float] = pa.Field(gt=0)
    이자현금흐름: Series[float] = pa.Field(nullable=True)
    원금현금흐름: Series[float] = pa.Field(nullable=False)

    class Config:
        coerce = True

    @pa.dataframe_check
    def leg_matches_product(cls, df: pd.DataFrame) -> Series[bool]:
        irs_ok = (df["상품구분"] == "IRS") & df["다리구분"].isin(["고정", "변동"])
        crs_ok = (df["상품구분"] == "CRS") & df["다리구분"].isin(["자국고정", "외국고정"])
        return irs_ok | crs_ok

    @pa.dataframe_check
    def interest_cashflow_nullness(cls, df: pd.DataFrame) -> Series[bool]:
        is_floating = df["다리구분"] == "변동"
        return is_floating == df["이자현금흐름"].isna()

    @pa.dataframe_check
    def end_after_start(cls, df: pd.DataFrame) -> Series[bool]:
        return df["종료일"] > df["시작일"]


class DiscountRateSchema(pa.DataFrameModel):
    """Schema for 4_아웃풋2_회차별할인율 (per-installment discount rate) output CSV."""

    계약ID: Series[Any] = pa.Field(nullable=False)
    회차: Series[int] = pa.Field(gt=0)
    결제일: Series[pd.Timestamp] = pa.Field(nullable=False)
    통화: Series[str] = pa.Field(nullable=False)
    # 범위 제약 없음: 할인 단계는 필터/클램프를 하지 않으므로(spec §5.2) 과거 회차의
    # 음수 기간, 선형외삽으로 인한 범위 밖 금리, 1 초과 할인계수도 정상 출력값이다.
    평가일로부터기간_년: Series[float] = pa.Field(nullable=False)
    적용할인율: Series[float] = pa.Field(nullable=False)
    할인계수: Series[float] = pa.Field(gt=0)

    class Config:
        coerce = True
        # CRS는 회차마다 자국/외국 두 통화 행을 가지므로 통화까지 포함해야 유일하다.
        unique = ["계약ID", "통화", "회차"]
