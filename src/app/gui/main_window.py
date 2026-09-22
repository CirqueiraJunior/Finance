from PySide6.QtCore import QThread, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QInputDialog, QLineEdit, QMessageBox,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core.config import Settings
from app.core.gui_rbac import (
    allowed_dashboard_areas, allowed_modules, allowed_registration_areas,
    role_has_permission, role_label,
)
from app.core.branding import apply_window_icon
from finance_server.security import validate_password
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
from app.gui.pages.administracao import AdministracaoPage, UserDialog
from app.gui.pages.boe import BoePage
from app.gui.pages.cadastros import CadastrosPage
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.financeiro import FinanceiroPage
from app.gui.pages.metas import MetasPage
from app.gui.pages.orcamento import OrcamentoPage
from app.gui.pages.relatorios import RelatoriosPage
from app.gui.pages.historical_import import HistoricalImportDialog
from app.gui.controllers.historical_import_controller import HistoricalImportController
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
from app.gui.login_dialog import ChangePasswordDialog, LoginDialog
from app.gui.help_dialog import HelpDialog
from app.gui.processing import OperationWorker
from app.services.update_service import UpdateCheckResult, UpdateService, UpdateStatus
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
        initial_role = authenticated_user.perfil if authenticated_user else "ADMINISTRADOR"
        self._authenticated_role = initial_role
        dashboard_areas = (
            allowed_dashboard_areas(initial_role)
        )
        dashboard_page.set_allowed_areas(dashboard_areas)
        relatorios_page = RelatoriosPage()
        cadastros_page = CadastrosPage()
        administracao_page = AdministracaoPage()
        self._update_service = UpdateService()
        self._update_thread: QThread | None = None
        self._update_worker: OperationWorker | None = None
        self._update_page: AdministracaoPage | None = None
        administracao_page.check_updates_button.clicked.connect(
            lambda: self._check_for_updates(administracao_page)
        )

        self._boe_session = None
        self._historical_import_service = None
        self._api_health = api_client.health() if api_client is not None else None
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
                import_service=cashflow_service,
            )
            self._budget_controller = BudgetController(
                orcamento_page, budget_service, catalog_service)
            self._target_controller = TargetController(
                metas_page, target_service, RemoteRankingService(api_client))
            self._remote_dashboard_service = RemoteDashboardService(
                api_client, dashboard_areas
            )
            self._dashboard_controller = DashboardController(
                dashboard_page, self._remote_dashboard_service)
            self._cashflow_controller.import_completed.connect(
                self._dashboard_controller.refresh
            )
            self._report_controller = ReportController(
                relatorios_page, RemoteReportService(api_client), RemoteCSVService(api_client))
            self._registration_controller = RemoteRegistrationController(
                cadastros_page, api_client,
                allowed_areas=allowed_registration_areas(initial_role),
            )
            administracao_page.logs_button.setEnabled(False)
            administracao_page.backup_button.setEnabled(False)
            historical_enabled = bool(
                self._api_health.get("historical_import_enabled")
                if self._api_health else False
            )
            administracao_page.import_button.setEnabled(historical_enabled)
            if historical_enabled:
                self._boe_session = get_session_factory()()
                entity_service = EntityService(EntityRepository(self._boe_session))
                local_catalog = CashflowCatalogService(
                    CashflowCatalogRepository(self._boe_session)
                )
                local_cashflow = CashflowService(CashflowRepository(self._boe_session))
                local_boe = BOEService(
                    BOERepository(self._boe_session), EntityRepository(self._boe_session),
                    BOEImporter(), local_cashflow,
                )
                self._historical_import_service = HistoricalImportService(
                    self._boe_session, HistoricalWorkbookImporter(), entity_service,
                    local_catalog, BackupService(settings), local_boe,
                )
                administracao_page.import_button.clicked.connect(
                    lambda: self._open_historical_import(administracao_page)
                )
                administracao_page.set_status(
                    "Ambiente DEV: importação histórica local disponível."
                )
            else:
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
            self._cashflow_controller.import_completed.connect(
                self._dashboard_controller.refresh
            )
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
            self._apply_administration_permissions(administracao_page, initial_role)
            administracao_page.change_password_button.clicked.connect(
                self._change_password
            )
            administracao_page.compact_change_password_button.clicked.connect(
                self._change_password
            )
            administracao_page.refresh_button.clicked.connect(
                lambda: self._load_remote_information(administracao_page))
            administracao_page.server_button.clicked.connect(
                lambda: self._load_server_status(administracao_page))
            administracao_page.users_button.clicked.connect(
                lambda: self._load_remote_users(administracao_page))
            administracao_page.reload_users_button.clicked.connect(
                lambda: self._load_remote_users(administracao_page))
            administracao_page.new_user_button.clicked.connect(
                lambda: self._create_remote_user(administracao_page))
            administracao_page.edit_user_button.clicked.connect(
                lambda: self._edit_remote_user(administracao_page))
            administracao_page.toggle_user_button.clicked.connect(
                lambda: self._toggle_remote_user(administracao_page))
            administracao_page.reset_password_button.clicked.connect(
                lambda: self._reset_remote_user_password(administracao_page))
            administracao_page.audit_button.clicked.connect(
                lambda: self._load_remote_audit(administracao_page))
            administracao_page.ranking_parameters_widget.load_button.clicked.connect(
                lambda: self._load_ranking_parameters(administracao_page)
            )
            administracao_page.ranking_parameters_widget.save_button.clicked.connect(
                lambda: self._save_ranking_parameters(administracao_page)
            )
        else:
            administracao_page.set_user_management_enabled(False)

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
        initial_modules = set(indexes) if api_client is None else allowed_modules(initial_role)
        self.navigation = NavigationController(stack, indexes, initial_modules)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._api_client = api_client
        self.header = AppHeader(
            user_name=authenticated_user.nome if authenticated_user else "",
            user_role=role_label(authenticated_user.perfil) if authenticated_user else "",
        )
        self.header.logout_button.clicked.connect(self._logout)
        root_layout.addWidget(self.header)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar(
            self._handle_sidebar_action,
            allowed_pages=initial_modules,
            on_logout=self._logout,
        )
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(stack, 1)

        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

        status = QStatusBar()
        connection = "Servidor conectado" if api_client else "Modo local de desenvolvimento"
        status.showMessage(f"Ambiente: {settings.app_env} | {connection} | Pronto")
        self.setStatusBar(status)

        if authenticated_user is not None:
            self._apply_desktop_permissions(initial_role)

        first_page = self.navigation.first_allowed_page()
        if first_page is not None:
            self.navigation.navigate_to(first_page)
            self.sidebar.select_page(first_page)

    def apply_authenticated_user(self, user: AuthenticatedUser) -> None:
        self._authenticated_role = user.perfil
        modules = allowed_modules(user.perfil)
        self.navigation.set_allowed_pages(modules)
        self.sidebar.set_allowed_pages(modules)
        dashboard_areas = allowed_dashboard_areas(user.perfil)
        self.pages["dashboard"].set_allowed_areas(dashboard_areas)
        if hasattr(self, "_remote_dashboard_service"):
            self._remote_dashboard_service.areas = dashboard_areas
        self.header.user.setText(f"{user.nome}\n{role_label(user.perfil)}")
        self.header.user.setVisible(True)
        self.header.logout_button.setVisible(False)
        self._apply_administration_permissions(
            self.pages["administracao"], user.perfil
        )
        self._registration_controller.set_allowed_areas(
            allowed_registration_areas(user.perfil)
        )
        self._apply_desktop_permissions(user.perfil)
        first_page = self.navigation.first_allowed_page()
        if first_page is not None:
            self.navigation.navigate_to(first_page)
            self.sidebar.select_page(first_page)

    @staticmethod
    def _apply_administration_permissions(
        page: AdministracaoPage, role: str
    ) -> None:
        page.set_remote_action_permissions(
            can_read_admin=role_has_permission(role, "admin:read"),
            can_manage_users=role_has_permission(role, "users:manage"),
            can_read_audit=role_has_permission(role, "audit:read"),
            can_manage_ranking=role == "ADMINISTRADOR",
        )

    def _apply_desktop_permissions(self, role: str) -> None:
        cashflow_write = role_has_permission(role, "cashflow:write")
        self.pages["financeiro"].new_entry_button.setEnabled(cashflow_write)
        self.pages["financeiro"].select_import_button.setEnabled(cashflow_write)
        if not cashflow_write:
            self.pages["financeiro"].validate_import_button.setEnabled(False)
            self.pages["financeiro"].confirm_import_button.setEnabled(False)

        budget_write = role_has_permission(role, "budget:write")
        for button in (
            self.pages["orcamento"].new_button,
            self.pages["orcamento"].edit_button,
            self.pages["orcamento"].import_file_button,
        ):
            button.setEnabled(budget_write)
        if not budget_write:
            self.pages["orcamento"].confirm_import_button.setEnabled(False)

        boe_write = role_has_permission(role, "boe:write")
        self.pages["boe"].select_button.setEnabled(boe_write)
        if not boe_write:
            self.pages["boe"].validate_button.setEnabled(False)
            self.pages["boe"].import_button.setEnabled(False)

        target_write = role_has_permission(role, "targets:write")
        for button in (
            self.pages["metas"].new_button,
            self.pages["metas"].edit_button,
            self.pages["metas"].import_file_button,
        ):
            button.setEnabled(target_write)
        if not target_write:
            self.pages["metas"].confirm_import_button.setEnabled(False)

        reports_export = role_has_permission(role, "reports:export")
        self.pages["relatorios"].choose_folder_button.setEnabled(reports_export)
        self.pages["relatorios"].export_button.setEnabled(reports_export)

        registration = self.pages["cadastros"]
        areas = allowed_registration_areas(role)
        registration.tabs.setTabVisible(0, "entities" in areas)
        registration.tabs.setTabVisible(1, "catalog" in areas)
        if "entities" in areas:
            registration.tabs.setCurrentIndex(0)
        elif "catalog" in areas:
            registration.tabs.setCurrentIndex(1)
        entity_write = role_has_permission(role, "entities:manage")
        for button in (
            registration.new_entity_button,
            registration.edit_entity_button,
            registration.toggle_entity_button,
        ):
            button.setEnabled(entity_write)
        registration.aliases_button.setEnabled("entities" in areas)
        catalog_write = role_has_permission(role, "catalog:manage")
        registration.new_catalog_button.setEnabled(catalog_write)
        registration.edit_catalog_button.setEnabled(catalog_write)

    def _handle_sidebar_action(self, page_key: str) -> None:
        if page_key == "__help__":
            HelpDialog(self).exec()
            return
        self.navigation.navigate_to(page_key)

    def _change_password(self) -> None:
        if self._api_client is not None:
            ChangePasswordDialog(self._api_client, self).exec()

    def _logout(self) -> None:
        if self._api_client is None:
            self.close()
            return
        self._api_client.logout()
        self.hide()
        dialog = LoginDialog(self._api_client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.user is not None:
            self.apply_authenticated_user(dialog.user)
            self.show()
        else:
            self.close()

    def _load_server_status(self, page: AdministracaoPage) -> None:
        try:
            health = self._api_client.health()
            page.set_status(
                f"API online | versão {health['version']} | "
                f"{health.get('database', 'banco não informado')}"
            )
        except RuntimeError as error:
            page.set_status(str(error), error=True)

    def _check_for_updates(self, page: AdministracaoPage) -> None:
        if self._update_thread is not None and self._update_thread.isRunning():
            return
        page.set_update_check_running(True)
        page.set_status("Consultando a última versão publicada...")
        self._update_page = page
        self._update_thread = QThread(self)
        self._update_worker = OperationWorker(self._update_service.check)
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.succeeded.connect(self._update_succeeded)
        self._update_worker.failed.connect(self._update_failed)
        self._update_worker.finished.connect(self._update_thread.quit)
        self._update_worker.finished.connect(self._update_worker.deleteLater)
        self._update_thread.finished.connect(self._finish_update_check)
        self._update_thread.start()

    @Slot(object)
    def _update_succeeded(self, result: UpdateCheckResult) -> None:
        if self._update_page is None:
            return
        if result.status == UpdateStatus.UPDATE_AVAILABLE:
            message = f"Nova versão disponível: {result.available_version}."
        elif result.status == UpdateStatus.INSTALLED_NEWER:
            message = (
                "A versão instalada é mais recente que a última versão publicada."
            )
        else:
            message = "O Finance está atualizado."
        self._update_page.set_status(message)

    @Slot(object)
    def _update_failed(self, _error: Exception) -> None:
        if self._update_page is not None:
            self._update_page.set_status(
                "Não foi possível consultar atualizações no momento.", error=True
            )

    @Slot()
    def _finish_update_check(self) -> None:
        if self._update_page is not None:
            self._update_page.set_update_check_running(False)
        if self._update_thread is not None:
            self._update_thread.deleteLater()
        self._update_thread = None
        self._update_worker = None
        self._update_page = None

    def _load_remote_information(self, page: AdministracaoPage) -> None:
        try:
            health = self._api_client.health()
            page.show_remote_information(health)
            page.set_status("Informações centrais atualizadas.")
        except RuntimeError as error:
            page.set_status(f"Falha ao consultar informações: {error}", error=True)

    def _open_historical_import(self, page: AdministracaoPage) -> None:
        if self._historical_import_service is None:
            page.set_status("Importação histórica indisponível neste ambiente.", error=True)
            return
        dialog = HistoricalImportDialog(page)
        dialog.controller = HistoricalImportController(
            dialog, self._historical_import_service
        )
        dialog.exec()

    def _load_remote_users(self, page: AdministracaoPage) -> None:
        try:
            page.show_users(self._api_client.list_users())
            page.set_status("Usuários atualizados.")
        except RuntimeError as error:
            page.set_status(str(error), error=True)

    def _create_remote_user(self, page: AdministracaoPage) -> None:
        dialog = UserDialog(
            page,
            allow_administrator=self._authenticated_role == "ADMINISTRADOR",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api_client.create_user(dialog.payload())
            self._load_remote_users(page)
            page.set_status("Usuário criado com sucesso.")
        except RuntimeError as error:
            page.set_status(f"Não foi possível criar o usuário: {error}", error=True)

    def _edit_remote_user(self, page: AdministracaoPage) -> None:
        user = page.selected_user()
        if user is None:
            page.set_status("Selecione um usuário para editar.", error=True)
            return
        if (
            self._authenticated_role == "GESTOR"
            and user.get("perfil") == "ADMINISTRADOR"
        ):
            page.set_status(
                "Gestores não podem administrar usuários Administrador.", error=True
            )
            return
        dialog = UserDialog(
            page, user=user,
            allow_administrator=self._authenticated_role == "ADMINISTRADOR",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._api_client.update_user(user["id"], dialog.payload())
            self._load_remote_users(page)
            page.set_status("Usuário atualizado com sucesso.")
        except RuntimeError as error:
            page.set_status(f"Não foi possível atualizar o usuário: {error}", error=True)

    def _toggle_remote_user(self, page: AdministracaoPage) -> None:
        user = page.selected_user()
        if user is None:
            page.set_status("Selecione um usuário para ativar ou inativar.", error=True)
            return
        if (
            self._authenticated_role == "GESTOR"
            and user.get("perfil") == "ADMINISTRADOR"
        ):
            page.set_status(
                "Gestores não podem administrar usuários Administrador.", error=True
            )
            return
        active = not user["ativo"]
        try:
            self._api_client.update_user(user["id"], {"ativo": active})
            self._load_remote_users(page)
            page.set_status(f"Usuário {'ativado' if active else 'inativado'} com sucesso.")
        except RuntimeError as error:
            page.set_status(f"Não foi possível alterar a situação do usuário: {error}", error=True)

    def _reset_remote_user_password(self, page: AdministracaoPage) -> None:
        user = page.selected_user()
        if user is None:
            page.set_status("Selecione um usuário para redefinir a senha.", error=True)
            return
        if (
            self._authenticated_role == "GESTOR"
            and user.get("perfil") == "ADMINISTRADOR"
        ):
            page.set_status(
                "Gestores não podem administrar usuários Administrador.",
                error=True,
            )
            return

        temporary_password, ok = QInputDialog.getText(
            page,
            "Redefinir senha",
            f"Informe a senha temporária para {user['username']}:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return

        confirmation, ok = QInputDialog.getText(
            page,
            "Confirmar senha temporária",
            "Confirme a senha temporária:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        if temporary_password != confirmation:
            page.set_status("As senhas temporárias não coincidem.", error=True)
            return

        try:
            validate_password(temporary_password)
            self._api_client.reset_user_password(user["id"], temporary_password)
            self._load_remote_users(page)
            page.set_status(
                "Senha temporária definida. O usuário deverá alterá-la no próximo acesso."
            )
        except (RuntimeError, ValueError) as error:
            page.set_status(f"Não foi possível redefinir a senha: {error}", error=True)

    def _load_remote_audit(self, page: AdministracaoPage) -> None:
        try:
            values = self._api_client.get("/api/v1/audit")
            page.show_remote_rows([(item["timestamp"], str(item.get("user_id") or "—"),
                                    item["action"], item.get("entity_type") or "—") for item in values])
            page.set_status("Auditoria atualizada (somente leitura).")
        except RuntimeError as error:
            page.set_status(str(error), error=True)

    def _load_ranking_parameters(self, page: AdministracaoPage) -> None:
        widget = page.ranking_parameters_widget
        try:
            values = self._api_client.get_ranking_parameters(widget.year.value())
            widget.show_parameters(values)
        except RuntimeError as error:
            widget.set_status(f"Não foi possível carregar: {error}", error=True)

    def _save_ranking_parameters(self, page: AdministracaoPage) -> None:
        widget = page.ranking_parameters_widget
        try:
            payload = widget.payload()
            values = self._api_client.save_ranking_parameters(
                widget.year.value(), payload
            )
            widget.show_parameters(values)
            widget.set_status(
                f"Parâmetros do Ranking de {widget.year.value()} salvos com sucesso."
            )
        except (RuntimeError, ValueError) as error:
            widget.set_status(f"Não foi possível salvar: {error}", error=True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._api_client is not None:
            self._api_client.logout()
            self._api_client.close()
        if self._boe_session is not None:
            self._boe_session.close()
        super().closeEvent(event)
