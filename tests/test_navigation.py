import pytest
from PySide6.QtWidgets import QLabel, QStackedWidget

from app.gui.controllers.navigation_controller import NavigationController


def test_navigation_changes_current_page(qtbot) -> None:
    stack = QStackedWidget()
    qtbot.addWidget(stack)
    first = stack.addWidget(QLabel("A"))
    second = stack.addWidget(QLabel("B"))
    controller = NavigationController(stack, {"a": first, "b": second})

    controller.navigate_to("b")

    assert stack.currentIndex() == second


def test_navigation_rejects_unknown_page(qtbot) -> None:
    stack = QStackedWidget()
    qtbot.addWidget(stack)
    controller = NavigationController(stack, {})

    with pytest.raises(ValueError, match="Página desconhecida"):
        controller.navigate_to("missing")

