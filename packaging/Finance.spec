from pathlib import Path


project_root = Path(SPECPATH).parent.parent
source_root = project_root / "src"

resources_root = source_root / "app" / "resources"

datas = [
    (str(project_root / "assets" / "branding"), "assets/branding"),
    (
        str(resources_root / "styles" / "base.qss"),
        "app/resources/styles",
    ),
    (
        str(resources_root / "icons" / "sidebar"),
        "app/resources/icons/sidebar",
    ),
]

analysis = Analysis(
    [str(source_root / "app" / "main.py")],
    pathex=[str(source_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "app.resources",
        "app.gui.service_config_dialog",
        "finance_server.service_config",
        "finance_server.service_setup",
        "win32security",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Finance",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / "assets" / "branding" / "finance_desktop_v100.ico"),
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Finance",
)
