from app.core.config import get_settings
from app.gui.main_window import MainWindow


def test_main_window_has_required_shell(qtbot) -> None:
    window = MainWindow(get_settings())
    qtbot.addWidget(window)

    assert window.centralWidget() is not None
    assert window.statusBar() is not None
    assert window.windowTitle() == "J.A. Finance"

