from pathlib import Path
from types import SimpleNamespace

from app.gui.controllers.boe_controller import BOEController
from app.gui.pages.boe import BoePage


def test_step_five_requires_authorization(qtbot, monkeypatch):
    page = BoePage()
    qtbot.addWidget(page)

    controller = BOEController(
        page, object(), defer_initial_load=True
    )
    calls = []
    monkeypatch.setattr(
        controller, "import_file",
        lambda: calls.append("import_file"),
    )

    assert not page.import_steps.buttons[3].isEnabled()

    controller.import_step()
    assert calls == []

    controller._selected_file = Path("teste.xlsx")
    controller._validated_boe = SimpleNamespace(
        aprovado=True,
        caminho_arquivo=Path("teste.xlsx"),
    )

    controller.import_step()
    assert calls == []

    controller._boe_step_confirmed = True
    page.import_steps.buttons[3].setEnabled(True)
    page.import_steps.buttons[3].click()

    assert calls == ["import_file"]
    assert not controller._boe_step_confirmed
    assert not page.import_steps.buttons[3].isEnabled()

    controller.import_step()
    assert calls == ["import_file"]


def test_step_five_rejects_changed_file(qtbot, monkeypatch):
    page = BoePage()
    qtbot.addWidget(page)

    controller = BOEController(
        page, object(), defer_initial_load=True
    )
    calls = []
    monkeypatch.setattr(
        controller, "import_file",
        lambda: calls.append("import_file"),
    )

    controller._selected_file = Path("novo.xlsx")
    controller._validated_boe = SimpleNamespace(
        aprovado=True,
        caminho_arquivo=Path("anterior.xlsx"),
    )
    controller._boe_step_confirmed = True
    page.import_steps.buttons[3].setEnabled(True)

    controller.import_step()

    assert calls == []
    assert not controller._boe_step_confirmed
    assert not page.import_steps.buttons[3].isEnabled()
