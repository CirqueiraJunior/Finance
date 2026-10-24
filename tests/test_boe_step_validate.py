from pathlib import Path
from types import SimpleNamespace

from app.gui.controllers.boe_controller import BOEController
from app.gui.pages.boe import BoePage
from app.importers.boe_types import BOEValidationResult


def test_step_two_validates_selected_file(qtbot, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    page = BoePage()
    qtbot.addWidget(page)
    calls = []

    class ServiceStub:
        repository = SimpleNamespace(
            session=SimpleNamespace(rollback=lambda: None)
        )

        def validate_file(self, path):
            calls.append(Path(path))
            return BOEValidationResult(
                caminho_arquivo=Path(path),
                nome_arquivo=Path(path).name,
                periodo_ano=2026,
                periodo_mes=10,
            )

    controller = BOEController(
        page, ServiceStub(), defer_initial_load=True
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: ("boe_teste.xlsx", ""),
    )

    assert not page.import_steps.buttons[1].isEnabled()
    page.import_steps.buttons[0].click()
    assert page.import_steps.buttons[1].isEnabled()

    page.import_steps.buttons[1].click()
    assert calls == [Path("boe_teste.xlsx")]
    assert controller._validated_boe is not None
    assert "APROVADO" in page.validation_result.toPlainText()
