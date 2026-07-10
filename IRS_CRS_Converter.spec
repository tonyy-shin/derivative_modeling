# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 빌드 스펙 (gui_design.md §6: onefile + windowed).
# 빌드: 레포 루트에서 `pyinstaller IRS_CRS_Converter.spec`
# Windows .exe는 Windows에서 빌드해야 한다 (PyInstaller는 크로스 컴파일 미지원).

a = Analysis(
    ["src/gui/app.py"],
    # `from src.extract import extract` 등 절대 임포트가 레포 루트 기준이므로
    # SPECPATH(이 spec 파일이 있는 디렉터리 = 레포 루트)를 검색 경로에 넣는다.
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="IRS_CRS_Converter",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # --windowed: 검은 콘솔 창이 함께 뜨지 않도록 (비개발자 사용자 대상, gui_design.md §6)
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
