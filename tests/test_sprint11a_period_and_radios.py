import pytest

from decimal import Decimal

from app.gui.pages.financeiro import CashflowEntryDialog, FinanceiroPage, MonetaryLineEdit
from app.services.cashflow_catalog_service import CashflowCatalogOption


def _options():
    return (
        CashflowCatalogOption("Software", "ADMINISTRATIVO", "DESPESA"),
        CashflowCatalogOption("Viagem", "DIRETORIA", "DESPESA"),
        CashflowCatalogOption("Viagem", "EVENTOS", "DESPESA"),
        CashflowCatalogOption("Viagem", "OPERACIONAL", "DESPESA"),
        CashflowCatalogOption("Venda de Produtos/Serviços", "RECEITA_INDIRETA", "RECEITA"),
        CashflowCatalogOption("Aplicação", "INVESTIMENTO", "APLICACAO"),
        CashflowCatalogOption("Resgate de Aplicação", "RESGATE", "RESGATE"),
        CashflowCatalogOption("Reembolso", "DIRETORIA", "DESPESA"),
        CashflowCatalogOption("Reembolso", "OPERACIONAL", "DESPESA"),
        CashflowCatalogOption("Reembolso", "RECEITA_INDIRETA", "RECEITA"),
    )


def test_catalog_dialog_uses_period_only_and_internal_first_day(qtbot):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    assert dialog.year_input.value() == 2026
    assert dialog.month_input.currentData() == 8
    assert dialog.month_input.currentText() == "Agosto"
    assert dialog.month_input.itemData(0) == 1
    assert dialog.month_input.itemText(0) == "Janeiro"
    assert dialog.month_input.itemData(11) == 12
    assert dialog.month_input.itemText(11) == "Dezembro"
    assert not dialog.entry_date.isVisible()
    assert dialog.movement_date().isoformat() == "2026-08-01"
    dialog.year_input.setValue(2027)
    dialog.month_input.setCurrentIndex(dialog.month_input.findData(3))
    assert dialog.movement_date().isoformat() == "2027-03-01"


def test_multiple_categories_start_blank_and_type_is_not_preselected(qtbot):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Viagem")
    assert dialog.category.currentData() is None
    assert dialog.category.currentText() == "Selecione a categoria..."
    assert dialog.entry_type.currentData() is None
    assert not any(radio.isChecked() for radio in dialog.type_radios.values())

    dialog.category.setCurrentIndex(1)
    assert dialog.category.currentData() in {"DIRETORIA", "EVENTOS", "OPERACIONAL"}
    assert dialog.type_radios["DESPESA"].isChecked()


def test_single_category_autoselects_and_type_radio_is_derived(qtbot):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Software")
    assert dialog.category.currentData() == "ADMINISTRATIVO"
    assert dialog.type_radios["DESPESA"].isChecked()
    assert dialog.entry_type.currentData() == "DESPESA"
    assert dialog.type_radios["DESPESA"].isEnabled()


def test_boe_is_radio_selection_and_starts_blank(qtbot):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    assert not dialog.boe_yes.isChecked()
    assert not dialog.boe_no.isChecked()
    dialog.description.setCurrentText("Software")
    assert not dialog.boe_yes.isChecked()
    assert not dialog.boe_no.isChecked()
    dialog.boe_yes.setChecked(True)
    dialog.value.setText("1,00")
    assert dialog.values()[-1] is True


def test_official_single_category_examples_derive_type(qtbot):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)

    expected = (
        ("Venda de Produtos/Serviços", "RECEITA_INDIRETA", "RECEITA"),
        ("Aplicação", "INVESTIMENTO", "APLICACAO"),
    )
    for description, category, movement_type in expected:
        dialog.description.setCurrentText(description)
        assert dialog.category.currentData() == category
        assert dialog.entry_type.currentData() == movement_type
        assert dialog.type_radios[movement_type].isChecked()


def test_reimbursement_derives_type_only_after_category(qtbot):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Reembolso")
    assert dialog.category.currentData() is None
    assert dialog.entry_type.currentData() is None

    expense_index = dialog.category.findData("OPERACIONAL")
    dialog.category.setCurrentIndex(expense_index)
    assert dialog.entry_type.currentData() == "DESPESA"

    revenue_index = dialog.category.findData("RECEITA_INDIRETA")
    dialog.category.setCurrentIndex(revenue_index)
    assert dialog.entry_type.currentData() == "RECEITA"


def test_brazilian_value_and_portuguese_buttons(qtbot):
    from PySide6.QtWidgets import QDialogButtonBox

    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    buttons = dialog.findChild(QDialogButtonBox)
    assert dialog.value.placeholderText() == "R$ 0,00"
    assert isinstance(dialog.value, MonetaryLineEdit)
    assert buttons.button(QDialogButtonBox.StandardButton.Save).text() == "Salvar"
    assert buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Cancelar"
    dialog.value.setText("1.250,75")
    assert dialog.values()[4] == "1250.75"


@pytest.mark.parametrize(
    ("digits", "formatted", "amount"),
    (
        ("1", "R$ 0,01", Decimal("0.01")),
        ("12", "R$ 0,12", Decimal("0.12")),
        ("123", "R$ 1,23", Decimal("1.23")),
        ("1234", "R$ 12,34", Decimal("12.34")),
        ("123456", "R$ 1.234,56", Decimal("1234.56")),
    ),
)
def test_monetary_typing_uses_last_two_digits_as_cents(
    qtbot, digits, formatted, amount
):
    field = MonetaryLineEdit()
    qtbot.addWidget(field)
    field.show()
    field.setFocus()
    qtbot.keyClicks(field, digits)
    assert field.text() == formatted
    assert field.decimal_value() == amount


@pytest.mark.parametrize(
    "description",
    (
        "Alimentação/Refeição",
        "Hospedagem",
        "Manutenção",
        "Materais Gráficos e Escritório",
        "Palestra/Workshop",
        "Premiação",
        "Reembolso",
        "Viagem",
    ),
)
def test_all_official_ambiguous_descriptions_start_without_category_or_type(
    qtbot, description
):
    options = (
        CashflowCatalogOption(description, "DIRETORIA", "DESPESA"),
        CashflowCatalogOption(description, "OPERACIONAL", "DESPESA"),
    )
    dialog = CashflowEntryDialog(
        catalog_options=options, period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText(description)
    assert dialog.category.currentData() is None
    assert dialog.entry_type.currentData() is None
    assert not any(radio.isChecked() for radio in dialog.type_radios.values())


def test_financial_table_uses_period_not_date(qtbot):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    assert page.entries_table.horizontalHeaderItem(0).text() == "Período"
