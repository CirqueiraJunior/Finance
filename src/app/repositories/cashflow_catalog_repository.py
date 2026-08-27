from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cashflow_catalog_entry import CashflowCatalogEntry
from app.repositories.base import BaseRepository


class CashflowCatalogRepository(BaseRepository[CashflowCatalogEntry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def list_active(self) -> list[CashflowCatalogEntry]:
        statement = (
            select(CashflowCatalogEntry)
            .where(CashflowCatalogEntry.ativa.is_(True))
            .order_by(
                CashflowCatalogEntry.descricao,
                CashflowCatalogEntry.categoria,
                CashflowCatalogEntry.tipo,
            )
        )
        return list(self.session.scalars(statement))

    def list_by_description(self, description: str) -> list[CashflowCatalogEntry]:
        statement = (
            select(CashflowCatalogEntry)
            .where(
                CashflowCatalogEntry.ativa.is_(True),
                CashflowCatalogEntry.descricao == description,
            )
            .order_by(CashflowCatalogEntry.categoria, CashflowCatalogEntry.tipo)
        )
        return list(self.session.scalars(statement))
