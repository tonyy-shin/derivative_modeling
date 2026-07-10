"""
Load 단계: 변환된 DataFrame을 주어진 경로에 CSV로 저장한다 (architecture.md §3).
출력 경로 획득은 GUI/콘솔 진입점 책임이며, 이 모듈은 "주어진 경로에 쓴다"만 담당
(gui_design.md §7의 Extract-tkinter 분리 원칙과 동일).
"""

from pathlib import Path

import pandas as pd


# Error handling ---------------------------------------------------------------
class LoadError(Exception):
    """Base class for all load errors"""

class LoadWriteError(LoadError):
    """Raised when the DataFrame could not be written to the target path
    (권한 없음, 디스크 공간 부족, 대상 파일이 다른 프로그램에서 열려 있음 등)."""
    def __init__(self, message: str, path: Path, cause: Exception):
        super().__init__(message)
        self.path = path
        self.cause = cause


REASON_MESSAGES = {
    "write_failed": "출력 파일을 저장할 수 없습니다 (권한/디스크 공간/파일 사용 중 여부를 확인해주세요): {path}",
}


# Function -----------------------------------------------------------------------
def write_csv(df: pd.DataFrame, path: str) -> None:
    """df를 path에 CSV로 저장한다.

    - encoding="utf-8-sig": extract.read_csv의 읽기 인코딩과 대칭 (Excel 호환).
    - date_format="%Y-%m-%d": 출력 스펙(docs/input_output/3·4)의 날짜 표기와 일치.
    - index=False: 출력 스키마에 인덱스 컬럼이 없음.
    """
    p = Path(path)
    try:
        df.to_csv(p, index=False, encoding="utf-8-sig", date_format="%Y-%m-%d")
    except OSError as e:
        raise LoadWriteError(
            message=REASON_MESSAGES["write_failed"].format(path=p),
            path=p,
            cause=e,
        ) from e
