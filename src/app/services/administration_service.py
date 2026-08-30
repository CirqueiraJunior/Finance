from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.version import __version__
from app.models.boe_import import BOEImport
from app.models.cashflow_entry import CashflowEntry
from app.models.csv_export import CSVExport
from app.models.entity import Entity
from app.models.target_entry import TargetEntry


@dataclass(frozen=True, slots=True)
class SystemInformation:
    application: str
    environment: str
    version: str
    database: str
    alembic_revision: str
    log_directory: Path
    entities: int
    entries: int
    boe_imports: int
    targets: int
    exports: tuple[CSVExport, ...]


class AdministrationService:
    def __init__(self, session: Session, settings: Settings, engine: Engine) -> None:
        self.session, self.settings, self.engine = session, settings, engine

    def information(self) -> SystemInformation:
        revision = self.session.scalar(text("SELECT version_num FROM alembic_version"))
        exports = tuple(self.session.scalars(
            select(CSVExport).order_by(CSVExport.created_at.desc()).limit(20)
        ))
        return SystemInformation(
            self.settings.app_name, self.settings.app_env, __version__,
            self.engine.url.render_as_string(hide_password=True),
            str(revision or "não inicializado"), self.settings.log_dir,
            self._count(Entity), self._count(CashflowEntry), self._count(BOEImport),
            self._count(TargetEntry), exports,
        )

    def _count(self, model) -> int:
        return int(self.session.scalar(select(func.count()).select_from(model)) or 0)
