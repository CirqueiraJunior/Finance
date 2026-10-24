from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.budget_entry import BudgetEntry


def test_distinct_descriptions_and_normalized_duplicate():
    engine = create_engine("sqlite:///:memory:")
    BudgetEntry.__table__.create(engine)

    def budget(description):
        return BudgetEntry(
            periodo_ano=2025,
            periodo_mes=1,
            tipo="DESPESA",
            categoria="ADMINISTRATIVO",
            descricao=description,
            valor_orcado=Decimal("100.00"),
        )

    try:
        with Session(engine) as session:
            session.add_all([
                budget("Impostos e Taxas"),
                budget("IPVA"),
                budget("Manutencao"),
            ])
            session.commit()
            assert len(session.scalars(select(BudgetEntry)).all()) == 3

            session.add(budget(" impostos e taxas "))
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

            assert len(session.scalars(select(BudgetEntry)).all()) == 3
    finally:
        engine.dispose()
