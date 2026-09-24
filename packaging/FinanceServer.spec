from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules


project_root = Path(SPECPATH).parent
source_root = project_root / "src"

psycopg_datas, psycopg_binaries, psycopg_hiddenimports = collect_all("psycopg")
binary_datas = collect_data_files("psycopg_binary")

datas = (
    collect_data_files("finance_server", includes=["resources/*.pem"])
    + psycopg_datas
    + binary_datas
)
binaries = psycopg_binaries
hiddenimports = sorted(set(
    collect_submodules("uvicorn")
    + psycopg_hiddenimports
    + [
        "psycopg_binary",
        "psycopg_binary._psycopg",
        "psycopg_binary._uuid",
        "psycopg_binary.pq",
        "servicemanager",
        "sqlalchemy.dialects.postgresql.psycopg",
        "win32event",
        "win32service",
        "win32serviceutil",
        "win32timezone",
    ]
))

analysis = Analysis(
    [str(source_root / "finance_server" / "windows_service.py")],
    pathex=[str(source_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="FinanceServer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "assets" / "branding" / "finance_desktop_v100.ico"),
)
