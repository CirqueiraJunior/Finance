import logging
import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app.api_client import APIClient, APIConnectionError
from app.core.branding import apply_application_icon
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.session import get_engine
from app.database.startup import DatabaseStartupError, validate_database_startup
from app.gui.login_dialog import LoginDialog
from app.gui.main_window import MainWindow
from app.gui.splash import show_splash
from app.resources import load_stylesheet
from app.widgets.buttons import ButtonStyleFilter


def create_application(argv: list[str] | None = None) -> QApplication:
    settings = get_settings()
    configure_logging(settings)
    logging.getLogger(__name__).info("Finance iniciando.")
    application = QApplication(argv if argv is not None else sys.argv)
    application.setApplicationName(settings.app_name)
    apply_application_icon(application)
    application.setFont(QFont("Segoe UI", 10))
    application.setStyleSheet(load_stylesheet())
    application._button_style_filter = ButtonStyleFilter(application)
    application.installEventFilter(application._button_style_filter)
    return application


def _close_splash(application: QApplication, splash) -> None:
    if splash is None:
        return
    splash.close()
    splash.deleteLater()
    application.processEvents()


def main() -> int:
    application = create_application()
    splash = show_splash(application)
    settings = get_settings()

    if not settings.api_url:
        try:
            validate_database_startup(settings, get_engine())
        except DatabaseStartupError as error:
            logging.getLogger(__name__).critical("%s", error)
            print(str(error), file=sys.stderr)
            _close_splash(application, splash)
            return 1

    api_client = None
    authenticated_user = None

    if settings.api_url:
        api_client = APIClient(settings.api_url, settings.api_timeout_seconds)
        try:
            api_client.health()
        except APIConnectionError as error:
            _close_splash(application, splash)
            QMessageBox.critical(None, "Finance indisponível", str(error))
            api_client.close()
            return 1

        _close_splash(application, splash)
        splash = None

        login = LoginDialog(api_client)
        if login.exec() != QDialog.DialogCode.Accepted:
            api_client.close()
            return 0
        authenticated_user = login.user

    window = MainWindow(
        settings,
        api_client=api_client,
        authenticated_user=authenticated_user,
    )
    window.show()

    if splash is not None:
        splash.finish(window)

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
