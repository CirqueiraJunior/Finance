from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core.config import Settings
from app.database.session import get_session_factory
from app.gui.controllers.boe_controller import BOEController
from app.gui.controllers.cashflow_controller import CashflowController
from app.gui.controllers.navigation_controller import NavigationController
from app.gui.pages.administracao import AdministracaoPage
from app.gui.pages.boe import BoePage
from app.gui.pages.cadastros import CadastrosPage
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.financeiro import FinanceiroPage
from app.gui.pages.metas import MetasPage
from app.gui.pages.relatorios import RelatoriosPage
from app.importers.boe_importer import BOEImporter
from app.repositories.boe_repository import BOERepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.entity_repository import EntityRepository
from app.services.boe_service import BOEService
from app.services.cashflow_service import CashflowService
from app.widgets.sidebar import Sidebar
from app.widgets.topbar import TopBar


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.setObjectName("mainWindow")
        self.setWindowTitle(settings.app_name)
        self.resize(1200, 760)
        self.setMinimumSize(900, 600)

        boe_page = BoePage()
        financeiro_page = FinanceiroPage()
        self._boe_session = get_session_factory()()
        cashflow_service = CashflowService(CashflowRepository(self._boe_session))
        self._boe_controller = BOEController(
            boe_page,
            BOEService(
                BOERepository(self._boe_session),
                EntityRepository(self._boe_session),
                BOEImporter(),
                cashflow_service,
            ),
        )
        self._cashflow_controller = CashflowController(
            financeiro_page, cashflow_service
        )

        pages = {
            "dashboard": DashboardPage(),
            "financeiro": financeiro_page,
            "boe": boe_page,
            "metas": MetasPage(),
            "cadastros": CadastrosPage(),
            "relatorios": RelatoriosPage(),
            "administracao": AdministracaoPage(),
        }
        stack = QStackedWidget()
        indexes = {key: stack.addWidget(page) for key, page in pages.items()}
        self.navigation = NavigationController(stack, indexes)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(Sidebar(self.navigation.navigate_to))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(TopBar("Gestão financeira"))
        content_layout.addWidget(stack)
        body_layout.addWidget(content, 1)
        self.setCentralWidget(body)

        status = QStatusBar()
        status.showMessage(f"Ambiente: {settings.app_env} | Pronto")
        self.setStatusBar(status)
        self.navigation.navigate_to("dashboard")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._boe_session.close()
        super().closeEvent(event)
