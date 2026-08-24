from app.importers.boe_importer import BOEImporter
from app.models.entity import Entity
from app.repositories.boe_repository import BOERepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.entity_repository import EntityRepository
from app.services.boe_service import BOEService
from app.services.cashflow_service import CashflowService
from app.core.exceptions import BOEValidationError
from app.models.boe_import import BOEImport
from sqlalchemy import select
from tests.boe_helpers import create_boe_workbook


def test_boe_import_creates_one_direct_revenue(db_session, tmp_path):
    db_session.add_all([
        Entity(codigo_entidade=7501, nome="CDL GOIANIA/GO"),
        Entity(codigo_entidade=7544, nome="CDL ANAPOLIS/GO"),
    ])
    db_session.commit()
    cashflow = CashflowService(CashflowRepository(db_session))
    boe = BOEService(
        BOERepository(db_session), EntityRepository(db_session), BOEImporter(), cashflow
    )
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")

    imported = boe.import_file(path)

    entry = cashflow.repository.get_by_boe_import_id(imported.id)
    assert entry is not None
    assert entry.valor == imported.valor_total
    assert len(cashflow.list_entries()) == 1

    try:
        boe.import_file(path)
    except BOEValidationError:
        pass
    else:
        raise AssertionError("A segunda importação BOE deveria ser bloqueada.")
    assert len(cashflow.list_entries()) == 1


def test_cashflow_failure_rolls_back_boe_import(db_session, tmp_path, monkeypatch):
    db_session.add_all([
        Entity(codigo_entidade=7501, nome="CDL GOIANIA/GO"),
        Entity(codigo_entidade=7544, nome="CDL ANAPOLIS/GO"),
    ])
    db_session.commit()
    cashflow = CashflowService(CashflowRepository(db_session))
    boe = BOEService(
        BOERepository(db_session), EntityRepository(db_session), BOEImporter(), cashflow
    )
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")

    monkeypatch.setattr(
        cashflow.repository,
        "add",
        lambda _entry: (_ for _ in ()).throw(RuntimeError("falha controlada")),
    )
    try:
        boe.import_file(path)
    except RuntimeError:
        pass
    else:
        raise AssertionError("A falha financeira deveria abortar a importação BOE.")

    assert db_session.scalars(select(BOEImport)).all() == []
