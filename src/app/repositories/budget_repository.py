from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.budget_entry import BudgetEntry
from app.repositories.base import BaseRepository


class BudgetRepository(BaseRepository[BudgetEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_id(self, budget_id: int) -> BudgetEntry | None:
        return self.session.get(BudgetEntry, budget_id)

    def get_by_period_type_category(
        self, year: int, month: int, entry_type: str, category: str
    ) -> BudgetEntry | None:
        return self.session.scalar(
            select(BudgetEntry).where(
                BudgetEntry.periodo_ano == year,
                BudgetEntry.periodo_mes == month,
                BudgetEntry.tipo == entry_type,
                BudgetEntry.categoria == category,
            )
        )

    def exists(self, year: int, month: int, entry_type: str, category: str) -> bool:
        return self.get_by_period_type_category(
            year, month, entry_type, category
        ) is not None

    def add(self, budget: BudgetEntry) -> BudgetEntry:
        self.session.add(budget)
        self.session.flush()
        return budget

    def list_all(self) -> list[BudgetEntry]:
        statement = select(BudgetEntry).order_by(
            BudgetEntry.periodo_ano, BudgetEntry.periodo_mes,
            BudgetEntry.tipo, BudgetEntry.categoria,
        )
        return list(self.session.scalars(statement))

    def list_by_period(self, year: int, month: int) -> list[BudgetEntry]:
        statement = (
            select(BudgetEntry)
            .where(BudgetEntry.periodo_ano == year, BudgetEntry.periodo_mes == month)
            .order_by(BudgetEntry.tipo, BudgetEntry.categoria)
        )
        return list(self.session.scalars(statement))

    def list_by_year(self, year: int) -> list[BudgetEntry]:
        statement = (
            select(BudgetEntry)
            .where(BudgetEntry.periodo_ano == year)
            .order_by(BudgetEntry.periodo_mes, BudgetEntry.tipo, BudgetEntry.categoria)
        )
        return list(self.session.scalars(statement))
