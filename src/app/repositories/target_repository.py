from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.target_entry import TargetEntry
from app.repositories.base import BaseRepository


class TargetRepository(BaseRepository[TargetEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def add(self, target: TargetEntry) -> TargetEntry:
        self.session.add(target)
        self.session.flush()
        return target

    def get_by_id(self, target_id: int) -> TargetEntry | None:
        return self.session.scalar(
            select(TargetEntry)
            .options(selectinload(TargetEntry.entity))
            .where(TargetEntry.id == target_id)
        )

    def get_by_key(
        self, entity_id: int, year: int, month: int, indicator: str
    ) -> TargetEntry | None:
        return self.session.scalar(
            select(TargetEntry).where(
                TargetEntry.entity_id == entity_id,
                TargetEntry.periodo_ano == year,
                TargetEntry.periodo_mes == month,
                TargetEntry.indicador == indicator,
            )
        )

    def exists(self, entity_id: int, year: int, month: int, indicator: str) -> bool:
        return self.get_by_key(entity_id, year, month, indicator) is not None

    def list_all(self) -> list[TargetEntry]:
        return self._list(select(TargetEntry))

    def list_by_period(self, year: int, month: int) -> list[TargetEntry]:
        return self._list(
            select(TargetEntry).where(
                TargetEntry.periodo_ano == year,
                TargetEntry.periodo_mes == month,
            )
        )

    def list_by_entity(self, entity_id: int) -> list[TargetEntry]:
        return self._list(
            select(TargetEntry).where(TargetEntry.entity_id == entity_id)
        )

    def list_by_year(self, year: int) -> list[TargetEntry]:
        return self._list(
            select(TargetEntry).where(TargetEntry.periodo_ano == year)
        )

    @staticmethod
    def _ordered(statement):
        return statement.order_by(
            TargetEntry.periodo_ano,
            TargetEntry.periodo_mes,
            TargetEntry.indicador,
            TargetEntry.entity_id,
        )

    def _list(self, statement) -> list[TargetEntry]:
        statement = self._ordered(statement).options(selectinload(TargetEntry.entity))
        return list(self.session.scalars(statement))
