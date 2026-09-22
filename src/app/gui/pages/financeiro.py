from datetime import date
from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton,
    QMessageBox, QRadioButton, QScrollArea, QSizePolicy, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.cashflow_entry import EXPENSE_CATEGORIES, CashflowCategory, CashflowType
from app.models.investment_movement import InvestmentMovementType
from app.services.cashflow_catalog_service import CashflowCatalogOption
from app.services.financial_flow_service import FinancialFlowSummary, FinancialMovement
from app.widgets import BRLCurrencyEdit, MonthComboBox


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
        self.entry_type = QComboBox()
        for label, value in self.TYPE_OPTIONS:
            self.entry_type.addItem(label, value)

        self.entry_date = QDateEdit(QDate.currentDate())
        self.entry_date.setCalendarPopup(True)
        self.entry_date.setDisplayFormat("dd/MM/yyyy")

        self.description = QComboBox() if self._catalog_mode else QLineEdit()
        self.category = QComboBox()
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
            self.year_input = QSpinBox()
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


class FinanceiroPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 2, 20, 0)
        layout.setSpacing(2)
        title = QLabel("Fluxo de Caixa")
        title.setObjectName("pageTitle")
        description = QLabel("Receitas, despesas, aplicações e resgates no mesmo fluxo financeiro.")
        description.setObjectName("pageDescription")
        filters = QHBoxLayout()
        self.year_filter = QSpinBox()
        self.year_filter.setRange(2000, 9999)
        self.year_filter.setValue(date.today().year)
        self.month_filter = MonthComboBox()
        self.month_filter.set_month(date.today().month)
        self.filter_button = QPushButton("Aplicar filtro")
        self.new_entry_button = QPushButton("Novo Lançamento")
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
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        import_layout = QVBoxLayout(self.import_box)
        import_actions = QHBoxLayout()
        self.select_import_button = QPushButton("Selecionar arquivo")
        self.validate_import_button = QPushButton("Validar")
        self.confirm_import_button = QPushButton("Importar")
        self.confirm_import_button.setObjectName("primaryButton")
        self.selected_import_file = QLabel("Nenhum arquivo selecionado.")
        self.validate_import_button.setEnabled(False)
        self.confirm_import_button.setEnabled(False)
        import_actions.addWidget(self.select_import_button)
        import_actions.addWidget(self.validate_import_button)
        import_actions.addWidget(self.confirm_import_button)
        import_actions.addWidget(self.selected_import_file, 1)
        self.import_issues = QPlainTextEdit()
        self.import_issues.setReadOnly(True)
        self.import_issues.setPlainText("Selecione uma planilha para iniciar.")
        self.import_issues.setFixedHeight(72)
        self.import_issues.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.import_issues.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
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
        self.import_issues_scroll.setWidget(self.import_issues)
        self.import_preview = QTableWidget(0, 8)
        self.import_preview.setHorizontalHeaderLabels(
            ["Linha", "Período", "Tipo", "Descrição", "Categoria", "BOE", "Valor", "Situação"]
        )
        self.import_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.import_preview.setMinimumHeight(210)
        self.import_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        import_layout.addLayout(import_actions)
        import_layout.addWidget(self.import_issues_scroll)
        import_layout.addWidget(self.import_preview, 1)

        cards = QGridLayout()
        self.opening_balance = self._card("Saldo Inicial", cards, 0, 0)
        self.revenue_total = self._card("Receita Total", cards, 0, 1)
        self.expense_total = self._card("Despesa Total", cards, 0, 2)
        self.operational_result = self._card("Resultado Operacional", cards, 0, 3)

        self.applications_total = self._card("Aplicações", cards, 1, 0)
        self.redemptions_total = self._card("Resgates", cards, 1, 1)
        self.bank_balance = self._card("Saldo Bancário", cards, 1, 2)
        self.applied_balance = self._card("Saldo Aplicado", cards, 1, 3)

        self.boe_total = self._card("Valor BOE", cards, 2, 0)
        self.net_revenue = self._card("Receita Líquida", cards, 2, 1)
        self.direct_total = QLabel()
        self.indirect_total = QLabel()
        self.monthly_balance = self.operational_result

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
        layout.addLayout(filters)
        layout.addLayout(cards)
        layout.addWidget(self.entries_table, 0)
        layout.addWidget(self.import_box, 1)
        layout.addWidget(self.operation_status, 0)

    @staticmethod
    def _card(title: str, layout: QGridLayout, row: int, column: int) -> QLabel:
        card = QWidget()
        card.setObjectName("summaryCard")
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
        self.applied_balance.setText(self.format_currency(summary.applied_balance))

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
        return self.year_filter.value(), self.month_filter.month()

    def set_period(self, year: int, month: int) -> None:
        self.year_filter.setValue(year)
        self.month_filter.set_month(month)

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
        self.import_issues.setPlainText("\n\n".join(messages))
        self._fit_import_issues()
        self.confirm_import_button.setEnabled(bool(result.get("can_import")))
        self.import_preview.resizeColumnsToContents()

    def show_import_result(self, result: dict) -> None:
        self.set_status(
            "Importação Financeiro concluída: "
            f"{result.get('imported', 0)} lançamento(s) importado(s), "
            f"{result.get('ignored', 0)} ignorado(s)."
        )
        self.import_issues.setPlainText(
            "Importação concluída com sucesso. "
            f"Avisos: {len(result.get('warnings', []))}."
        )
        self._fit_import_issues()

    def _fit_import_issues(self) -> None:
        """Mantém mensagens completas sem comprimir a tabela de prévia."""
        width = max(self.import_issues_scroll.viewport().width(), 320)
        content_height = max(
            self.import_issues.heightForWidth(width),
            self.import_issues.sizeHint().height(),
        )
        self.import_issues.setMinimumHeight(content_height)
        self.import_issues_scroll.setFixedHeight(min(content_height + 2, 96))
        self.import_issues_scroll.verticalScrollBar().setValue(0)

    @staticmethod
    def format_currency(value: Decimal) -> str:
        formatted = f"{value:,.2f}"
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def _category_label(category: str) -> str:
        return CashflowEntryDialog.category_text(category)
