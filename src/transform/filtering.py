"""Transform 필터링 단계 (architecture.md §3.1.3).

현재 이 프로젝트에 확정된 필터링 규칙은 없다. 특히 과거 회차(종료일 ≤ 평가일)도
제외하지 않는다 — 두 출력 모두 공식대로 계산된 값을 그대로 유지한다 (spec §5.2의
"필터/클램프 없음" 원칙과 일관). 이 모듈은 의도적인 no-op이며, 향후 규칙이 확정되면
이 함수 안에만 로직을 추가하면 되도록 인터페이스(반환 레코드 형태 포함)를 고정해 둔다.
"""

import pandas as pd


def filter_cashflow_mapping(
    cashflow_mapping_df: pd.DataFrame, evaluation_date
) -> tuple[pd.DataFrame, list[dict]]:
    """cashflow_mapping_df에서 제외할 행을 골라 (남은 df, 제외 레코드 목록)을 반환한다.

    제외 레코드는 validate.run의 skip 목록과 동일한 형태를 따른다:
    {"row_key": 계약ID, "reason": <규칙 코드>, "details": {...}}
    — pipeline 진입점이 category="transform-filter"로 로깅한다 (validate-skip과 구분).

    ※ 의도적 no-op: 확정된 필터링 규칙이 아직 없어 입력을 그대로(복사본) 반환한다.
    누락이 아니라 규칙 부재에 따른 결정이다. 입력 불변, I/O·로깅 없음.
    """
    return cashflow_mapping_df.copy(), []
