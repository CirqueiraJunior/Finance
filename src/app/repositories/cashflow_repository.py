from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.cashflow_entry import CashflowEntry
from app.repositories.base import BaseRepository


class CashflowRepository(BaseRepository[CashflowEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_id(self, entry_id: int) -> CashflowEntry | None:
        return self.session.scalar(
            select(CashflowEntry)
            .options(selectinload(CashflowEntry.boe_import))
            .where(CashflowEntry.id == entry_id)
        )

    def get_by_boe_import_id(self, boe_import_id: int) -> CashflowEntry | None:
        return self.session.scalar(
            select(CashflowEntry).where(CashflowEntry.boe_import_id == boe_import_id)
        )

    def exists_for_boe_import(self, boe_import_id: int) -> bool:
        return self.session.scalar(
            select(CashflowEntry.id).where(CashflowEntry.boe_import_id == boe_import_id)
        ) is not None

    def add(self, entry: CashflowEntry) -> CashflowEntry:
        self.session.add(entry)
        self.session.flush()
        return entry

    def list_all(self) -> list[CashflowEntry]:
        statement = select(CashflowEntry).order_by(
            CashflowEntry.data_lancamento.desc(), CashflowEntry.id.desc()
        )
        return list(self.session.scalars(statement))

    def list_by_period(self, year: int, month: int) -> list[CashflowEntry]:
        statement = (
            select(CashflowEntry)
            .where(CashflowEntry.periodo_ano == year, CashflowEntry.periodo_mes == month)
            .order_by(CashflowEntry.data_lancamento, CashflowEntry.id)
        )
        return list(self.session.scalars(statement))
