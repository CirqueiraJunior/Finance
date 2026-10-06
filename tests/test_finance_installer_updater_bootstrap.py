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


def test_updater_required_version_and_registry_contract_are_declared():
    text = source()

    assert '#define UpdaterRequiredVersion "1.0.0"' in text
    assert '#define UpdaterUninstallKey ' in text
    assert "DisplayVersion" in text
    assert "HKLM64" in text


def test_updater_detection_checks_official_executable_and_version():
    text = source()

    assert "function UpdaterNeedsInstallation(): Boolean;" in text
    assert (
        r"{autopf}\J.A. Technology\J.A. Updater\J.A. Updater.exe"
        in text
    )
    assert "if not FileExists(UpdaterExe) then" in text
    assert "RegQueryStringValue(" in text


def test_updater_version_policy_installs_only_when_older():
    text = source()

    assert "function CompareVersions(" in text
    assert "function NextVersionPart(" in text
    assert "function CompareVersionPart(" in text
    assert (
        "CompareVersions(\n"
        "      InstalledVersion,\n"
        "      '{#UpdaterRequiredVersion}'\n"
        "    ) < 0;"
        in text
    )


def test_equal_or_newer_updater_is_preserved_before_extraction():
    text = source()

    procedure = text[text.index("procedure InstallUpdaterIfRequired();"):]
    skip_check = procedure.index("if not UpdaterNeedsInstallation() then")
    extraction = procedure.index("ExtractTemporaryFile(")

    assert skip_check < extraction
    assert "if not UpdaterNeedsInstallation() then\n    Exit;" in procedure


def test_required_updater_runs_silent_bootstrap_synchronously():
    text = source()

    assert "InstallUpdaterIfRequired();" in text
    assert "ExtractTemporaryFile(" in text
    assert "'{#UpdaterInstallerName}'" in text
    assert r"{tmp}\{#UpdaterInstallerName}" in text
    assert "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-" in text
    assert "ewWaitUntilTerminated" in text


def test_bootstrap_failure_and_post_install_version_validation_are_mandatory():
    text = source()

    assert "if ResultCode <> 0 then" in text
    assert "bootstrap returned exit code %d" in text
    assert "if UpdaterNeedsInstallation() then" in text
    assert "did not install the required version" in text


def test_updater_bootstrap_precedes_finance_service_replacement():
    text = source()
    prepare = text[text.index("function PrepareToInstall"):]

    assert prepare.index("InstallUpdaterIfRequired();") < prepare.index(
        "RemovePreviousService();"
    )


def test_finance_version_fallback_and_dynamic_output_name():
    text = source()

    assert '#define ProductVersion "1.0.0"' in text
    assert "OutputBaseFilename=Finance_Setup_{#ProductVersion}" in text
