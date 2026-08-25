import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.gui.main_window import MainWindow
from app.resources import load_stylesheet


def create_application(argv: list[str] | None = None) -> QApplication:
    settings = get_settings()
    configure_logging(settings)
    application = QApplication(argv if argv is not None else sys.argv)
    application.setApplicationName(settings.app_name)
    application.setFont(QFont("Segoe UI", 10))
    application.setStyleSheet(load_stylesheet())
    return application


def main() -> int:
    application = create_application()
    window = MainWindow(get_settings())
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
