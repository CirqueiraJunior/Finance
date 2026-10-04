from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.investment_movement import InvestmentMovement
from app.repositories.base import BaseRepository


class InvestmentRepository(BaseRepository[InvestmentMovement]):
    def get_by_id(self, movement_id: int) -> InvestmentMovement | None:
        return self.session.get(InvestmentMovement, movement_id)

    def add(self, movement: InvestmentMovement) -> InvestmentMovement:
        self.session.add(movement)
        self.session.flush()
        return movement

    def list_all(self) -> list[InvestmentMovement]:
        statement = select(InvestmentMovement).order_by(
            InvestmentMovement.data_movimento, InvestmentMovement.id
        )
        return list(self.session.scalars(statement))

    def list_by_period(self, year: int, month: int) -> list[InvestmentMovement]:
        statement = (
            select(InvestmentMovement)
            .where(
                InvestmentMovement.periodo_ano == year,
                InvestmentMovement.periodo_mes == month,
            )
            .order_by(InvestmentMovement.data_movimento, InvestmentMovement.id)
        )
        return list(self.session.scalars(statement))

    def available_years(self) -> list[int]:
        return list(self.session.scalars(
            select(InvestmentMovement.periodo_ano)
            .distinct().order_by(InvestmentMovement.periodo_ano)
        ))

    def list_until_date(self, end_date: date) -> list[InvestmentMovement]:
        statement = (
            select(InvestmentMovement)
            .where(InvestmentMovement.data_movimento <= end_date)
            .order_by(InvestmentMovement.data_movimento, InvestmentMovement.id)
        )
        return list(self.session.scalars(statement))
