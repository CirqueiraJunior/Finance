from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.boe_entity_total import BOEEntityTotal
from app.models.boe_import import BOEImport
from app.models.boe_import_issue import BOEImportIssue
from app.models.entity import Entity
from tests.boe_helpers import add_boe_import


def test_boe_relationships_and_numeric_precision(db_session: Session) -> None:
    entity = Entity(codigo_entidade=7501, nome="CDL GOIANIA/GO")
    db_session.add(entity)
    db_session.flush()
    boe_import = add_boe_import(db_session)
    boe_import.entity_totals.append(
        BOEEntityTotal(
            entity_id=entity.id,
            codigo_entidade_origem=7501,
            nome_entidade_origem="CDL GOIANIA/GO",
            quantidade_consultas=100,
            valor_total=Decimal("6.9300"),
        )
    )
    boe_import.issues.append(
        BOEImportIssue(
            linha=10,
            codigo="7501",
            mensagem="Aviso de teste",
            severidade="WARNING",
        )
    )
    db_session.commit()
    db_session.expire_all()

    persisted = db_session.get(BOEImport, boe_import.id)

    assert persisted is not None
    assert persisted.entity_totals[0].valor_total == Decimal("6.9300")
    assert persisted.entity_totals[0].entity.codigo_entidade == 7501
    assert persisted.issues[0].boe_import is persisted


def test_boe_import_hash_is_unique(db_session: Session) -> None:
    add_boe_import(db_session, file_hash="b" * 64)
    duplicate = BOEImport(
        periodo_ano=2026,
        periodo_mes=8,
        nome_arquivo="outro.xlsx",
        caminho_origem="C:/outro.xlsx",
        hash_arquivo="b" * 64,
        quantidade_entidades=0,
        quantidade_inconsistencias=0,
        valor_total=Decimal("0"),
        status="imported",
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_boe_import_period_is_unique(db_session: Session) -> None:
    add_boe_import(db_session, year=2026, month=7, file_hash="c" * 64)
    duplicate = BOEImport(
        periodo_ano=2026,
        periodo_mes=7,
        nome_arquivo="outro.xlsx",
        caminho_origem="C:/outro.xlsx",
        hash_arquivo="d" * 64,
        quantidade_entidades=0,
        quantidade_inconsistencias=0,
        valor_total=Decimal("0"),
        status="imported",
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_deleting_import_cascades_to_totals_and_issues(db_session: Session) -> None:
    entity = Entity(codigo_entidade=7501, nome="CDL GOIANIA/GO")
    db_session.add(entity)
    db_session.flush()
    boe_import = add_boe_import(db_session, file_hash="e" * 64)
    boe_import.entity_totals.append(
        BOEEntityTotal(
            entity_id=entity.id,
            codigo_entidade_origem=7501,
            nome_entidade_origem="CDL GOIANIA/GO",
            quantidade_consultas=1,
            valor_total=Decimal("0.0693"),
        )
    )
    boe_import.issues.append(
        BOEImportIssue(mensagem="Aviso de teste", severidade="WARNING")
    )
    db_session.commit()

    db_session.delete(boe_import)
    db_session.commit()

    totals = db_session.scalar(select(func.count()).select_from(BOEEntityTotal))
    issues = db_session.scalar(select(func.count()).select_from(BOEImportIssue))
    assert totals == 0
    assert issues == 0
