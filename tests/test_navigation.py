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


def test_navigation_rejects_known_but_forbidden_page(qtbot) -> None:
    stack = QStackedWidget()
    qtbot.addWidget(stack)
    index = stack.addWidget(QLabel("Administração"))
    controller = NavigationController(stack, {"administracao": index}, {"dashboard"})

    with pytest.raises(PermissionError, match="Acesso não autorizado"):
        controller.navigate_to("administracao")
