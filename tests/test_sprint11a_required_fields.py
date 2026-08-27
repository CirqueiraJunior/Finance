from PySide6.QtWidgets import QMessageBox

from app.gui.pages.financeiro import CashflowEntryDialog
from app.services.cashflow_catalog_service import CashflowCatalogOption


def _options():
    return (
        CashflowCatalogOption("Viagem", "DIRETORIA", "DESPESA"),
        CashflowCatalogOption("Viagem", "EVENTOS", "DESPESA"),
        CashflowCatalogOption("Software", "ADMINISTRATIVO", "DESPESA"),
    )


def test_save_blocks_when_category_is_missing(qtbot, monkeypatch):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Viagem")
    dialog.value.setText("100,00")

    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: messages.append(args[2]) if len(args) > 2 else None,
    )

    dialog._accept_if_valid()

    assert dialog.result() == 0
    assert messages == ["Informe a Categoria."]


def test_save_blocks_when_description_is_missing(qtbot, monkeypatch):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: messages.append(args[2]) if len(args) > 2 else None,
    )

    dialog._accept_if_valid()

    assert dialog.result() == 0
    assert messages == ["Informe a Descrição."]


def test_save_blocks_when_boe_is_missing(qtbot, monkeypatch):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Software")
    dialog.value.setText("100,00")

    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: messages.append(args[2]) if len(args) > 2 else None,
    )

    dialog._accept_if_valid()

    assert dialog.result() == 0
    assert messages == ["Informe se o lançamento é BOE: Sim ou Não."]


def test_save_blocks_when_value_is_missing(qtbot, monkeypatch):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Software")
    dialog.boe_no.setChecked(True)

    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: messages.append(args[2]) if len(args) > 2 else None,
    )

    dialog._accept_if_valid()

    assert dialog.result() == 0
    assert messages == ["Informe um valor maior que zero."]


def test_save_blocks_zero_negative_and_invalid_values(qtbot, monkeypatch):
    dialog = CashflowEntryDialog(
        catalog_options=_options(), period_year=2026, period_month=8
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Software")
    dialog.boe_no.setChecked(True)
    messages = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: messages.append(args[2]) if len(args) > 2 else None,
    )

    for value in ("0", "-1", "texto"):
        dialog.value.setText(value)
        dialog._accept_if_valid()

    assert messages == [
        "Informe um valor maior que zero.",
        "Informe um valor maior que zero.",
        "Informe um valor maior que zero.",
    ]
