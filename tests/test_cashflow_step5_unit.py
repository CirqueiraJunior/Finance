from types import SimpleNamespace

from app.gui.controllers.cashflow_controller import CashflowController


class Stages:
    def __init__(self):
        self.states = {}

    def set_stage_enabled(self, stage, enabled):
        self.states[stage] = bool(enabled)


def context():
    stages = Stages()
    calls = []
    obj = SimpleNamespace(
        view=SimpleNamespace(
            import_steps=stages,
            set_status=lambda *args, **kwargs: None,
        ),
        import_file_path="financeiro.xlsx",
        _import_validated=True,
        _import_compared=True,
        _import_step_confirmed=True,
        _authorized_import_file="financeiro.xlsx",
        _import_thread=None,
        _last_import_validation={"can_import": True},
        import_validated_file=lambda: calls.append("import"),
    )
    return obj, stages, calls


def test_authorization_is_single_use():
    obj, stages, calls = context()
    CashflowController.import_step(obj)
    CashflowController.import_step(obj)
    assert calls == ["import"]
    assert obj._import_step_confirmed is False
    assert stages.states[4] is False


def test_missing_authorization_blocks_import():
    obj, stages, calls = context()
    obj._import_step_confirmed = False
    CashflowController.import_step(obj)
    assert calls == []
    assert stages.states[4] is False


def test_invalid_validation_blocks_import():
    obj, stages, calls = context()
    obj._last_import_validation["can_import"] = False
    CashflowController.import_step(obj)
    assert calls == []
    assert stages.states[4] is False


def test_cancel_final_confirmation_blocks_processing():
    obj = SimpleNamespace(
        import_service=object(),
        import_file_path="financeiro.xlsx",
        _import_validated=True,
        _import_thread=None,
        _request_final_import_confirmation=lambda: False,
        view=SimpleNamespace(
            set_status=lambda *args, **kwargs: None,
        ),
    )
    # Any attempt to proceed would access missing UI controls.
    CashflowController.import_validated_file(obj)
