from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.csv_export import CSVExport
from app.repositories.base import BaseRepository


class CSVExportRepository(BaseRepository[CSVExport]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def add(self, export: CSVExport) -> CSVExport:
        self.session.add(export)
        self.session.flush()
        return export

    def list_recent(self, limit: int = 20) -> list[CSVExport]:
        statement = (
            select(CSVExport)
            .order_by(CSVExport.created_at.desc(), CSVExport.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))
