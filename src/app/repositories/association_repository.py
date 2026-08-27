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
