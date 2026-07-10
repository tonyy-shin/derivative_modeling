"""
파이프라인 진입점 (architecture.md §3, §4).

run_pipeline()이 Extract → Validate → Transform → Load를 순서대로 호출하는 유일한
오케스트레이션이며, JSON lines 로그 기록(validate-skip / transform-filter / fail-fast)도
architecture.md §4에 따라 전부 여기서 일괄 처리한다. GUI(src/gui/app.py의 worker())와
콘솔 진입점(main())이 모두 이 함수를 호출한다.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd

from src.extract import extract
from src.extract.extract import ExtractError, ExtractPathError, ExtractReadError
from src.load import load
from src.load.load import LoadWriteError
from src.runlog import RunLogger, new_run_logger
from src.transform import transform
from src.transform.cleaning import TransformCleaningError, TransformError
from src.transform.discounting import TransformDiscountingError
from src.validate import schemas, validate
from src.validate.validate import ValidateIndexError, ValidateStructuralError

DATE_FORMAT = "%Y-%m-%d"

# read_csv(extract.py)의 except 절과 동일한 cause 타입 -> REASON_MESSAGES 키 매핑.
# 예외 객체에는 reason 키가 남지 않으므로 cause 타입에서 역으로 복원한다
# (logging_design.md §5.1). read_csv의 분기가 바뀌면 이 목록도 같이 갱신해야 한다.
_READ_ERROR_REASON_BY_CAUSE_TYPE: list[tuple[type[Exception], str]] = [
    (pd.errors.EmptyDataError, "empty_file"),
    (pd.errors.ParserError, "malformed_csv"),
    (UnicodeDecodeError, "encoding_error"),
    (OSError, "path_unreadable"),
]


def _reason_for_read_error(e: ExtractReadError) -> str:
    for cause_type, reason in _READ_ERROR_REASON_BY_CAUSE_TYPE:
        if isinstance(e.cause, cause_type):
            return reason
    return "unmapped_read_error"


def _reason_for_path_error(e: ExtractPathError) -> str:
    return "path_unreadable" if e.attempted_path else "path_cancelled"


def run_pipeline(
    contract_path: str,
    market_path: str,
    cashflow_output_path: str,
    discount_output_path: str,
    evaluation_date,
    run_logger: RunLogger,
    on_status: Callable[[str], None] | None = None,
) -> dict:
    """파이프라인 1회 실행. 성공 시 요약 dict를 반환하고, fail-fast 예외는
    category="fail-fast"로 로깅한 뒤 호출자에게 그대로 전파한다.

    on_status: 단계 진입 시마다 한국어 진행 메시지를 받는 콜백 (GUI 상태 표시용).
    """
    status = on_status if on_status is not None else (lambda _msg: None)

    try:
        status("계약정보 추출 중...")
        contract_result = extract.read_csv(contract_path)

        status("시장금리입력 추출 중...")
        market_result = extract.read_csv(market_path)

        status("계약정보 검증 중...")
        contract_df, contract_skip = validate.run(
            contract_result.dataframe, schemas.ContractInfoSchema
        )

        status("시장금리입력 검증 중...")
        market_df, market_skip = validate.run(
            market_result.dataframe, schemas.MarketRateSchema
        )

        for source, skip_list in (("계약정보", contract_skip), ("시장금리입력", market_skip)):
            for rec in skip_list:
                run_logger.log(
                    category="validate-skip",
                    reason=rec["reason"],
                    details={"source": source, "row_key": rec["row_key"], **rec["details"]},
                )

        status("변환 중...")
        cashflow_mapping_df, discount_rate_df, filter_records = transform.run(
            contract_df, market_df, evaluation_date
        )

        for rec in filter_records:
            run_logger.log(
                category="transform-filter",
                reason=rec["reason"],
                details={"row_key": rec["row_key"], **rec["details"]},
            )

        status("저장 중...")
        load.write_csv(cashflow_mapping_df, cashflow_output_path)
        load.write_csv(discount_rate_df, discount_output_path)

        # total/success/skipped는 입력 행 기준 지표 — transform이 계약 1행을
        # leg×회차 다수 행으로 explode하므로 출력 행 수로 역산하지 않는다.
        # filtered는 transform-filter 레코드 수로 별도 집계한다 (validate-skip과
        # 카테고리 구분, architecture.md §3.1.3). 현재 필터 규칙이 no-op이라 항상
        # 0이지만, 실제 규칙이 추가돼도 요약/GUI가 바뀌지 않도록 필드는 유지한다.
        validate_skip = len(contract_skip) + len(market_skip)
        total = len(contract_result.dataframe) + len(market_result.dataframe)
        return {
            "total": total,
            "success": total - validate_skip,
            "skipped": validate_skip,
            "filtered": len(filter_records),
        }

    except ExtractReadError as e:
        run_logger.log(
            category="fail-fast",
            reason=_reason_for_read_error(e),
            details={"path": str(e.path), "cause": repr(e.cause)},
        )
        raise
    except ExtractPathError as e:
        run_logger.log(
            category="fail-fast",
            reason=_reason_for_path_error(e),
            details={"attempted_path": e.attempted_path},
        )
        raise
    except ExtractError as e:
        run_logger.log(
            category="fail-fast",
            reason="unmapped_extract_error",
            details={"message": str(e)},
        )
        raise
    except ValidateIndexError as e:
        run_logger.log(
            category="fail-fast",
            reason="duplicate_index_labels",
            details={"duplicated_labels": e.duplicated_labels},
        )
        raise
    except ValidateStructuralError as e:
        run_logger.log(
            category="fail-fast",
            reason="schema_structural_error",
            details={"columns": e.columns},
        )
        raise
    except TransformCleaningError as e:
        run_logger.log(
            category="fail-fast",
            reason="cleaning_failed",
            details={"계약ID": e.계약ID, "column": e.column, "value": e.value},
        )
        raise
    except TransformDiscountingError as e:
        run_logger.log(
            category="fail-fast",
            reason="missing_currency_curve",
            details={"계약ID": e.계약ID, "통화": e.통화},
        )
        raise
    except TransformError as e:
        run_logger.log(
            category="fail-fast",
            reason="transform_error",
            details={"message": str(e)},
        )
        raise
    except LoadWriteError as e:
        run_logger.log(
            category="fail-fast",
            reason="write_failed",
            details={"path": str(e.path), "cause": repr(e.cause)},
        )
        raise
    except Exception as e:
        # 출력 스키마 검증(pandera) 실패 등 위에서 매핑되지 않은 예외.
        run_logger.log(
            category="fail-fast",
            reason="unhandled_error",
            details={"type": type(e).__name__, "message": str(e)},
        )
        raise


# 콘솔 진입점 --------------------------------------------------------------------

def _prompt_input_path(label: str) -> str:
    """존재하는 파일 경로를 받을 때까지 재입력을 요청한다 (spec §2)."""
    while True:
        path = input(f"{label} CSV 경로를 입력하세요: ").strip()
        if path and Path(path).is_file():
            return path
        print(f"경로를 찾을 수 없습니다: {path}", file=sys.stderr)


def _prompt_output_path(label: str) -> str:
    while True:
        path = input(f"{label} 저장 경로를 입력하세요: ").strip()
        if path:
            return path


def _prompt_evaluation_date():
    while True:
        raw = input(f"평가일을 입력하세요 ({DATE_FORMAT.replace('%Y', 'YYYY').replace('%m', 'MM').replace('%d', 'DD')}): ").strip()
        try:
            return datetime.strptime(raw, DATE_FORMAT).date()
        except ValueError:
            print(f"날짜 형식이 올바르지 않습니다: {raw}", file=sys.stderr)


def main() -> None:
    contract_path = _prompt_input_path("계약정보")
    market_path = _prompt_input_path("시장금리입력")
    cashflow_output_path = _prompt_output_path("현금흐름매핑")
    discount_output_path = _prompt_output_path("회차별할인율")
    evaluation_date = _prompt_evaluation_date()

    try:
        run_logger = new_run_logger()
    except OSError as e:
        print(f"로그 디렉터리를 생성할 수 없습니다: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        summary = run_pipeline(
            contract_path,
            market_path,
            cashflow_output_path,
            discount_output_path,
            evaluation_date,
            run_logger,
            on_status=print,
        )
    except Exception as e:
        print(f"실행 실패: {e}", file=sys.stderr)
        print(f"상세 로그: {run_logger.log_path}", file=sys.stderr)
        sys.exit(1)

    print(
        f"전체 처리 행 수: {summary['total']}\n"
        f"성공: {summary['success']}\n"
        f"Skip: {summary['skipped']}\n"
        f"제외(필터): {summary['filtered']}"
    )
    print(f"로그 파일: {run_logger.log_path}")


if __name__ == "__main__":
    main()
