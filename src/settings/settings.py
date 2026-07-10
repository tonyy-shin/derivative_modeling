"""
마지막 사용 설정(입출력 경로, 평가일) 영속화.

GUI 실행 간에 사용자가 입력한 값이 사라지지 않도록 settings.json 하나에
최신 값만 덮어쓴다 (runlog의 JSON lines 실행 로그와는 별개 — 이력이 아니라
"마지막 값"만 필요하므로 append가 아닌 overwrite).

로드/저장 실패는 전부 조용히 무시한다 — 설정 파일이 없거나 깨졌다고 GUI가
못 뜨거나 실행이 막히면 안 된다. 실패 시 load는 빈 dict를 반환하고
save는 아무 일도 하지 않는다.
"""

import json
import sys
from pathlib import Path

# app.py의 StringVar 이름과 1:1 대응하는 키만 저장/복원한다.
SETTINGS_KEYS = (
    "contract_path",       # 계약정보 입력 경로
    "market_path",         # 시장금리입력 입력 경로
    "cashflow_output_path",  # 현금흐름매핑 출력 경로
    "discount_output_path",  # 회차별할인율 출력 경로
    "eval_date",           # 평가일 (YYYY-MM-DD 문자열)
)


def default_settings_path() -> Path:
    """settings.json의 경로를 결정한다.

    기준 디렉터리 결정 로직은 run_logger.default_log_dir()와 동일하게 유지한다
    (PyInstaller onefile frozen이면 .exe 옆, 아니면 레포 루트). 4줄짜리 안정적인
    분기라서 runlog에 의존성을 만드는 대신 여기 중복해 둔다 — 한쪽을 바꾸면
    다른 쪽도 같이 확인할 것.
    """
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).resolve().parents[2]
    return base / "settings.json"


def load_last_settings() -> dict:
    """저장된 마지막 설정을 읽어 dict로 반환한다.

    파일이 없거나, 읽을 수 없거나, JSON이 깨졌거나, dict가 아니면 빈 dict를
    반환한다 — 팝업/예외 없이 빈 필드로 시작하는 것이 정상 흐름이다.
    알려진 키의 문자열 값만 통과시킨다.
    """
    try:
        raw = json.loads(default_settings_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        key: value
        for key, value in raw.items()
        if key in SETTINGS_KEYS and isinstance(value, str)
    }


def save_last_settings(settings: dict) -> None:
    """설정을 settings.json에 덮어쓴다. 쓰기 실패(권한 등)는 조용히 무시한다."""
    filtered = {key: settings.get(key, "") for key in SETTINGS_KEYS}
    try:
        default_settings_path().write_text(
            json.dumps(filtered, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
