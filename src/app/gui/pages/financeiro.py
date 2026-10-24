from app.widgets.wheel_guard import WheelBlockedComboBox, WheelBlockedDateEdit, WheelBlockedSpinBox
from datetime import date
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QMessageBox, QRadioButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.gui.formatters import format_currency
from app.models.cashflow_entry import EXPENSE_CATEGORIES, CashflowCategory, CashflowType
from app.models.investment_movement import InvestmentMovementType
from app.services.cashflow_catalog_service import CashflowCatalogOption
from app.services.financial_flow_service import FinancialFlowSummary, FinancialMovement
from app.widgets import BRLCurrencyEdit, MonthComboBox
from app.widgets.year_combo import populate_year_combo, select_year


MonetaryLineEdit = BRLCurrencyEdit


class CashflowEntryDialog(QDialog):
    """Novo lançamento alinhado à planilha oficial.

    Em modo catálogo:
    - o período é somente mês/ano;
    - Descrição filtra as Categorias válidas;
    - Categoria fica em branco quando houver mais de uma opção;
    - Tipo é derivado da combinação Descrição + Categoria e exibido por radio;
    - BOE é escolhido por radio Sim/Não.
    """

    TYPE_OPTIONS = (
        ("Receita", CashflowType.REVENUE.value),
        ("Despesa", CashflowType.EXPENSE.value),
        ("Aplicação", InvestmentMovementType.APPLICATION.value),
        ("Resgate", InvestmentMovementType.REDEMPTION.value),
    )

    def __init__(
        self,
        parent: QWidget | None = None,
        catalog_options: tuple[CashflowCatalogOption, ...] | None = None,
        *,
        period_year: int | None = None,
        period_month: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Novo Lançamento")
        self.setMinimumWidth(500)
        self._catalog_options = catalog_options
        self._catalog_mode = catalog_options is not None
        today = date.today()
        self._period_year = period_year or today.year
        self._period_month = period_month or today.month

        layout = QFormLayout(self)

        # Mantido como estado interno para compatibilidade dos controllers/testes antigos.
        self.entry_type = WheelBlockedComboBox()
        for label, value in self.TYPE_OPTIONS:
            self.entry_type.addItem(label, value)

        self.entry_date = WheelBlockedDateEdit(QDate.currentDate())
        self.entry_date.setCalendarPopup(True)
        self.entry_date.setDisplayFormat("dd/MM/yyyy")

        self.description = WheelBlockedComboBox() if self._catalog_mode else QLineEdit()
        self.category = WheelBlockedComboBox()
        self.value = BRLCurrencyEdit()
        self.value.setPlaceholderText("R$ 0,00")
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        self.available_balance = QLabel("Saldo aplicado disponível: R$ 0,00")

        # Tipo por botões de seleção, derivado do catálogo.
        self.type_widget = QWidget()
        type_layout = QHBoxLayout(self.type_widget)
        type_layout.setContentsMargins(0, 0, 0, 0)
        self.type_group = QButtonGroup(self)
        self.type_radios: dict[str, QRadioButton] = {}
        for label, movement_type in self.TYPE_OPTIONS:
            radio = QRadioButton(label)
            # Indicadores derivados do catálogo: aparência ativa, sem permitir
            # que o usuário force um Tipo incompatível com Descrição/Categoria.
            radio.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            radio.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self.type_group.addButton(radio)
            self.type_radios[movement_type] = radio
            type_layout.addWidget(radio)
        type_layout.addStretch()

        # BOE por botões de seleção.
        self.boe_widget = QWidget()
        boe_layout = QHBoxLayout(self.boe_widget)
        boe_layout.setContentsMargins(0, 0, 0, 0)
        self.boe_group = QButtonGroup(self)
        self.boe_yes = QRadioButton("Sim")
        self.boe_no = QRadioButton("Não")
        self.boe_group.addButton(self.boe_yes)
        self.boe_group.addButton(self.boe_no)
        # Sem seleção inicial para evitar assumir BOE=Não pelo usuário.
        boe_layout.addWidget(self.boe_yes)
        boe_layout.addWidget(self.boe_no)
        boe_layout.addStretch()

        if self._catalog_mode:
            self.year_input = WheelBlockedSpinBox()
            self.year_input.setRange(2000, 9999)
            self.year_input.setValue(self._period_year)
            self.month_input = MonthComboBox()
            self.month_input.set_month(self._period_month)
            layout.addRow("Ano", self.year_input)
            layout.addRow("Mês", self.month_input)
            layout.addRow("Descrição", self.description)
            self.category_label = QLabel("Categoria")
            layout.addRow(self.category_label, self.category)
            layout.addRow("Tipo", self.type_widget)
            layout.addRow("BOE", self.boe_widget)

            self.description.addItem("Selecione a descrição...", None)
            for description in dict.fromkeys(
                option.description for option in self._catalog_options or ()
            ):
                self.description.addItem(description, description)

            self.description.currentIndexChanged.connect(self._update_from_description)
            self.category.currentIndexChanged.connect(self._update_type_from_category)
            self.entry_type.setVisible(False)
            self.entry_date.setVisible(False)
            self._update_from_description()

            layout.addRow("Valor", self.value)
            layout.addRow("Observação", self.notes)
            layout.addRow(self.available_balance)
        else:
            # Compatibilidade com testes/uso legado. A GUI operacional usa modo catálogo.
            layout.addRow("Tipo", self.entry_type)
            layout.addRow("Data", self.entry_date)
            layout.addRow("Descrição", self.description)
            self.category_label = QLabel("Categoria")
            layout.addRow(self.category_label, self.category)
            layout.addRow("Valor", self.value)
            layout.addRow("Observação", self.notes)
            layout.addRow(self.available_balance)
            self.type_widget.setVisible(False)
            self.boe_widget.setVisible(False)
            self.entry_type.currentIndexChanged.connect(self.update_fields)
            self.update_fields()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _update_from_description(self) -> None:
        if not self._catalog_mode:
            return
        description = self.description.currentData()
        if description is None:
            self.category.clear()
            self.category.addItem("Selecione a categoria...", None)
            self._update_type_from_category()
            return
        matches = [
            option for option in self._catalog_options or ()
            if option.description == description
        ]

        self.category.blockSignals(True)
        self.category.clear()
        if len(matches) > 1:
            self.category.addItem("Selecione a categoria...", None)
        for option in matches:
            self.category.addItem(self.category_text(option.category), option.category)
        if len(matches) == 1:
            self.category.setCurrentIndex(0)
        else:
            self.category.setCurrentIndex(0)
        self.category.blockSignals(False)
        self._update_type_from_category()

    def _clear_type_selection(self) -> None:
        self.type_group.setExclusive(False)
        for radio in self.type_radios.values():
            radio.setChecked(False)
        self.type_group.setExclusive(True)

    def _update_type_from_category(self) -> None:
        if not self._catalog_mode:
            return
        description = self.description.currentData()
        category = self.category.currentData()
        option = next(
            (
                item for item in self._catalog_options or ()
                if item.description == description and item.category == category
            ),
            None,
        )
        movement_type = option.movement_type if option else ""

        self._clear_type_selection()
        if movement_type in self.type_radios:
            self.type_radios[movement_type].setChecked(True)

        index = self.entry_type.findData(movement_type)
        self.entry_type.blockSignals(True)
        self.entry_type.setCurrentIndex(index if index >= 0 else -1)
        self.entry_type.blockSignals(False)

        is_redemption = movement_type == InvestmentMovementType.REDEMPTION.value
        self.available_balance.setVisible(is_redemption)

        # BOE só é aplicável a Receita/Despesa. Aplicação/Resgate ficam como Não.
        boe_enabled = movement_type in {
            CashflowType.REVENUE.value,
            CashflowType.EXPENSE.value,
        }
        self.boe_yes.setEnabled(boe_enabled)
        self.boe_no.setEnabled(boe_enabled)
        # Receita/Despesa exigem escolha explícita de BOE para evitar assumir "Não".
        self.boe_group.setExclusive(False)
        self.boe_yes.setChecked(False)
        self.boe_no.setChecked(False)
        self.boe_group.setExclusive(True)
        if movement_type in {
            InvestmentMovementType.APPLICATION.value,
            InvestmentMovementType.REDEMPTION.value,
        }:
            self.boe_no.setChecked(True)

    def _accept_if_valid(self) -> None:
        if self._catalog_mode:
            if self.description.currentData() is None:
                QMessageBox.warning(
                    self,
                    "Descrição obrigatória",
                    "Informe a Descrição.",
                )
                return
            if self.category.currentData() is None:
                QMessageBox.warning(
                    self,
                    "Categoria obrigatória",
                    "Informe a Categoria.",
                )
                return
            if self.entry_type.currentData() is None:
                QMessageBox.warning(
                    self,
                    "Tipo obrigatório",
                    "Informe o Tipo.",
                )
                return
            movement_type = self.entry_type.currentData()
            if movement_type in {
                CashflowType.REVENUE.value,
                CashflowType.EXPENSE.value,
            } and not (self.boe_yes.isChecked() or self.boe_no.isChecked()):
                QMessageBox.warning(
                    self,
                    "BOE obrigatório",
                    "Informe se o lançamento é BOE: Sim ou Não.",
                )
                return

        value_text = self.value.text().strip()
        if not value_text:
            QMessageBox.warning(
                self, "Valor obrigatório", "Informe um valor maior que zero."
            )
            return
        try:
            numeric_value = self.value.decimal_value()
        except InvalidOperation:
            QMessageBox.warning(
                self, "Valor inválido", "Informe um valor maior que zero."
            )
            return
        if numeric_value <= 0:
            QMessageBox.warning(
                self,
                "Valor inválido",
                "Informe um valor maior que zero.",
            )
            return

        self.accept()

    def update_fields(self) -> None:
        """Comportamento legado usado por testes anteriores."""
        entry_type = self.entry_type.currentData()
        uses_category = entry_type in {CashflowType.REVENUE.value, CashflowType.EXPENSE.value}
        self.category.setVisible(uses_category)
        self.category_label.setVisible(uses_category)
        self.available_balance.setVisible(entry_type == InvestmentMovementType.REDEMPTION.value)
        self.category.clear()
        if entry_type == CashflowType.REVENUE.value:
            self.category.addItem("Receita Indireta", CashflowCategory.INDIRECT_REVENUE.value)
        elif entry_type == CashflowType.EXPENSE.value:
            for category in EXPENSE_CATEGORIES:
                self.category.addItem(self.category_text(category.value), category.value)

    def set_available_balance(self, value: Decimal) -> None:
        self.available_balance.setText(
            f"Saldo aplicado disponível: {FinanceiroPage.format_currency(value)}"
        )

    def movement_date(self) -> date:
        if self._catalog_mode:
            # O modelo oficial usa somente mês/ano. O primeiro dia é apenas
            # representação técnica interna para manter compatibilidade do schema.
            return date(self.year_input.value(), self.month_input.currentData(), 1)
        return self.entry_date.date().toPython()

    def values(self) -> tuple[str, date, str, str | None, str, str, bool]:
        description = (
            self.description.currentData()
            if isinstance(self.description, QComboBox)
            else self.description.text()
        )
        return (
            self.entry_type.currentData(),
            self.movement_date(),
            description,
            self.category.currentData(),
            str(self.value.decimal_value()),
            self.notes.toPlainText(),
            self.boe_yes.isChecked() if self._catalog_mode else False,
        )

    @staticmethod
    def category_text(category: str) -> str:
        labels = {
            "RECEITA_DIRETA": "Receita Direta",
            "RECEITA_INDIRETA": "Receita Indireta",
            "ADMINISTRATIVO": "Administrativo",
            "DIRETORIA": "Diretoria",
            "EVENTOS": "Eventos",
            "OPERACIONAL": "Operacional",
            "PESSOAL": "Pessoal",
            "INVESTIMENTO": "Investimento",
            "RESGATE": "Resgate",
            "SALDO_APLICADO": "Saldo Aplicado",
            "OUTROS": "Outros",
        }
        return labels.get(category, category.replace("_", " ").title())

    @staticmethod
    def type_text(value: str) -> str:
        return {
            "RECEITA": "Receita",
            "DESPESA": "Despesa",
            "APLICACAO": "Aplicação",
            "RESGATE": "Resgate",
            "SALDO": "Saldo",
        }.get(value, value)


class IndirectRevenueDialog(CashflowEntryDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nova Receita Indireta")
        self.entry_type.setEnabled(False)


from app.gui.import_workflow_steps import ImportWorkflowSteps
from app.gui.import_workflow_panel import ImportWorkflowPanel


class FinanceiroPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 2, 20, 0)
        layout.setSpacing(2)
        title = QLabel("Fluxo de Caixa")
        title.setObjectName("pageTitle")
        description = QLabel("Receitas, despesas, aplicações e resgates no mesmo fluxo financeiro.")
        description.setObjectName("pageDescription")
        filter_panel = QWidget()
        filter_panel.setObjectName("dashboardFilterBar")
        filters = QHBoxLayout(filter_panel)
        self.year_filter = WheelBlockedComboBox()
        self.year_filter.setEnabled(False)
        self.month_filter = MonthComboBox()
        self.month_filter.set_month(date.today().month)
        self.filter_button = QPushButton("Aplicar filtro")
        self.filter_button.setEnabled(False)
        self.filter_button.setProperty("buttonRole", "toolbar")
        self.new_entry_button = QPushButton("Novo Lançamento")
        self.new_entry_button.setProperty("buttonRole", "primary")
        self.new_entry_button.setObjectName("primaryButton")
        self.new_indirect_button = self.new_entry_button
        for label, widget in (("Ano", self.year_filter), ("Mês", self.month_filter)):
            filters.addWidget(QLabel(label))
            filters.addWidget(widget)
        filters.addWidget(self.filter_button)
        filters.addStretch()
        filters.addWidget(self.new_entry_button)

        self.import_box = QGroupBox("Importação Financeiro")
        self.import_box.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum
        )
        import_layout = QVBoxLayout(self.import_box)
        self.import_steps = ImportWorkflowSteps(steps=(
            "Selecionar",
            "Validar",
            "Comparar e autorizar",
            "Importar",
        ))
        # Import steps are mounted in ImportWorkflowPanel below.
        self.selected_import_file = QLabel("Nenhum arquivo selecionado.")
        self.import_issues = QPlainTextEdit()
        self.import_issues.setReadOnly(True)
        self.import_issues.setPlainText("Selecione uma planilha para iniciar.")
        self.import_issues.setFixedHeight(150)
        self.import_issues.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.import_issues.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.import_issues_scroll = QScrollArea()
        self.import_issues_scroll.setWidgetResizable(True)
        self.import_issues_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.import_issues_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.import_issues_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        # Validation panel is inserted directly in its layout.
        self.import_preview = QTableWidget(0, 8)
        self.import_preview.setHorizontalHeaderLabels(
            ["Linha", "Período", "Tipo", "Descrição", "Categoria", "BOE", "Valor", "Situação"]
        )
        self.import_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.import_preview.setMinimumHeight(210)
        self.import_preview.setMaximumHeight(260)
        self.import_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        result_layout = QHBoxLayout()
        result_layout.setSpacing(12)
        result_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        validation_layout = QVBoxLayout()
        validation_title = QLabel("Resultado da valida\u00e7\u00e3o")
        validation_title.setObjectName("sectionTitle")
        validation_layout.addWidget(validation_title)
        self.import_issues_scroll.setFixedHeight(150)
        validation_layout.addWidget(self.import_issues)
        result_layout.addLayout(validation_layout, 1)

        import_result_layout = QVBoxLayout()
        import_result_title = QLabel("Resultado da importa\u00e7\u00e3o")
        import_result_title.setObjectName("sectionTitle")
        self.import_result = QPlainTextEdit()
        self.import_result.setObjectName("financeiroImportResult")
        self.import_result.setReadOnly(True)
        self.import_result.setMinimumHeight(150)
        self.import_result.setMaximumHeight(150)
        self.import_result.setPlaceholderText(
            "Nenhuma importa\u00e7\u00e3o executada nesta sess\u00e3o."
        )
        import_result_layout.addWidget(import_result_title)
        import_result_layout.addWidget(self.import_result)
        result_layout.addLayout(import_result_layout, 1)

        # Move existing widgets into the shared BOE-style container.

        self.import_panel = ImportWorkflowPanel(
            steps=self.import_steps,
            file_display=self.selected_import_file,
            results_layout=result_layout,
            preview=self.import_preview,
        )

        # Preserve the already-wired legacy buttons, which stay hidden.
        import_layout.addWidget(self.import_panel)

        cards = QGridLayout()
        self.opening_balance = self._card("Saldo Inicial", cards, 0, 0, "balance")
        self.direct_total = self._card("Receita Direta", cards, 0, 1, "revenue")
        self.indirect_total = self._card("Receita Indireta", cards, 0, 2, "revenue")
        self.revenue_total = self._card("Receita Total", cards, 0, 3, "revenue")

        self.expense_total = self._card("Despesa Total", cards, 1, 0, "expense")
        self.operational_result = self._card("Saldo do Período", cards, 1, 1, "balance")
        self.applications_total = self._card("Aplicações", cards, 1, 2, "movement")
        self.redemptions_total = self._card("Resgates", cards, 1, 3, "movement")

        self.net_revenue = self._card("Receita Líquida", cards, 2, 0, "revenue")
        self.boe_total = self._card("Valor BOE", cards, 2, 1, "movement")
        self.bank_balance = self._card("Saldo Bancário", cards, 2, 2, "balance")
        self.applied_balance = self._card("Saldo Aplicado", cards, 2, 3, "balance")
        self.monthly_balance = self.operational_result
        self.period_balance = self.operational_result

        self.entries_table = QTableWidget(0, 7)
        self.entries_table.setHorizontalHeaderLabels(
            ["Período", "Tipo", "Descrição", "Categoria", "Origem", "BOE", "Valor"]
        )
        self.entries_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.entries_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entries_table.horizontalHeader().setStretchLastSection(True)
        self.entries_table.setMinimumHeight(92)
        self.entries_table.setMaximumHeight(112)
        self.entries_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.operation_status = QLabel("Fluxo de Caixa pronto.")
        self.operation_status.setObjectName("operationStatus")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(filter_panel)
        layout.addLayout(cards)
        layout.addWidget(self.entries_table, 0)
        self.import_panel.add_footer(self.operation_status)
        layout.addWidget(self.import_box)

        self.scroll_area.setWidget(content)
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.scroll_area)

    @staticmethod
    def _card(
        title: str,
        layout: QGridLayout,
        row: int,
        column: int,
        role: str = "neutral",
    ) -> QLabel:
        card = QWidget()
        card.setObjectName("summaryCard")
        card.setProperty("cardRole", role)
        card.setMaximumHeight(54)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 3, 10, 3)
        card_layout.setSpacing(1)
        label = QLabel(title)
        label.setObjectName("summaryLabel")
        value = QLabel("R$ 0,00")
        value.setObjectName("summaryValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        layout.addWidget(card, row, column)
        return value

    def show_financial_flow(
        self, movements: list[FinancialMovement], summary: FinancialFlowSummary,
        position=None,
    ) -> None:
        self.entries_table.setRowCount(len(movements))
        for row, movement in enumerate(movements):
            values = (
                movement.movement_date.strftime("%m/%Y"),
                movement.movement_type,
                movement.description,
                self._category_label(movement.category) if movement.category else "—",
                movement.origin or "—",
                "Sim" if movement.boe else "Não",
                self.format_currency(movement.value),
            )
            for column, value in enumerate(values):
                self.entries_table.setItem(row, column, QTableWidgetItem(value))
        self.direct_total.setText(self.format_currency(summary.direct_revenue))
        self.indirect_total.setText(self.format_currency(summary.indirect_revenue))
        self.revenue_total.setText(self.format_currency(summary.total_revenue))
        self.expense_total.setText(self.format_currency(summary.total_expense))
        self.applications_total.setText(self.format_currency(summary.applications))
        self.redemptions_total.setText(self.format_currency(summary.redemptions))
        self.operational_result.setText(self.format_currency(summary.operational_result))
        self.boe_total.setText(self.format_currency(summary.boe_expense))
        applied_value = (position.applied_balance if position is not None and position.applied_balance is not None else summary.applied_balance)
        self.applied_balance.setText(self.format_currency(applied_value))

        if position is None:
            self.opening_balance.setText("—")
            self.bank_balance.setText("—")
            self.net_revenue.setText("—")
        else:
            self.opening_balance.setText(self.format_currency(position.opening_balance))
            self.bank_balance.setText(self.format_currency(position.bank_balance))
            self.net_revenue.setText(self.format_currency(position.net_revenue))
        self.entries_table.resizeColumnsToContents()

    def selected_period(self) -> tuple[int, int]:
        return self.year_filter.currentData(), self.month_filter.month()

    def set_period(self, year: int, month: int) -> None:
        select_year(self.year_filter, year)
        self.month_filter.set_month(month)

    def set_available_years(self, years: list[int]) -> None:
        selected = populate_year_combo(self.year_filter, years)
        self.filter_button.setEnabled(selected is not None)
        if selected is None:
            self.set_status("Nenhum ano financeiro disponível.", error=True)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.operation_status.setText(message)
        self.operation_status.setProperty("error", error)
        self.operation_status.style().unpolish(self.operation_status)
        self.operation_status.style().polish(self.operation_status)

    def show_import_validation(self, result: dict) -> None:
        rows = result.get("preview", [])
        self.import_preview.setRowCount(len(rows))
        for index, row in enumerate(rows):
            situation = (
                "Receita Direta/BOE (ignorada)" if row.get("skip")
                else "Duplicado (ignorado)" if row.get("duplicate")
                else "Pronto para importar"
            )
            values = (
                row.get("line", ""),
                f"{int(row.get('month', 0)):02d}/{row.get('year', '')}",
                row.get("type") or row.get("type_label", ""),
                row.get("description", ""),
                row.get("category") or row.get("category_label", ""),
                "Sim" if row.get("boe") else "Não",
                self.format_currency(Decimal(str(row.get("value", 0)))),
                situation,
            )
            for column, value in enumerate(values):
                self.import_preview.setItem(index, column, QTableWidgetItem(str(value)))
        messages = []
        if result.get("errors"):
            messages.append("Erros bloqueantes:\n• " + "\n• ".join(result["errors"]))
        if result.get("warnings"):
            messages.append("Avisos:\n• " + "\n• ".join(result["warnings"]))
        if not messages:
            messages.append("Arquivo validado sem inconsistências.")
        # A file with only previously registered entries is not malformed.
        validation_errors = result.get("errors") or ()
        if (
            len(validation_errors) == 1
            and str(validation_errors[0]).startswith("Nenhum lan")
            and str(validation_errors[0]).endswith("registros duplicados.")
            and result.get("duplicates", 0) > 0
        ):
            messages = [
                "Arquivo validado. Nenhuma importa\u00e7\u00e3o necess\u00e1ria.",
                "Os lan\u00e7amentos j\u00e1 cadastrados foram ignorados "
                "para preservar a integridade financeira.",
                "Receitas Diretas continuam vinculadas ao BOE.",
            ]

        self.import_issues.setPlainText("\n\n".join(messages))
        self._fit_import_issues()
        self.import_preview.resizeColumnsToContents()

    def show_import_result(self, result: dict) -> None:
        self.set_status(
            "Importação Financeiro concluída: "
            f"{result.get('imported', 0)} lançamento(s) importado(s), "
            f"{result.get('ignored', 0)} ignorado(s)."
        )
        self.import_result.setPlainText(
            "Importa\u00e7\u00e3o conclu\u00edda com sucesso.\n"
            f"Importados: {result.get('imported', 0)}\n"
            f"Ignorados: {result.get('ignored', 0)}\n"
            f"Avisos: {len(result.get('warnings', []))}."
        )

    def _fit_import_issues(self) -> None:
        """The validation field handles its own scrolling."""
        self.import_issues.verticalScrollBar().setValue(0)

    @staticmethod
    def format_currency(value: Decimal) -> str:
        return format_currency(value)

    @staticmethod
    def _category_label(category: str) -> str:
        return CashflowEntryDialog.category_text(category)
