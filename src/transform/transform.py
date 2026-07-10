"""Transform 단계 오케스트레이터 (architecture.md §3, §3.1).

실행 순서(확정): 정제(Cleaning) → 파생(Derive) → 필터링(Filtering) → 할인(Discounting).
집계(Aggregation)/조인(Joins)은 현재 스펙상 사용되지 않아 호출하지 않는다 (§3.1.4~5).
"""

import pandas as pd

from src.transform.cleaning import clean_contract_df
from src.transform.derive import build_cashflow_mapping
from src.transform.discounting import compute_discount_rates
from src.transform.filtering import filter_cashflow_mapping
from src.validate.schemas import CashflowMappingSchema, DiscountRateSchema


def run(
    contract_df: pd.DataFrame, market_rate_df: pd.DataFrame, evaluation_date
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """(현금흐름매핑 df, 회차별할인율 df, 필터 제외 레코드 목록)을 반환한다.

    필터 레코드의 로깅은 architecture.md §4에 따라 호출부(pipeline 진입점)의 책임.
    필터링이 현재 no-op이므로 compute_discount_rates는 과거 회차(평가일로부터기간_년 ≤ 0)
    도 그대로 받는다 — 공식(선형보간/외삽 + e^(-r·t))이 클램프 없이 처리한다.
    입력 불변, I/O·로깅 없음.
    """
    cleaned_df = clean_contract_df(contract_df)
    cashflow_mapping_df = build_cashflow_mapping(cleaned_df)
    cashflow_mapping_df, filter_records = filter_cashflow_mapping(
        cashflow_mapping_df, evaluation_date
    )
    discount_rate_df = compute_discount_rates(
        cashflow_mapping_df, market_rate_df, evaluation_date
    )

    # 출력 스키마를 최종 안전장치로 검증 — 위반 시 pandera 예외로 fail-fast.
    CashflowMappingSchema.validate(cashflow_mapping_df)
    DiscountRateSchema.validate(discount_rate_df)

    return cashflow_mapping_df, discount_rate_df, filter_records
