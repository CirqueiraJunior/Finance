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
from app.gui.controllers.budget_controller import BudgetController
from app.gui.controllers.cashflow_controller import CashflowController
from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.controllers.navigation_controller import NavigationController
from app.gui.controllers.target_controller import TargetController
from app.gui.pages.administracao import AdministracaoPage
from app.gui.pages.boe import BoePage
from app.gui.pages.cadastros import CadastrosPage
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.financeiro import FinanceiroPage
from app.gui.pages.metas import MetasPage
from app.gui.pages.orcamento import OrcamentoPage
from app.gui.pages.relatorios import RelatoriosPage
from app.importers.boe_importer import BOEImporter
from app.repositories.boe_repository import BOERepository
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.investment_repository import InvestmentRepository
from app.repositories.target_repository import TargetRepository
from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService
from app.services.cashflow_service import CashflowService
from app.services.dashboard_service import DashboardService
from app.services.financial_flow_service import FinancialFlowService
from app.services.investment_service import InvestmentService
from app.services.target_service import TargetService
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
        orcamento_page = OrcamentoPage()
        metas_page = MetasPage()
        dashboard_page = DashboardPage()
        self._boe_session = get_session_factory()()
        cashflow_service = CashflowService(CashflowRepository(self._boe_session))
        boe_service = BOEService(
            BOERepository(self._boe_session),
            EntityRepository(self._boe_session),
            BOEImporter(),
            cashflow_service,
        )
        self._boe_controller = BOEController(
            boe_page,
            boe_service,
        )
        investment_service = InvestmentService(
            InvestmentRepository(self._boe_session)
        )
        self._cashflow_controller = CashflowController(
            financeiro_page, cashflow_service, investment_service
        )
        budget_service = BudgetService(
            BudgetRepository(self._boe_session),
            CashflowRepository(self._boe_session),
        )
        self._budget_controller = BudgetController(orcamento_page, budget_service)
        target_service = TargetService(
            TargetRepository(self._boe_session),
            EntityRepository(self._boe_session),
        )
        self._target_controller = TargetController(metas_page, target_service)
        self._dashboard_controller = DashboardController(
            dashboard_page,
            DashboardService(
                FinancialFlowService(cashflow_service, investment_service),
                boe_service,
                budget_service,
                target_service,
            ),
        )

        pages = {
            "dashboard": dashboard_page,
            "financeiro": financeiro_page,
            "orcamento": orcamento_page,
            "boe": boe_page,
            "metas": metas_page,
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
