from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.association_entry import AssociationEntry
from app.repositories.base import BaseRepository


class AssociationRepository(BaseRepository[AssociationEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def add(self, entry: AssociationEntry) -> AssociationEntry:
        self.session.add(entry)
        self.session.flush()
        return entry

    def add_all(self, entries: Iterable[AssociationEntry]) -> None:
        self.session.add_all(list(entries))

    def existing_keys(
        self, years: Iterable[int]
    ) -> set[tuple[int, int, int]]:
        scoped_years = tuple(sorted(set(years)))
        if not scoped_years:
            return set()
        rows = self.session.execute(
            select(
                AssociationEntry.entity_id,
                AssociationEntry.periodo_ano,
                AssociationEntry.periodo_mes,
            ).where(AssociationEntry.periodo_ano.in_(scoped_years))
        )
        return {tuple(row) for row in rows}

    def get_by_key(
        self, entity_id: int, year: int, month: int
    ) -> AssociationEntry | None:
        return self.session.scalar(
            select(AssociationEntry).where(
                AssociationEntry.entity_id == entity_id,
                AssociationEntry.periodo_ano == year,
                AssociationEntry.periodo_mes == month,
            )
        )

    def list_by_year(self, year: int) -> list[AssociationEntry]:
        statement = (
            select(AssociationEntry)
            .options(selectinload(AssociationEntry.entity))
            .where(AssociationEntry.periodo_ano == year)
            .order_by(
                AssociationEntry.entity_id,
                AssociationEntry.periodo_mes,
            )
        )
        return list(self.session.scalars(statement))
