from app.repositories.cashflow_repository import CashflowRepository
from tests.boe_helpers import add_boe_import
from tests.cashflow_helpers import make_manual_entry


def test_repository_get_by_id_and_lists(db_session):
    repository = CashflowRepository(db_session)
    july = repository.add(make_manual_entry())
    repository.add(make_manual_entry(month=8, description="Agosto"))
    db_session.commit()

    assert repository.get_by_id(july.id) is july
    assert len(repository.list_all()) == 2
    assert repository.list_by_period(2026, 7) == [july]


def test_repository_finds_entry_by_boe_import(db_session):
    from datetime import date
    from decimal import Decimal
    from app.models.cashflow_entry import CashflowEntry

    boe_import = add_boe_import(db_session)
    repository = CashflowRepository(db_session)
    entry = repository.add(CashflowEntry(
        periodo_ano=2026, periodo_mes=7, data_lancamento=date(2026, 7, 1),
        descricao="BOE", tipo="RECEITA", origem="BOE", categoria="RECEITA_DIRETA",
        valor=Decimal("1"), boe_import_id=boe_import.id,
    ))
    db_session.commit()

    assert repository.get_by_boe_import_id(boe_import.id) is entry
    assert repository.exists_for_boe_import(boe_import.id)
    assert not repository.exists_for_boe_import(9999)
