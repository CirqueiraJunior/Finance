from PySide6.QtWidgets import QPlainTextEdit
from app.gui.import_workflow_steps import ImportWorkflowSteps
from app.gui.import_workflow_panel import ImportWorkflowPanel
from app.widgets.wheel_guard import WheelBlockedComboBox, WheelBlockedSpinBox
from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.gui.formatters import format_currency, format_number, format_percentage
from app.models.budget_entry import BudgetEntry
from app.models.cashflow_entry import EXPENSE_CATEGORIES, CashflowCategory, CashflowType
from app.services.budget_service import BudgetVsActual, REVENUE_CATEGORIES
from app.services.cashflow_catalog_service import CashflowCatalogOption
from app.widgets import BRLCurrencyEdit, MonthComboBox
from app.widgets.year_combo import populate_year_combo, select_year


from PySide6.QtWidgets import QScrollArea

class BudgetImportProgressDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importação de Orçamento")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        self.title = QLabel("Processando importação...")
        self.title.setObjectName("sectionTitle")
        self.description = QLabel("Esta operação pode levar alguns instantes.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(self.title)
        layout.addWidget(self.description)
        layout.addWidget(self.progress)

    def reject(self) -> None:
        return


class BudgetDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, budget: BudgetEntry | None = None,
        *, catalog_options: tuple[CashflowCatalogOption, ...] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Orçamento" if budget else "Novo Orçamento")
        self.setMinimumWidth(430)
        layout = QFormLayout(self)
        self.year = WheelBlockedSpinBox()
        self.year.setRange(2000, 9999)
        self.year.setValue(budget.periodo_ano if budget else date.today().year)
        self.month = MonthComboBox()
        self.month.set_month(budget.periodo_mes if budget else date.today().month)
        self.entry_type = WheelBlockedComboBox()
        self.entry_type.addItem("Receita", CashflowType.REVENUE.value)
        self.entry_type.addItem("Despesa", CashflowType.EXPENSE.value)
        self.entry_type.setEnabled(False)
        self.category = WheelBlockedComboBox()
        self.description = WheelBlockedComboBox()
        options = [
            option for option in catalog_options
            if option.movement_type in {
                CashflowType.REVENUE.value, CashflowType.EXPENSE.value
            }
            and (budget is None or (
                option.category == budget.categoria
                and option.movement_type == budget.tipo
            ))
        ]
        if budget and budget.descricao and not any(
            option.description == budget.descricao
            and option.category == budget.categoria
            and option.movement_type == budget.tipo
            for option in options
        ):
            options.append(CashflowCatalogOption(
                budget.descricao, budget.categoria, budget.tipo
            ))
        self._catalog_options = tuple(options)
        self.description.addItem("Selecione a descrição...", None)
        for value in dict.fromkeys(option.description for option in self._catalog_options):
            self.description.addItem(value, value)
        self.budgeted_value = BRLCurrencyEdit()
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        layout.addRow("Ano", self.year)
        layout.addRow("Mês", self.month)
        layout.addRow("Descrição", self.description)
        layout.addRow("Categoria", self.category)
        layout.addRow("Tipo", self.entry_type)
        layout.addRow("Valor Orçado", self.budgeted_value)
        layout.addRow("Observação", self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.description.currentIndexChanged.connect(self.update_categories)
        self.category.currentIndexChanged.connect(self.update_type)
        self.update_categories()
        if budget:
            description_index = self.description.findData(budget.descricao)
            self.description.setCurrentIndex(description_index)
            category_index = self.category.findData(budget.categoria)
            self.category.setCurrentIndex(category_index)
            self.update_type()
            self.budgeted_value.set_decimal_value(budget.valor_orcado)
            self.notes.setPlainText(budget.observacao or "")
            for widget in (self.year, self.month, self.entry_type, self.category):
                widget.setEnabled(False)

    def update_categories(self) -> None:
        description = self.description.currentData()
        self.category.clear()
        matches = [option for option in self._catalog_options
                   if option.description == description]
        if not matches:
            self.category.addItem("Selecione a categoria...", None)
        elif len(matches) > 1:
            self.category.addItem("Selecione a categoria...", None)
        for option in matches:
            self.category.addItem(self.category_label(option.category), option.category)
        self.update_type()

    def update_type(self) -> None:
        description = self.description.currentData()
        category = self.category.currentData()
        option = next((item for item in self._catalog_options
                       if item.description == description and item.category == category), None)
        index = self.entry_type.findData(option.movement_type if option else None)
        self.entry_type.setCurrentIndex(index)

    def _accept_if_valid(self) -> None:
        if self.description.currentData() is None:
            QMessageBox.warning(self, "Descrição obrigatória", "Selecione a Descrição.")
            return
        if self.category.currentData() is None or self.entry_type.currentData() is None:
            QMessageBox.warning(self, "Catálogo inválido", "Selecione uma combinação válida de Descrição e Categoria.")
            return
        self.accept()

    def create_values(self) -> tuple[int, int, str, str, str, str, str]:
        return (
            self.year.value(), self.month.month(), self.entry_type.currentData(),
            self.category.currentData(), self.description.currentData(), self.normalized_value(),
            self.notes.toPlainText(),
        )

    def update_values(self) -> tuple[str, str, str]:
        return self.description.currentData(), self.normalized_value(), self.notes.toPlainText()

    def normalized_value(self) -> str:
        return str(self.budgeted_value.decimal_value())

    @staticmethod
    def category_label(value: str) -> str:
        return value.replace("_", " ").title()

    @staticmethod
    def format_decimal(value: Decimal) -> str:
        return format_number(value)


class OrcamentoPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        self._import_available = False
        self._import_permitted = True
        self.budget_scroll_area = QScrollArea(self)
        self.budget_scroll_area.setObjectName("budgetScrollArea")
        self.budget_scroll_area.setWidgetResizable(True)
        self.budget_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.budget_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.budget_scroll_area.setStyleSheet(
            "QScrollArea#budgetScrollArea { background: transparent; border: none; }"
        )
        self.budget_content = QWidget()
        self.budget_content.setObjectName("budgetScrollContent")
        layout = QVBoxLayout(self.budget_content)
        layout.setContentsMargins(32, 2, 32, 12)
        layout.setSpacing(6)
        title = QLabel("Orçado x Realizado")
        title.setObjectName("pageTitle")
        description = QLabel("Orçamento mensal ou anual comparado ao Fluxo de Caixa.")
        description.setObjectName("pageDescription")

        filter_panel = QWidget()
        filter_panel.setObjectName("dashboardFilterBar")
        filters = QHBoxLayout(filter_panel)
        self.year_filter = WheelBlockedComboBox()
        self.year_filter.setEnabled(False)
        self.month_filter = MonthComboBox(include_all=True)
        self.filter_button = QPushButton("Aplicar filtro")
        self.filter_button.setEnabled(False)
        self.filter_button.setProperty("buttonRole", "toolbar")
        self.new_button = QPushButton("Novo Orçamento")
        self.new_button.setProperty("buttonRole", "primary")
        self.new_button.setObjectName("primaryButton")
        self.edit_button = QPushButton("Editar Orçamento")
        self.edit_button.setProperty("buttonRole", "secondary")
        filters.addWidget(QLabel("Ano"))
        filters.addWidget(self.year_filter)
        filters.addWidget(QLabel("Mês"))
        filters.addWidget(self.month_filter)
        filters.addWidget(self.filter_button)
        filters.addStretch()
        filters.addWidget(self.edit_button)
        filters.addWidget(self.new_button)

        import_area = QWidget()
        import_area.setObjectName("sectionCard")
        import_layout = QVBoxLayout(import_area)
        self.import_summary = QLabel(
            "Selecione um arquivo para validar a importação de Orçamento."
        )
        self.import_summary.setWordWrap(True)
        self.import_preview = QTableWidget(0, 7)
        self.import_preview.setHorizontalHeaderLabels(
            ["Linha", "Ano", "Mês", "Tipo", "Categoria", "Valor", "Origem"]
        )
        self.import_preview.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.import_issues = QLabel()
        self.import_issues.setWordWrap(True)

        self.import_steps = ImportWorkflowSteps(
            steps=(
                "Selecionar",
                "Validar",
                "Comparar e autorizar",
                "Importar",
            )
        )

        validation_column = QVBoxLayout()
        validation_title = QLabel("Resultado da valida\u00e7\u00e3o")
        validation_title.setObjectName("sectionTitle")
        validation_column.addWidget(validation_title)

        self.import_issues.setMinimumHeight(150)
        self.import_issues.setStyleSheet(
            "background-color: white;"
            "border: 1px solid #CAD6E3;"
            "border-radius: 7px;"
            "padding: 10px;"
        )
        validation_column.addWidget(self.import_issues)

        result_column = QVBoxLayout()
        result_title = QLabel("Resultado da importa\u00e7\u00e3o")
        result_title.setObjectName("sectionTitle")
        result_column.addWidget(result_title)

        self.import_result = QPlainTextEdit()
        self.import_result.setReadOnly(True)
        self.import_result.setFixedHeight(150)
        self.import_result.setPlaceholderText(
            "Nenhuma importa\u00e7\u00e3o executada nesta sess\u00e3o."
        )
        result_column.addWidget(self.import_result)

        results = QHBoxLayout()
        results.setSpacing(12)
        results.addLayout(validation_column, 1)
        results.addLayout(result_column, 1)

        self.import_panel = ImportWorkflowPanel(
            steps=self.import_steps,
            file_display=self.import_summary,
            results_layout=results,
            preview=self.import_preview,
        )
        import_layout.addWidget(self.import_panel)

        cards = QHBoxLayout()
        self.budgeted_revenue = self._card("Receita Orçada", cards)
        self.actual_revenue = self._card("Receita Realizada", cards)
        self.budgeted_expense = self._card("Despesa Orçada", cards)
        self.actual_expense = self._card("Despesa Realizada", cards)
        self.revenue_result = self._card("Resultado Receita", cards)
        self.expense_result = self._card("Resultado Despesas", cards)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Tipo", "Descrição", "Categoria", "Orçado", "Realizado", "Desvio", "Desvio %", "Observação"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellClicked.connect(self._toggle_budget_category)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.status = QLabel("Orçamento pronto.")
        self.status.setObjectName("operationStatus")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(filter_panel)
        layout.addLayout(cards)
        self.table.setMinimumHeight(280)
        layout.addWidget(self.table)
        layout.addWidget(import_area)
        layout.addWidget(self.status)
        self.budget_scroll_area.setWidget(self.budget_content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.budget_scroll_area)

    def set_import_available(self, available: bool) -> None:
        self._import_available = bool(available)
        self._apply_import_access()
        if not available:
            self.import_summary.setText(
                "Importação central disponível somente no modo servidor."
            )

    def set_import_permission(self, permitted: bool) -> None:
        self._import_permitted = bool(permitted)
        self._apply_import_access()

    @property
    def import_workflow_allowed(self) -> bool:
        return self._import_available and self._import_permitted

    def _apply_import_access(self) -> None:
        for stage in range(1, len(self.import_steps.buttons) + 1):
            self.import_steps.set_stage_enabled(stage, False)
        self.import_steps.set_stage_enabled(
            1, self.import_workflow_allowed
        )

    def show_import_validation(self, value: dict) -> None:
        metadata = value.get("metadata", {})
        totals = value.get("totals", {})
        self.import_summary.setText(
            f"Arquivo: {metadata.get('file_name', '—')} | "
            f"Tipo: {metadata.get('detected_type', '—')} | "
            f"Ano: {metadata.get('year') or '—'} | "
            f"Registros: {totals.get('rows', 0)} | "
            f"Total: {format_currency(totals.get('value', 0))}"
        )
        rows = value.get("preview", [])
        self.import_preview.setRowCount(min(len(rows), 500))
        for index, row in enumerate(rows[:500]):
            values = (
                row.get("line", "—"), row.get("year", "—"),
                row.get("month", "—"), row.get("entry_type", "—"),
                row.get("category", "—"), format_currency(row.get("value", 0)),
                row.get("source_label", "—"),
            )
            for column, text in enumerate(values):
                self.import_preview.setItem(
                    index, column, QTableWidgetItem(str(text))
                )
        messages = [f"ERRO: {item}" for item in value.get("errors", [])]
        messages.extend(
            f"AVISO: {item}" for item in value.get("warnings", [])
        )
        self.import_issues.setText(
            "\n".join(messages) or "Nenhuma inconsistência."
        )
        self.import_preview.resizeColumnsToContents()
        self.set_status(
            "Arquivo validado e pronto para importação."
            if value.get("can_import") else
            "Arquivo com inconsistências bloqueantes.",
            error=not value.get("can_import"),
        )

    def show_import_result(self, value: dict) -> None:
        result_text = (
            f"Importação concluída: {value.get('imported', 0)} registros | "
            f"Ano: {value.get('year') or '—'} | "
            f"Total: {format_currency(value.get('total', 0))}"
        )
        self.import_summary.setText(result_text)
        self.import_result.setPlainText(result_text)
        self.set_status("Orçamento importado com sucesso.")

    @staticmethod
    def _card(title: str, layout: QHBoxLayout) -> QLabel:
        card = QWidget()
        card.setObjectName("summaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 6, 10, 6)
        card_layout.setSpacing(2)
        label = QLabel(title)
        label.setObjectName("summaryLabel")
        value = QLabel("R$ 0,00")
        value.setObjectName("summaryValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        layout.addWidget(card, 1)
        return value

    def selected_period(self) -> tuple[int, int | None]:
        month = self.month_filter.currentData()
        return self.year_filter.currentData(), month or None

    def set_period(self, year: int, month: int | None) -> None:
        select_year(self.year_filter, year)
        self.month_filter.set_month(month)

    def set_available_years(self, years: list[int]) -> None:
        selected = populate_year_combo(self.year_filter, years)
        self.filter_button.setEnabled(selected is not None)
        if selected is None:
            self.set_status("Nenhum ano de orçamento disponível.", error=True)

    def show_result(
        self, result: BudgetVsActual, budgets: list[BudgetEntry]
    ) -> None:
        # Financial actuals come from comparison.details, never from budget.
        # Group budgets only to associate an editable ID and optional notes.
        budget_lookup = {}
        for budget in budgets:
            key = (
                budget.tipo,
                budget.categoria,
                (budget.descricao or "Sem descricao").strip().casefold(),
            )
            budget_lookup.setdefault(key, []).append(budget)

        self._budget_children = {}
        self.table.setRowCount(0)

        for comparison in result.comparisons:
            details = sorted(
                comparison.details,
                key=lambda detail: (
                    detail.unmatched,
                    detail.description.casefold(),
                ),
            )
            parent_row = self.table.rowCount()
            self.table.insertRow(parent_row)
            self._budget_children[parent_row] = []

            label = (
                f"+ Detalhar lançamentos ({len(details)})"
                if details else "Sem detalhamento"
            )
            values = [
                comparison.entry_type,
                label,
                BudgetDialog.category_label(comparison.category),
                self.currency(comparison.budgeted),
                self.currency(comparison.actual),
                self.currency(comparison.absolute_variance),
                format_percentage(comparison.percentage_variance),
                "Resumo por categoria",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, None)
                if column == 1 and details:
                    item.setToolTip("Clique para expandir ou recolher.")
                self.table.setItem(parent_row, column, item)

            detail_budgeted = Decimal("0")
            detail_actual = Decimal("0")

            for detail in details:
                detail_budgeted += detail.budgeted
                detail_actual += detail.actual

                identity = (
                    comparison.entry_type,
                    comparison.category,
                    detail.description.strip().casefold(),
                )
                matched_budgets = budget_lookup.get(identity, ())
                budget_id = (
                    matched_budgets[0].id
                    if len(matched_budgets) == 1 and not detail.unmatched
                    else None
                )

                detail_row = self.table.rowCount()
                self.table.insertRow(detail_row)
                self._budget_children[parent_row].append(detail_row)

                notes = (
                    "Realizado sem orcamento correspondente"
                    if detail.unmatched else
                    (
                        matched_budgets[0].observacao or ""
                        if len(matched_budgets) == 1 else
                        "Valores agrupados por descricao"
                    )
                )
                prefix = "    [SEM ORCAMENTO] " if detail.unmatched else "    "
                values = [
                    comparison.entry_type,
                    prefix + detail.description,
                    BudgetDialog.category_label(comparison.category),
                    self.currency(detail.budgeted),
                    self.currency(detail.actual),
                    self.currency(detail.variance),
                    format_percentage((detail.variance / detail.budgeted * Decimal("100")).quantize(Decimal("0.0001"))) if detail.budgeted > 0 else "N/A",
                    notes or "?",
                ]
                for column, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if column == 0:
                        item.setData(Qt.ItemDataRole.UserRole, budget_id)
                    if detail.unmatched:
                        item.setToolTip(
                            "Lancamento do Financeiro sem correspondencia "
                            "com uma descricao do Orcamento."
                        )
                    self.table.setItem(detail_row, column, item)
                self.table.setRowHidden(detail_row, True)

            if (
                detail_budgeted != comparison.budgeted
                or detail_actual != comparison.actual
            ):
                raise ValueError(
                    "Detalhamento nao corresponde ao total da categoria."
                )

        summary = result.summary
        self.budgeted_revenue.setText(self.currency(summary.budgeted_revenue))
        self.actual_revenue.setText(self.currency(summary.actual_revenue))
        self.budgeted_expense.setText(self.currency(summary.budgeted_expense))
        self.actual_expense.setText(self.currency(summary.actual_expense))
        self.revenue_result.setText(self.currency(summary.revenue_result))
        self.expense_result.setText(self.currency(summary.expense_result))
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(1, 280)
        self.table.setMinimumHeight(350)
        self.table.setColumnWidth(2, 150)

    def _toggle_budget_category(self, row: int, column: int) -> None:
        children = getattr(self, "_budget_children", {}).get(row)
        if not children:
            return

        expanding = self.table.isRowHidden(children[0])
        for child in children:
            self.table.setRowHidden(child, not expanding)

        label = self.table.item(row, 1)
        if label is not None:
            action = "-" if expanding else "+"
            label.setText(
                f"{action} Detalhar lançamentos ({len(children)})"
            )

    def selected_budget_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    @staticmethod
    def currency(value: Decimal) -> str:
        return format_currency(value)
