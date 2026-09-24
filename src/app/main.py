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
from app.gui.initial_setup_dialog import InitialSetupDialog
from app.gui.main_window import MainWindow
from app.gui.splash import hold_splash, show_splash
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


def _run_service_configuration() -> int:
    from app.gui.service_config_dialog import ServiceConfigurationDialog

    application = create_application()
    dialog = ServiceConfigurationDialog()
    result = dialog.exec()
    application.processEvents()
    return 0 if result == QDialog.DialogCode.Accepted else 1


def main() -> int:
    if "--configure-service" in sys.argv[1:]:
        return _run_service_configuration()

    application = create_application()
    splash = show_splash(application)
    hold_splash(splash)
    _close_splash(application, splash)
    splash = None
    settings = get_settings()

    if not settings.api_url:
        try:
            validate_database_startup(settings, get_engine())
        except DatabaseStartupError as error:
            logging.getLogger(__name__).critical("%s", error)
            print(str(error), file=sys.stderr)
            return 1

    api_client = None
    authenticated_user = None

    if settings.api_url:
        api_client = APIClient(settings.api_url, settings.api_timeout_seconds)
        try:
            api_client.health()
        except APIConnectionError as error:
            QMessageBox.critical(None, "Finance indisponível", str(error))
            api_client.close()
            return 1

        try:
            requires_initial_setup = api_client.initial_setup_required()
        except APIConnectionError as error:
            QMessageBox.critical(None, "Finance indisponível", str(error))
            api_client.close()
            return 1
        except RuntimeError as error:
            QMessageBox.critical(None, "Configuração inicial", str(error))
            api_client.close()
            return 1

        if requires_initial_setup:
            setup = InitialSetupDialog(api_client)
            if setup.exec() != QDialog.DialogCode.Accepted:
                api_client.close()
                return 0

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

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
