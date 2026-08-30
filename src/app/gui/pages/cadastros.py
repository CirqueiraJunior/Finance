from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.cashflow_entry import EXPENSE_CATEGORIES
from app.models.entity import Entity
from app.models.cashflow_catalog_entry import CashflowCatalogEntry


class EntityDialog(QDialog):
    def __init__(self, parent=None, entity: Entity | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Entidade" if entity else "Nova Entidade")
        form = QFormLayout(self)
        self.code = QSpinBox()
        self.code.setRange(1, 999999)
        self.name = QLineEdit()
        self.official_name = QLineEdit()
        self.city = QLineEdit()
        self.state = QLineEdit()
        self.state.setMaxLength(2)
        self.acronym = QLineEdit()
        self.active = QCheckBox("Ativa")
        self.active.setChecked(True)
        for label, field in (
            ("Código", self.code), ("Nome", self.name),
            ("Nome Oficial", self.official_name), ("Município", self.city),
            ("UF", self.state), ("Sigla", self.acronym), ("Situação", self.active),
        ):
            form.addRow(label, field)
        if entity:
            self.code.setValue(entity.codigo_entidade)
            self.code.setEnabled(False)
            self.name.setText(entity.nome)
            self.official_name.setText(entity.nome_oficial or "")
            self.city.setText(entity.municipio or "")
            self.state.setText(entity.uf or "")
            self.acronym.setText(entity.sigla or "")
            self.active.setChecked(entity.ativa)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict:
        return {
            "codigo_entidade": self.code.value(), "nome": self.name.text(),
            "nome_oficial": self.official_name.text(), "municipio": self.city.text(),
            "uf": self.state.text(), "sigla": self.acronym.text(),
            "ativa": self.active.isChecked(),
        }


class CatalogDialog(QDialog):
    TYPE_OPTIONS = (
        ("Receita", "RECEITA"),
        ("Despesa", "DESPESA"),
        ("Aplicação", "APLICACAO"),
        ("Resgate", "RESGATE"),
        ("Saldo", "SALDO"),
    )

    def __init__(self, parent=None, entry: CashflowCatalogEntry | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Item" if entry else "Novo Item do Catálogo")
        self.setMinimumWidth(520)

        form = QFormLayout(self)

        self.description = QLineEdit()

        # Tipo com o mesmo padrão visual do Novo Lançamento.
        self.type_widget = QWidget()
        type_layout = QHBoxLayout(self.type_widget)
        type_layout.setContentsMargins(0, 0, 0, 0)

        self.type_group = QButtonGroup(self)
        self.type_radios: dict[str, QRadioButton] = {}

        for label, movement_type in self.TYPE_OPTIONS:
            radio = QRadioButton(label)
            self.type_group.addButton(radio)
            self.type_radios[movement_type] = radio
            type_layout.addWidget(radio)

        type_layout.addStretch()

        self.category = QComboBox()
        self.category.addItem("Selecione a categoria...", None)

        self.active = QCheckBox("Ativo")
        self.active.setChecked(True)

        form.addRow("Descrição", self.description)
        form.addRow("Tipo", self.type_widget)
        form.addRow("Categoria", self.category)
        form.addRow("Situação", self.active)

        for radio in self.type_radios.values():
            radio.toggled.connect(self._update_categories)

        if entry:
            self.description.setText(entry.descricao)

            radio = self.type_radios.get(entry.tipo)
            if radio is not None:
                radio.setChecked(True)

            self._update_categories()

            category_index = self.category.findData(entry.categoria)
            if category_index >= 0:
                self.category.setCurrentIndex(category_index)

            self.active.setChecked(entry.ativa)
        else:
            self._update_categories()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selected_type(self) -> str | None:
        for movement_type, radio in self.type_radios.items():
            if radio.isChecked():
                return movement_type
        return None

    def _update_categories(self) -> None:
        movement_type = self.selected_type()

        self.category.blockSignals(True)
        self.category.clear()
        self.category.addItem("Selecione a categoria...", None)

        if movement_type == "RECEITA":
            categories = (
                ("Receita Direta", "RECEITA_DIRETA"),
                ("Receita Indireta", "RECEITA_INDIRETA"),
            )

        elif movement_type == "DESPESA":
            categories = tuple(
                (self._category_text(item.value), item.value)
                for item in EXPENSE_CATEGORIES
            )

        elif movement_type == "APLICACAO":
            categories = (("Investimento", "INVESTIMENTO"),)

        elif movement_type == "RESGATE":
            categories = (("Resgate", "RESGATE"),)

        elif movement_type == "SALDO":
            categories = (("Saldo Aplicado", "SALDO_APLICADO"),)

        else:
            categories = ()

        for label, value in categories:
            self.category.addItem(label, value)

        if len(categories) == 1:
            self.category.setCurrentIndex(1)

        self.category.blockSignals(False)

    @staticmethod
    def _category_text(category: str) -> str:
        labels = {
            "RECEITA_DIRETA": "Receita Direta",
            "RECEITA_INDIRETA": "Receita Indireta",
            "ADMINISTRATIVO": "Administrativo",
            "DIRETORIA": "Diretoria",
            "EVENTOS": "Eventos",
            "OPERACIONAL": "Operacional",
            "PESSOAL": "Pessoal",
            "INVESTIMENTO": "Investimento",
            "OUTROS": "Outros",
            "RESGATE": "Resgate",
            "SALDO_APLICADO": "Saldo Aplicado",
        }
        return labels.get(category, category.replace("_", " ").title())

    def values(self) -> dict:
        return {
            "description": self.description.text(),
            "category": self.category.currentData(),
            "movement_type": self.selected_type(),
            "active": self.active.isChecked(),
        }


class CadastrosPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Cadastros")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.entity_table = QTableWidget(0, 7)
        self.entity_table.setHorizontalHeaderLabels(
            ["Código", "Nome", "Nome Oficial", "Município", "UF", "Sigla", "Ativa"]
        )
        self.entity_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        entity_tab = QWidget()
        entity_layout = QVBoxLayout(entity_tab)
        entity_actions = QHBoxLayout()
        self.new_entity_button = QPushButton("Nova Entidade")
        self.edit_entity_button = QPushButton("Editar Entidade")
        self.toggle_entity_button = QPushButton("Ativar/Inativar")
        self.aliases_button = QPushButton("Consultar Aliases")
        for button in (self.new_entity_button, self.edit_entity_button,
                       self.toggle_entity_button, self.aliases_button):
            entity_actions.addWidget(button)
        entity_actions.addStretch()
        entity_layout.addLayout(entity_actions)
        entity_layout.addWidget(self.entity_table)
        self.catalog_table = QTableWidget(0, 4)
        self.catalog_table.setHorizontalHeaderLabels(
            ["Descrição", "Categoria", "Tipo", "Ativo"]
        )
        self.catalog_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.catalog_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        catalog_tab = QWidget()
        catalog_layout = QVBoxLayout(catalog_tab)
        catalog_actions = QHBoxLayout()
        self.new_catalog_button = QPushButton("Novo Item")
        self.edit_catalog_button = QPushButton("Editar Item")
        catalog_actions.addWidget(self.new_catalog_button)
        catalog_actions.addWidget(self.edit_catalog_button)
        catalog_actions.addStretch()
        catalog_layout.addLayout(catalog_actions)
        catalog_layout.addWidget(self.catalog_table)
        self.tabs.addTab(entity_tab, "Base Mestre de Entidades")
        self.tabs.addTab(catalog_tab, "Catálogo do Fluxo de Caixa")
        self.status = QLabel()
        layout.addWidget(self.status)

    def show_entities(self, entities: list[Entity]) -> None:
        self.entity_table.setRowCount(len(entities))
        for row, entity in enumerate(entities):
            values = (entity.codigo_entidade, entity.nome, entity.nome_oficial or "—",
                      entity.municipio or "—", entity.uf or "—", entity.sigla or "—",
                      "Sim" if entity.ativa else "Não")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, entity.id)
                self.entity_table.setItem(row, column, item)
        self.entity_table.resizeColumnsToContents()

    def show_catalog(self, entries: list[CashflowCatalogEntry]) -> None:
        self.catalog_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for column, value in enumerate((entry.descricao, entry.categoria, entry.tipo,
                                            "Sim" if entry.ativa else "Não")):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, entry.id)
                self.catalog_table.setItem(row, column, item)
        self.catalog_table.resizeColumnsToContents()

    def selected_entity_id(self) -> int | None:
        row = self.entity_table.currentRow()
        return None if row < 0 else self.entity_table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def selected_catalog_id(self) -> int | None:
        row = self.catalog_table.currentRow()
        return None if row < 0 else self.catalog_table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #b91c1c;" if error else "color: #166534;")
