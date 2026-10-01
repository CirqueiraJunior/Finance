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


def test_finance_release_remains_version_100():
    text = ISS.read_text(encoding="utf-8")

    assert '#define ProductVersion "1.0.0"' in text
    assert "OutputBaseFilename=Finance_Setup_1.0.0" in text
