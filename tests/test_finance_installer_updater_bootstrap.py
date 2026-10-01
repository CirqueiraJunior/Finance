from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = PROJECT_ROOT / "packaging" / "Finance.iss"


def source() -> str:
    return INSTALLER.read_text(encoding="utf-8")


def test_updater_is_required_as_external_build_dependency():
    text = source()

    assert "#ifndef UpdaterInstaller" in text
    assert "#error UpdaterInstaller define is required" in text
    assert 'Source: "{#UpdaterInstaller}"' in text
    assert "Flags: dontcopy" in text


def test_updater_installer_binary_is_not_stored_in_finance_repository():
    binaries = tuple(PROJECT_ROOT.rglob("JA_Updater_Setup*.exe"))

    assert binaries == ()


def test_bootstrap_detects_the_official_installed_executable():
    text = source()

    assert "function UpdaterInstalled(): Boolean;" in text
    assert (
        r"{autopf}\J.A. Technology\J.A. Updater\J.A. Updater.exe"
        in text
    )


def test_existing_updater_is_preserved_before_temporary_extraction():
    text = source()
    installed_check = text.index("if UpdaterInstalled() then")
    extraction = text.index("ExtractTemporaryFile('{#UpdaterInstallerName}')")

    assert installed_check < extraction
    assert "if UpdaterInstalled() then\n    exit;" in text


def test_missing_updater_runs_silent_bootstrap_synchronously():
    text = source()

    assert "EnsureUpdaterInstalled();" in text
    assert "ExtractTemporaryFile('{#UpdaterInstallerName}')" in text
    assert "{tmp}\\{#UpdaterInstallerName}" in text
    assert "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-" in text
    assert "ewWaitUntilTerminated" in text


def test_bootstrap_failure_and_post_install_validation_are_mandatory():
    text = source()

    assert "if ResultCode <> 0 then" in text
    assert "bootstrap returned exit code %d" in text
    assert text.count("if not UpdaterInstalled() then") == 1
    assert "completed without the expected executable" in text


def test_updater_bootstrap_precedes_finance_service_replacement():
    text = source()
    prepare = text[text.index("function PrepareToInstall"):]

    assert prepare.index("EnsureUpdaterInstalled();") < prepare.index(
        "RemovePreviousService();"
    )


def test_finance_version_and_output_name_remain_100():
    text = source()

    assert '#define ProductVersion "1.0.0"' in text
    assert "OutputBaseFilename=Finance_Setup_1.0.0" in text
