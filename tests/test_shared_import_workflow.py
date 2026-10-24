import pytest

from app.gui.import_workflow_steps import ImportWorkflowSteps


def test_shared_workflow_routes_five_actions(qtbot):
    widget = ImportWorkflowSteps()
    qtbot.addWidget(widget)
    original_buttons = tuple(widget.buttons)
    calls = []

    widget.configure_actions(
        on_select=lambda: calls.append("select"),
        on_validate=lambda: calls.append("validate"),
        on_compare=lambda: calls.append("compare"),
        on_confirm=lambda: calls.append("confirm"),
        on_import=lambda: calls.append("import"),
    )

    widget.reset_stages()
    assert widget.buttons[0].isEnabled()
    assert not any(
        button.isEnabled() for button in widget.buttons[1:]
    )

    widget.buttons[0].click()
    assert calls == ["select"]

    for stage in range(2, 6):
        widget.set_stage_enabled(stage, True)
        widget.buttons[stage - 1].click()

    assert calls == [
        "select", "validate", "compare", "confirm", "import"
    ]
    assert tuple(widget.buttons) == original_buttons


def test_shared_workflow_rejects_duplicate_binding(qtbot):
    widget = ImportWorkflowSteps()
    qtbot.addWidget(widget)

    widget.configure_actions(on_select=lambda: None)

    with pytest.raises(RuntimeError):
        widget.configure_actions(on_select=lambda: None)


def test_shared_workflow_rejects_invalid_stage(qtbot):
    widget = ImportWorkflowSteps()
    qtbot.addWidget(widget)

    with pytest.raises(ValueError):
        widget.set_stage_enabled(0, True)

    with pytest.raises(ValueError):
        widget.set_stage_enabled(6, True)
