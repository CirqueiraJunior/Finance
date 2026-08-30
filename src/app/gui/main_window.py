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
from app.core.branding import apply_window_icon
from app.database.session import get_engine, get_session_factory
from app.gui.controllers.administration_controller import AdministrationController
from app.gui.controllers.boe_controller import BOEController
from app.gui.controllers.budget_controller import BudgetController
from app.gui.controllers.cashflow_controller import CashflowController
from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.controllers.navigation_controller import NavigationController
from app.gui.controllers.report_controller import ReportController
from app.gui.controllers.target_controller import TargetController
from app.gui.controllers.registration_controller import (
    RegistrationController,
    RemoteRegistrationController,
)
from app.gui.pages.administracao import AdministracaoPage
from app.gui.pages.boe import BoePage
from app.gui.pages.cadastros import CadastrosPage
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.financeiro import FinanceiroPage
from app.gui.pages.metas import MetasPage
from app.gui.pages.orcamento import OrcamentoPage
from app.gui.pages.relatorios import RelatoriosPage
from app.importers.boe_importer import BOEImporter
from app.importers.historical_importer import HistoricalWorkbookImporter
from app.repositories.association_repository import AssociationRepository
from app.repositories.boe_repository import BOERepository
from app.repositories.csv_export_repository import CSVExportRepository
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.investment_repository import InvestmentRepository
from app.repositories.target_repository import TargetRepository
from app.services.boe_service import BOEService
from app.services.administration_service import AdministrationService
from app.services.backup_service import BackupService
from app.services.report_service import ReportService
from app.services.site_csv_service import SiteCSVService
from app.services.budget_service import BudgetService
from app.services.cashflow_service import CashflowService
from app.services.dashboard_service import DashboardService
from app.services.financial_flow_service import FinancialFlowService
from app.services.investment_service import InvestmentService
from app.services.target_service import TargetService
from app.services.ranking_service import RankingService
from app.services.cashflow_catalog_service import CashflowCatalogService
from app.services.entity_service import EntityService
from app.services.historical_import_service import HistoricalImportService
from app.widgets.sidebar import Sidebar
from app.widgets.app_header import AppHeader
from app.api_client.client import APIClient, AuthenticatedUser
from app.gui.login_dialog import LoginDialog
from PySide6.QtWidgets import QDialog
from app.services.remote_services import (
    RemoteBOEService, RemoteBudgetService, RemoteCashflowService,
    RemoteCatalogService, RemoteCSVService, RemoteDashboardService,
    RemoteFinancialFlowService, RemoteInvestmentService, RemoteRankingService,
    RemoteReportService, RemoteTargetService,
)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, *, api_client: APIClient | None = None,
                 authenticated_user: AuthenticatedUser | None = None) -> None:
        super().__init__()
        self.setObjectName("mainWindow")
        apply_window_icon(self)
        self.setWindowTitle(settings.app_name)
        self.resize(1200, 760)
        self.setMinimumSize(900, 600)

        boe_page = BoePage()
        financeiro_page = FinanceiroPage()
        orcamento_page = OrcamentoPage()
        metas_page = MetasPage()
        dashboard_page = DashboardPage()
        relatorios_page = RelatoriosPage()
        cadastros_page = CadastrosPage()
        administracao_page = AdministracaoPage()

        self._boe_session = None
        if api_client is not None:
            cashflow_service = RemoteCashflowService(api_client)
            investment_service = RemoteInvestmentService(api_client)
            financial_flow = RemoteFinancialFlowService(api_client)
            boe_service = RemoteBOEService(api_client)
            budget_service = RemoteBudgetService(api_client)
            catalog_service = RemoteCatalogService(api_client)
            target_service = RemoteTargetService(api_client)
            self._boe_controller = BOEController(boe_page, boe_service)
            self._cashflow_controller = CashflowController(
                financeiro_page, cashflow_service, investment_service,
                financial_flow=financial_flow,
                catalog_service=catalog_service,
            )
            self._budget_controller = BudgetController(
                orcamento_page, budget_service, catalog_service)
            self._target_controller = TargetController(
                metas_page, target_service, RemoteRankingService(api_client))
            self._dashboard_controller = DashboardController(
                dashboard_page, RemoteDashboardService(api_client))
            self._report_controller = ReportController(
                relatorios_page, RemoteReportService(api_client), RemoteCSVService(api_client))
            self._registration_controller = RemoteRegistrationController(
                cadastros_page, api_client
            )
            administracao_page.logs_button.setEnabled(False)
            administracao_page.backup_button.setEnabled(False)
            administracao_page.import_button.setEnabled(False)
            administracao_page.set_status(
                "Modo servidor: operações administrativas locais estão bloqueadas."
            )
        else:
            self._boe_session = get_session_factory()()
            cashflow_service = CashflowService(CashflowRepository(self._boe_session))
            boe_service = BOEService(
                BOERepository(self._boe_session), EntityRepository(self._boe_session),
                BOEImporter(), cashflow_service,
            )
            investment_service = InvestmentService(InvestmentRepository(self._boe_session))
            financial_flow = FinancialFlowService(cashflow_service, investment_service)
            budget_service = BudgetService(BudgetRepository(self._boe_session), CashflowRepository(self._boe_session))
            catalog_service = CashflowCatalogService(
                CashflowCatalogRepository(self._boe_session))
            target_service = TargetService(TargetRepository(self._boe_session), EntityRepository(self._boe_session))
            self._boe_controller = BOEController(boe_page, boe_service)
            self._cashflow_controller = CashflowController(financeiro_page, cashflow_service, investment_service)
            self._budget_controller = BudgetController(
                orcamento_page, budget_service, catalog_service)
            self._target_controller = TargetController(
                metas_page, target_service,
                RankingService(TargetRepository(self._boe_session), AssociationRepository(self._boe_session)))
            self._dashboard_controller = DashboardController(
                dashboard_page, DashboardService(financial_flow, boe_service, budget_service, target_service))
            self._report_controller = ReportController(
                relatorios_page, ReportService(financial_flow, boe_service, budget_service),
                SiteCSVService(EntityRepository(self._boe_session), TargetRepository(self._boe_session),
                               AssociationRepository(self._boe_session), CSVExportRepository(self._boe_session)))
            entity_service = EntityService(EntityRepository(self._boe_session))
            self._registration_controller = RegistrationController(
                cadastros_page, entity_service, catalog_service
            )
            backup_service = BackupService(settings)
            historical_service = HistoricalImportService(
                self._boe_session, HistoricalWorkbookImporter(), entity_service,
                catalog_service, backup_service, boe_service)
            self._administration_controller = AdministrationController(
                administracao_page, AdministrationService(self._boe_session, settings, get_engine()),
                backup_service, historical_service)
        if api_client is not None:
            administracao_page.refresh_button.clicked.connect(
                lambda: self._load_remote_information(administracao_page))
            administracao_page.server_button.clicked.connect(
                lambda: self._load_server_status(administracao_page))
            administracao_page.users_button.clicked.connect(
                lambda: self._load_remote_users(administracao_page))
            administracao_page.audit_button.clicked.connect(
                lambda: self._load_remote_audit(administracao_page))

        self.pages = {
            "dashboard": dashboard_page,
            "financeiro": financeiro_page,
            "orcamento": orcamento_page,
            "boe": boe_page,
            "metas": metas_page,
            "cadastros": cadastros_page,
            "relatorios": relatorios_page,
            "administracao": administracao_page,
        }

        stack = QStackedWidget()
        indexes = {key: stack.addWidget(page) for key, page in self.pages.items()}
        self.navigation = NavigationController(stack, indexes)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._api_client = api_client
        self.header = AppHeader(
            user_name=authenticated_user.nome if authenticated_user else "",
            user_role=authenticated_user.perfil if authenticated_user else "",
        )
        self.header.logout_button.clicked.connect(self._logout)
        root_layout.addWidget(self.header)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar(self.navigation.navigate_to)
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(stack, 1)

        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

        status = QStatusBar()
        connection = "Servidor conectado" if api_client else "Modo local de desenvolvimento"
        status.showMessage(f"Ambiente: {settings.app_env} | {connection} | Pronto")
        self.setStatusBar(status)

        self.navigation.navigate_to("dashboard")

    def _logout(self) -> None:
        if self._api_client is None:
            self.close()
            return
        self._api_client.logout()
        self.hide()
        dialog = LoginDialog(self._api_client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.user is not None:
            self.header.user.setText(f"{dialog.user.nome}\n{dialog.user.perfil}")
            self.show()
        else:
            self.close()

    def _load_server_status(self, page: AdministracaoPage) -> None:
        try:
            health = self._api_client.health()
            page.set_status(f"API online | versão {health['version']} | banco de produção: PostgreSQL")
        except RuntimeError as error:
            page.set_status(str(error), error=True)

    def _load_remote_information(self, page: AdministracaoPage) -> None:
        try:
            health = self._api_client.health()
            page.show_remote_information(health)
            page.set_status("Informações centrais atualizadas.")
        except RuntimeError as error:
            page.set_status(f"Falha ao consultar informações: {error}", error=True)

    def _load_remote_users(self, page: AdministracaoPage) -> None:
        try:
            values = self._api_client.get("/api/v1/users")
            page.show_remote_rows([(str(item["id"]), item["nome"], item["perfil"],
                                    "Ativo" if item["ativo"] else "Inativo") for item in values])
            page.set_status("Usuários atualizados.")
        except RuntimeError as error:
            page.set_status(str(error), error=True)

    def _load_remote_audit(self, page: AdministracaoPage) -> None:
        try:
            values = self._api_client.get("/api/v1/audit")
            page.show_remote_rows([(item["timestamp"], str(item.get("user_id") or "—"),
                                    item["action"], item.get("entity_type") or "—") for item in values])
            page.set_status("Auditoria atualizada (somente leitura).")
        except RuntimeError as error:
            page.set_status(str(error), error=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._api_client is not None:
            self._api_client.logout()
            self._api_client.close()
        if self._boe_session is not None:
            self._boe_session.close()
        super().closeEvent(event)
