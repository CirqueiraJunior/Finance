from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.budget_entry import BudgetEntry
from app.repositories.base import BaseRepository


class BudgetRepository(BaseRepository[BudgetEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_id(self, budget_id: int) -> BudgetEntry | None:
        return self.session.get(BudgetEntry, budget_id)

    @staticmethod
    def description_key(value: str | None) -> str:
        return (value or "").strip().lower()

    def get_by_period_type_category(
        self, year: int, month: int, entry_type: str,
        category: str, description: str | None = None,
    ) -> BudgetEntry | None:
        key = (
            year, month, entry_type, category,
            self.description_key(description),
        )
        return self.by_keys({key}).get(key)

    def exists(
        self, year: int, month: int, entry_type: str,
        category: str, description: str | None = None,
    ) -> bool:
        return self.get_by_period_type_category(
            year, month, entry_type, category, description
        ) is not None

    def add(self, budget: BudgetEntry) -> BudgetEntry:
        self.session.add(budget)
        self.session.flush()
        return budget

    def add_all(self, budgets: Iterable[BudgetEntry]) -> None:
        self.session.add_all(list(budgets))

    def available_years(self) -> list[int]:
        return list(self.session.scalars(
            select(BudgetEntry.periodo_ano)
            .distinct().order_by(BudgetEntry.periodo_ano)
        ))

    def existing_keys(
        self, years: Iterable[int]
    ) -> set[tuple[int, int, str, str, str]]:
        scoped_years = tuple(sorted(set(years)))
        if not scoped_years:
            return set()

        entries = self.session.scalars(
            select(BudgetEntry).where(
                BudgetEntry.periodo_ano.in_(scoped_years)
            )
        )
        return {
            (
                item.periodo_ano, item.periodo_mes,
                item.tipo, item.categoria,
                self.description_key(item.descricao),
            )
            for item in entries
        }

    def by_keys(
        self, keys: Iterable[tuple[int, int, str, str, str]]
    ) -> dict[tuple[int, int, str, str, str], BudgetEntry]:
        requested = set(keys)
        if not requested:
            return {}

        years = {key[0] for key in requested}
        entries = self.session.scalars(
            select(BudgetEntry).where(
                BudgetEntry.periodo_ano.in_(years)
            )
        )

        found = {}
        for item in entries:
            key = (
                item.periodo_ano, item.periodo_mes,
                item.tipo, item.categoria,
                self.description_key(item.descricao),
            )
            if key in requested:
                if key in found:
                    raise ValueError(
                        "Registros orcamentarios duplicados no banco."
                    )
                found[key] = item
        return found


    def by_groups(
        self, groups: Iterable[tuple[int, int, str, str]]
    ) -> list[BudgetEntry]:
        requested = set(groups)
        if not requested:
            return []

        years = sorted({year for year, _, _, _ in requested})
        entries = self.session.scalars(
            select(BudgetEntry).where(
                BudgetEntry.periodo_ano.in_(years)
            )
        )
        return [
            entry for entry in entries
            if (
                entry.periodo_ano, entry.periodo_mes,
                entry.tipo, entry.categoria,
            ) in requested
        ]

    def list_all(self) -> list[BudgetEntry]:
        statement = select(BudgetEntry).order_by(
            BudgetEntry.periodo_ano,
            BudgetEntry.periodo_mes,
            BudgetEntry.tipo,
            BudgetEntry.categoria,
        )
        return list(self.session.scalars(statement))

    def list_by_period(self, year: int, month: int) -> list[BudgetEntry]:
        statement = (
            select(BudgetEntry)
            .where(
                BudgetEntry.periodo_ano == year,
                BudgetEntry.periodo_mes == month,
            )
            .order_by(BudgetEntry.tipo, BudgetEntry.categoria)
        )
        return list(self.session.scalars(statement))

    def list_by_year(self, year: int) -> list[BudgetEntry]:
        statement = (
            select(BudgetEntry)
            .where(BudgetEntry.periodo_ano == year)
            .order_by(
                BudgetEntry.periodo_mes,
                BudgetEntry.tipo,
                BudgetEntry.categoria,
            )
        )
        return list(self.session.scalars(statement))
