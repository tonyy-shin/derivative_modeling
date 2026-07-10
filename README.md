# derivative_modeling

IRS/CRS 스왑 계약의 현금흐름 매핑(아웃풋 1)과 회차별 할인율/할인계수(아웃풋 2)를
생성하는 CSV ETL 파이프라인. 상세 스펙은 `docs/etl_pipeline_spec.md`,
아키텍처는 `docs/architecture.md` 참조.

## 실행 (개발 환경)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# GUI (기본 진입점)
python -m src.gui.app

# 콘솔 (경로/평가일을 프롬프트로 입력)
python -m src.pipeline
```

두 진입점 모두 레포 루트에서 실행해야 한다 (`src.*` 절대 임포트 기준).
실행 로그는 `logs/run_<타임스탬프>.jsonl`(JSON lines)로 남는다.

## Windows .exe 빌드 (PyInstaller)

**Windows에서** 빌드해야 한다 — PyInstaller는 크로스 컴파일을 지원하지 않는다.

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller IRS_CRS_Converter.spec
```

- 결과물: `dist\IRS_CRS_Converter.exe` (단일 파일, 콘솔 창 없음).
- 실행 로그는 `.exe` 파일이 위치한 디렉터리의 `logs\` 아래에 생성된다
  (`src/runlog/run_logger.py`의 frozen 분기). 따라서 `.exe`는 쓰기 가능한
  위치(예: 사용자 폴더)에 두고 실행해야 한다 — `Program Files`처럼 쓰기
  제한된 위치는 피할 것.
- `--onefile` 특성상 실행 파일이 수십~수백 MB이고 최초 실행 시 압축 해제로
  수 초 지연될 수 있다 (gui_design.md §6).
