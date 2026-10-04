from datetime import date
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import CashflowDomainError, InvestmentDomainError
from app.gui.pages.financeiro import CashflowEntryDialog, FinanceiroPage
from app.gui.processing import OperationWorker, ProcessingDialog
from app.models.cashflow_entry import CashflowType
from app.models.investment_movement import InvestmentMovementType
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository
from app.repositories.investment_repository import InvestmentRepository
from app.repositories.financial_balance_repository import FinancialBalanceRepository
from app.services.cashflow_catalog_service import CashflowCatalogService
from app.services.cashflow_service import CashflowService
from app.services.financial_flow_service import FinancialFlowService
from app.services.financial_balance_service import FinancialBalanceService
from app.services.investment_service import InvestmentService
from app.widgets.year_combo import AvailableYearsLoader


class CashflowController(QObject):
    import_completed = Signal()

    def __init__(
        self, view: FinanceiroPage, service: CashflowService,
        investment_service: InvestmentService | None = None,
        financial_flow=None,
        catalog_service=None,
        import_service=None,
    ) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.investment_service = investment_service or InvestmentService(
            InvestmentRepository(service.repository.session)
        )
        self.financial_flow = financial_flow or FinancialFlowService(service, self.investment_service)
        self.financial_balance = (
            FinancialBalanceService(
                FinancialBalanceRepository(service.repository.session),
                self.financial_flow,
            )
            if financial_flow is None
            else None
        )
        self.catalog_service = catalog_service or CashflowCatalogService(
            CashflowCatalogRepository(service.repository.session)
        )
        self.import_service = import_service
        self.import_file_path: str | None = None
        self._import_validated = False
        self._import_thread: QThread | None = None
        self._import_worker: OperationWorker | None = None
        self._import_dialog: ProcessingDialog | None = None
        self._operation_thread: QThread | None = None
        self._operation_worker: OperationWorker | None = None
        self._operation_dialog: ProcessingDialog | None = None
        self.view.filter_button.clicked.connect(self.refresh_entries)
        self.view.new_entry_button.clicked.connect(self.open_new_entry_dialog)
        self.view.select_import_button.clicked.connect(self.select_import_file)
        self.view.validate_import_button.clicked.connect(self.validate_import_file)
        self.view.confirm_import_button.clicked.connect(self.import_validated_file)
        self.view.select_import_button.setEnabled(import_service is not None)
        self._years_loader = AvailableYearsLoader(
            self,
            self.financial_flow.available_years,
            self.view.set_available_years,
            lambda error: self.view.set_status(
                f"Falha ao carregar anos disponíveis: {error}", error=True
            ),
        )
        self._years_loader.load(
            remote=getattr(self.financial_flow, "api", None) is not None
        )
        # A MainWindow possui o ProcessingDialog global de pós-login.
        # Evita abrir um segundo diálogo "Financeiro" durante a construção.

    def _run_operation(
        self,
        *,
        window_title: str,
        title: str,
        description: str,
        operation,
        succeeded,
        error_prefix: str,
    ) -> None:
        repository = getattr(self.service, "repository", None)
        local_session = getattr(repository, "session", None)

        # Sessões SQLAlchemy locais não podem atravessar threads.
        # O Finance em produção usa serviços remotos; esses continuam
        # executando em QThread com ProcessingDialog.
        if isinstance(local_session, Session):
            try:
                succeeded(operation())
            except Exception as error:
                try:
                    local_session.rollback()
                except Exception:
                    pass
                self.view.set_status(
                    f"{error_prefix}: {error}",
                    error=True,
                )
            return

        if (
            self._operation_thread is not None
            and self._operation_thread.isRunning()
        ):
            return

        self._operation_dialog = ProcessingDialog(
            self.view,
            window_title=window_title,
            title=title,
            description=description,
        )
        self._operation_thread = QThread(self)
        self._operation_worker = OperationWorker(operation)
        self._operation_worker.moveToThread(self._operation_thread)

        def failed(error: Exception) -> None:
            try:
                self.service.repository.session.rollback()
            except Exception:
                pass
            self.view.set_status(
                f"{error_prefix}: {error}",
                error=True,
            )

        def finished() -> None:
            if self._operation_dialog is not None:
                self._operation_dialog.accept()
                self._operation_dialog.deleteLater()
                self._operation_dialog = None

            if self._operation_thread is not None:
                self._operation_thread.deleteLater()

            self._operation_thread = None
            self._operation_worker = None

        self._operation_thread.started.connect(
            self._operation_worker.run
        )
        self._operation_worker.succeeded.connect(succeeded)
        self._operation_worker.failed.connect(failed)
        self._operation_worker.finished.connect(
            self._operation_thread.quit
        )
        self._operation_worker.finished.connect(
            self._operation_worker.deleteLater
        )
        self._operation_thread.finished.connect(finished)

        self._operation_dialog.show()
        self._operation_thread.start()

    def select_import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.view, "Selecionar arquivo Financeiro", "",
            "Planilhas Excel (*.xlsx *.xlsm)",
        )
        if not path:
            return
        self.import_file_path = path
        self._import_validated = False
        self.view.selected_import_file.setText(Path(path).name)
        self.view.validate_import_button.setEnabled(True)
        self.view.confirm_import_button.setEnabled(False)
        self.view.import_issues.setText("Arquivo selecionado. Clique em Validar.")
        self.view.import_preview.setRowCount(0)

    def validate_import_file(self) -> None:
        if not self.import_service or not self.import_file_path:
            return

        self.view.confirm_import_button.setEnabled(False)
        selected_file = self.import_file_path

        def succeeded(validation: dict) -> None:
            self.view.show_import_validation(validation)
            self._import_validated = bool(
                validation.get("can_import")
            )
            self.view.confirm_import_button.setEnabled(
                self._import_validated
            )

        self._run_operation(
            window_title="Validacao Financeiro",
            title="Validando arquivo...",
            description=(
                "Aguarde enquanto o arquivo Financeiro "
                "e analisado."
            ),
            operation=lambda: self.import_service.validate_import(
                selected_file
            ),
            succeeded=succeeded,
            error_prefix="Falha ao validar arquivo Financeiro",
        )

    def import_validated_file(self) -> None:
        if not self.import_service or not self.import_file_path or not self._import_validated or (
            self._import_thread is not None and self._import_thread.isRunning()
        ):
            return
        self.view.select_import_button.setEnabled(False)
        self.view.validate_import_button.setEnabled(False)
        self.view.confirm_import_button.setEnabled(False)
        self._import_dialog = ProcessingDialog(
            self.view, window_title="Importação Financeiro"
        )
        self._import_dialog.show()
        self._import_thread = QThread(self)
        selected_file = self.import_file_path
        self._import_worker = OperationWorker(
            lambda: self.import_service.import_file(selected_file)
        )
        self._import_worker.moveToThread(self._import_thread)
        self._import_thread.started.connect(self._import_worker.run)
        self._import_worker.succeeded.connect(self._import_succeeded)
        self._import_worker.failed.connect(self._import_failed)
        self._import_worker.finished.connect(self._import_thread.quit)
        self._import_worker.finished.connect(self._import_worker.deleteLater)
        self._import_thread.finished.connect(self._import_finished)
        self._import_thread.start()

    @Slot(object)
    def _import_succeeded(self, result: dict) -> None:
        self.view.show_import_result(result)
        self.import_file_path = None
        self._import_validated = False
        self.view.selected_import_file.setText("Nenhum arquivo selecionado.")
        if self.view.selected_period()[0] is not None:
            self.refresh_entries()
        self.import_completed.emit()

    @Slot(object)
    def _import_failed(self, error: Exception) -> None:
        self.view.set_status(f"Falha ao importar Financeiro: {error}", error=True)

    @Slot()
    def _import_finished(self) -> None:
        if self._import_dialog is not None:
            self._import_dialog.accept()
            self._import_dialog.deleteLater()
            self._import_dialog = None
        if self._import_thread is not None:
            self._import_thread.deleteLater()
        self._import_thread = None
        self._import_worker = None
        self.view.select_import_button.setEnabled(True)
        self.view.validate_import_button.setEnabled(self.import_file_path is not None)
        self.view.confirm_import_button.setEnabled(
            self.import_file_path is not None and self._import_validated
        )

    def refresh_entries(self) -> None:
        year, month = self.view.selected_period()

        def operation():
            entries = self.financial_flow.list_by_period(
                year,
                month,
            )
            summary = self.financial_flow.get_summary(
                year,
                month,
            )

            if self.financial_balance is not None:
                position = self.financial_balance.position(
                    year,
                    month,
                )
            elif hasattr(self.financial_flow, "get_position"):
                position = self.financial_flow.get_position(
                    year,
                    month,
                )
            else:
                position = None

            return entries, summary, position

        def succeeded(result) -> None:
            entries, summary, position = result
            self.view.show_financial_flow(
                entries,
                summary,
                position,
            )

        self._run_operation(
            window_title="Financeiro",
            title="Carregando informações...",
            description=(
                f"Aguarde enquanto o período "
                f"{month:02d}/{year} é processado."
            ),
            operation=operation,
            succeeded=succeeded,
            error_prefix="Falha ao carregar lançamentos",
        )

    def open_new_entry_dialog(self) -> None:
        year, month = self.view.selected_period()
        year = year or date.today().year
        dialog = CashflowEntryDialog(
            self.view,
            self.catalog_service.list_options(),
            period_year=year,
            period_month=month,
        )

        def update_balance() -> None:
            dialog.set_available_balance(
                self.investment_service.get_applied_balance(
                    dialog.movement_date()
                )
            )

        dialog.category.currentIndexChanged.connect(update_balance)
        dialog.year_input.valueChanged.connect(update_balance)
        dialog.month_input.currentIndexChanged.connect(update_balance)
        update_balance()

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        (
            entry_type,
            entry_date,
            description,
            category,
            value,
            notes,
            boe,
        ) = dialog.values()

        year = entry_date.year
        month = entry_date.month

        def operation():
            if entry_type == CashflowType.REVENUE.value:
                self.service.create_indirect_revenue(
                    year=year,
                    month=month,
                    entry_date=entry_date,
                    description=description,
                    value=value,
                    notes=notes,
                    boe=boe,
                )
                message = "Receita Indireta cadastrada com sucesso."

            elif entry_type == CashflowType.EXPENSE.value:
                self.service.create_expense(
                    year=year,
                    month=month,
                    entry_date=entry_date,
                    description=description,
                    category=category,
                    value=value,
                    notes=notes,
                    boe=boe,
                )
                message = "Despesa cadastrada com sucesso."

            elif entry_type == InvestmentMovementType.APPLICATION.value:
                self.financial_flow.create_application(
                    movement_date=entry_date,
                    description=description,
                    value=value,
                    notes=notes,
                )
                message = "Aplicação cadastrada com sucesso."

            else:
                self.financial_flow.create_redemption(
                    movement_date=entry_date,
                    description=description,
                    value=value,
                    notes=notes,
                )
                message = "Resgate cadastrado com sucesso."

            entries = self.financial_flow.list_by_period(
                year,
                month,
            )
            summary = self.financial_flow.get_summary(
                year,
                month,
            )

            if self.financial_balance is not None:
                position = self.financial_balance.position(
                    year,
                    month,
                )
            elif hasattr(self.financial_flow, "get_position"):
                position = self.financial_flow.get_position(
                    year,
                    month,
                )
            else:
                position = None

            return message, entries, summary, position

        def succeeded(result) -> None:
            message, entries, summary, position = result
            self.view.show_financial_flow(
                entries,
                summary,
                position,
            )
            self.view.set_status(message)

        self._run_operation(
            window_title="Financeiro",
            title="Salvando lançamento...",
            description=(
                "Aguarde enquanto o lançamento é processado."
            ),
            operation=operation,
            succeeded=succeeded,
            error_prefix="Falha ao salvar lançamento",
        )

    def open_indirect_revenue_dialog(self) -> None:
        self.open_new_entry_dialog()
