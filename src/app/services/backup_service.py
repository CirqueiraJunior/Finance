from datetime import datetime
import logging
from pathlib import Path
import sqlite3

from sqlalchemy.engine import make_url

from app.core.config import PROJECT_ROOT, Settings


logger = logging.getLogger(__name__)


class BackupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_manual_backup(self) -> Path:
        return self._create(PROJECT_ROOT / "backups" / "manual")

    def create_import_backup(self) -> Path:
        return self._create(PROJECT_ROOT / "backups" / "imports")

    def _create(self, directory: Path) -> Path:
        url = make_url(self.settings.database_url)
        if not url.drivername.startswith("sqlite") or not url.database:
            raise ValueError("O backup local está disponível somente para SQLite.")
        source = Path(url.database)
        if not source.is_absolute():
            source = (PROJECT_ROOT / source).resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Banco SQLite não encontrado: {source}")
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destination = directory / f"ja_finance_{stamp}.db"
        if destination.exists():
            raise FileExistsError("O arquivo de backup já existe.")
        with sqlite3.connect(source) as source_db, sqlite3.connect(destination) as target_db:
            source_db.backup(target_db)
        if not destination.is_file() or destination.stat().st_size == 0:
            destination.unlink(missing_ok=True)
            raise OSError("A cópia do banco não foi concluída.")
        logger.info("Backup criado com sucesso: %s", destination)
        return destination
