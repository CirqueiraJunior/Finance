from app import main as application_main


def test_service_configuration_mode_bypasses_normal_desktop(monkeypatch):
    monkeypatch.setattr(
        application_main.sys,
        "argv",
        ["Finance.exe", "--configure-service"],
    )
    monkeypatch.setattr(application_main, "_run_service_configuration", lambda: 7)
    monkeypatch.setattr(
        application_main,
        "create_application",
        lambda: (_ for _ in ()).throw(AssertionError("normal startup used")),
    )

    assert application_main.main() == 7
