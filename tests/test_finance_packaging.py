from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "Finance.spec"
ISS = ROOT / "packaging" / "Finance.iss"


def test_finance_spec_packages_required_runtime_resources():
    text = SPEC.read_text(encoding="utf-8")

    assert 'resources_root = source_root / "app" / "resources"' in text
    assert '"styles" / "base.qss"' in text
    assert '"app/resources/styles"' in text
    assert '"icons" / "sidebar"' in text
    assert '"app/resources/icons/sidebar"' in text
    assert '"assets/branding"' in text


def test_finance_spec_remains_windowed():
    text = SPEC.read_text(encoding="utf-8")

    assert "console=False" in text


def test_finance_installer_accepts_release_version():
    text = ISS.read_text(encoding="utf-8")

    assert "#ifndef ProductVersion" in text
    assert '#define ProductVersion "1.0.0"' in text

    assert (
        "OutputBaseFilename=Finance_Setup_{#ProductVersion}"
        in text
    )


def test_finance_installer_preserves_release_paths_and_branding():
    text = ISS.read_text(encoding="utf-8")

    assert "#ifndef BuildRoot" in text
    assert "#ifndef OutputRoot" in text
    assert "OutputDir={#OutputRoot}" in text

    assert (
        'SetupIconFile=..\\assets\\branding\\finance_desktop_v100.ico'
        in text
    )

    assert (
        'Source: "{#BuildRoot}\\Finance\\*"'
        in text
    )

    assert (
        'Source: "{#BuildRoot}\\FinanceServer.exe"'
        in text
    )

    assert (
        'DefaultDirName={autopf}\\J.A. Technology\\Finance'
        in text
    )


def test_finance_specs_resolve_project_root_from_packaging_directory():
    for spec_name in ("Finance.spec", "FinanceServer.spec"):
        text = (ROOT / "packaging" / spec_name).read_text(
            encoding="utf-8"
        )

        assert (
            "project_root = Path(SPECPATH).parent"
            in text
        )
