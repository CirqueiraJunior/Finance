from datetime import date
from decimal import Decimal

from app.gui.pages.financeiro import CashflowEntryDialog
from app.models.cashflow_catalog_entry import CashflowCatalogEntry
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.services.cashflow_catalog_service import (
    CashflowCatalogOption,
    CashflowCatalogService,
)
from app.services.cashflow_service import CashflowService


def seed_catalog(db_session):
    rows = [
        CashflowCatalogEntry(
            descricao="Viagem", categoria="DIRETORIA", tipo="DESPESA", ativa=True
        ),
        CashflowCatalogEntry(
            descricao="Viagem", categoria="EVENTOS", tipo="DESPESA", ativa=True
        ),
        CashflowCatalogEntry(
            descricao="Venda de Produtos/Serviços",
            categoria="RECEITA_INDIRETA",
            tipo="RECEITA",
            ativa=True,
        ),
        CashflowCatalogEntry(
            descricao="Aplicação", categoria="INVESTIMENTO", tipo="APLICACAO", ativa=True
        ),
        CashflowCatalogEntry(
            descricao="Saldo Aplicado", categoria="SALDO_APLICADO", tipo="SALDO", ativa=True
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()


def test_catalog_filters_description_and_excludes_manual_balance(db_session):
    seed_catalog(db_session)
    service = CashflowCatalogService(CashflowCatalogRepository(db_session))
    assert service.list_descriptions() == (
        "Aplicação", "Venda de Produtos/Serviços", "Viagem"
    )
    viagem = service.options_for_description("Viagem")
    assert {(item.category, item.movement_type) for item in viagem} == {
        ("DIRETORIA", "DESPESA"),
        ("EVENTOS", "DESPESA"),
    }
    assert any(
        option.movement_type == "SALDO"
        for option in service.list_options(include_balance=True)
    )


def test_dialog_derives_type_from_description_and_category(qtbot, db_session):
    seed_catalog(db_session)
    options = CashflowCatalogService(
        CashflowCatalogRepository(db_session)
    ).list_options()
    dialog = CashflowEntryDialog(catalog_options=options)
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Viagem")
    # placeholder + duas categorias válidas no catálogo de teste
    assert dialog.category.count() == 3
    assert dialog.category.currentData() is None
    assert not any(radio.isChecked() for radio in dialog.type_radios.values())

    dialog.category.setCurrentIndex(1)
    assert dialog.type_radios["DESPESA"].isChecked()
    assert dialog.boe_yes.isEnabled()
    assert dialog.boe_no.isEnabled()

    dialog.description.setCurrentText("Venda de Produtos/Serviços")
    assert dialog.category.count() == 1
    assert dialog.type_radios["RECEITA"].isChecked()
    assert dialog.boe_yes.isEnabled()
    assert dialog.boe_no.isEnabled()


def test_cashflow_persists_boe_flag_and_splits_expenses(db_session):
    service = CashflowService(CashflowRepository(db_session))
    service.create_expense(
        year=2026,
        month=7,
        entry_date=date(2026, 7, 5),
        description="Salários e Encargos",
        category="PESSOAL",
        value="100.0000",
        boe=True,
    )
    service.create_expense(
        year=2026,
        month=7,
        entry_date=date(2026, 7, 6),
        description="Seguro",
        category="ADMINISTRATIVO",
        value="50.0000",
        boe=False,
    )
    summary = service.get_monthly_summary(2026, 7)
    assert summary.total_expense == Decimal("150.0000")
    assert summary.boe_expense == Decimal("100.0000")
    assert summary.non_boe_expense == Decimal("50.0000")


def test_selected_month_is_persisted_with_internal_first_day(qtbot, db_session):
    dialog = CashflowEntryDialog(
        catalog_options=(
            CashflowCatalogOption("Software", "ADMINISTRATIVO", "DESPESA"),
        ),
        period_year=2026,
        period_month=8,
    )
    qtbot.addWidget(dialog)
    dialog.description.setCurrentText("Software")
    dialog.boe_no.setChecked(True)
    dialog.value.setText("100,50")
    movement_type, entry_date, description, category, value, _, boe = dialog.values()

    entry = CashflowService(CashflowRepository(db_session)).create_expense(
        year=entry_date.year,
        month=entry_date.month,
        entry_date=entry_date,
        description=description,
        category=category,
        value=value,
        boe=boe,
    )

    assert movement_type == "DESPESA"
    assert entry.periodo_ano == 2026
    assert entry.periodo_mes == 8
    assert entry.data_lancamento == date(2026, 8, 1)
    assert entry.valor == Decimal("100.5000")
