import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

# Result ------------------------------------------------------------------------
@dataclass(frozen=True)
class ExtractResult:
    dataframe: pd.DataFrame
    source_paths: tuple[Path, ...]
    retry_records: tuple[dict, ...] = ()


# Error handling ---------------------------------------------------------------
class ExtractError(Exception):
    """Base class for all extract errors"""

class ExtractPathError(ExtractError):
    """Raised when the user could not supply valid path"""
    def __init__(self, message: str, attempted_path: list[str]):
        super().__init__(message)
        self.attempted_path = attempted_path

class ExtractReadError(ExtractError):
    """Raised when a path exists and is readable but pandas couldn't parse as CSV"""
    def __init__(self, message: str, path: Path, cause: Exception):
        super().__init__(message)
        self.path = path
        self.cause = cause


# reason 코드 -> 사용자에게 보여줄 한국어 메시지.
# malformed_csv/empty_file/encoding_error 등 read_csv의 실패 사유 키는
# read_csv 구현 시 추가한다 (이 모듈의 현재 범위 밖).
REASON_MESSAGES = {
    "path_cancelled": "입력 파일 선택이 취소되었습니다.",
    "path_unreadable": "선택한 파일을 읽을 수 없습니다: {path}",
    "empty_file": "선택한 파일에 데이터가 없습니다: {path}",
    "malformed_csv": "CSV 형식이 올바르지 않습니다 (구분자/열 개수 불일치 등): {path}",
    "encoding_error": "파일 인코딩을 확인해주세요. UTF-8(BOM 포함) 형식이 아닙니다: {path}",
}



# Function -----------------------------------------------------------------------
def prompt_for_input_path() -> str:
    """입력 CSV 파일을 선택하는 네이티브 파일 다이얼로그를 띄운다.

    취소 시 attempted_path=[]인 ExtractPathError를, 선택한 파일의 읽기 권한이
    없을 시 attempted_path=[path]인 ExtractPathError를 발생시킨다. 재시도
    루프는 없다 — 다이얼로그는 실재하는 파일만 반환하므로 콘솔 입력 방식의
    "잘못된 경로 타이핑" 실패 모드 자체가 존재하지 않는다.
    """
    # tkinter는 GUI 경로에서만 필요하다 — 모듈 레벨에서 import하면 tkinter가 없는
    # 환경(headless 서버 등)에서 콘솔 진입점(src/pipeline.py)까지 함께 깨진다.
    from tkinter import filedialog

    path = filedialog.askopenfilename(
        title="입력 CSV 파일 선택",
        filetypes=[("CSV files", "*.csv"), ("모든 파일", "*.*")],
    )

    if not path:
        raise ExtractPathError(
            message=REASON_MESSAGES["path_cancelled"],
            attempted_path=[],
        )

    if not os.access(path, os.R_OK):
        raise ExtractPathError(
            message=REASON_MESSAGES["path_unreadable"].format(path=path),
            attempted_path=[path],
        )

    return path


def read_csv(path: str) -> ExtractResult:
    """
    Extracts the input files from path.
    """
    p = Path(path)
    try:
        df = pd.read_csv(p, encoding="utf-8-sig")
    except pd.errors.EmptyDataError as e:
        raise ExtractReadError(
            message = REASON_MESSAGES["empty_file"].format(path=p),
            path=p,
            cause=e
        ) from e
    except pd.errors.ParserError as e:
        raise ExtractReadError(
            message=REASON_MESSAGES["malformed_csv"].format(path=p),
            path=p, cause=e,
        ) from e
    except UnicodeDecodeError as e:
        raise ExtractReadError(
            message=REASON_MESSAGES["encoding_error"].format(path=p),
            path=p, cause=e,
        ) from e
    except OSError as e: 
        raise ExtractReadError(
            message=REASON_MESSAGES["path_unreadable"].format(path=p),
            path=p, cause=e,
        ) from e

    return ExtractResult(dataframe=df, source_paths=(p,))