from dataclasses import dataclass
import logging
from pathlib import Path

from sqlalchemy import Engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings


logger = logging.getLogger(__name__)
EXPECTED_SCHEMA_REVISION = "20260830_14"


@dataclass(frozen=True, slots=True)
class DatabaseStartupState:
    engine_name: str
    database_path: Path | None
    migration_revision: str


class DatabaseStartupError(RuntimeError):
    pass


def effective_sqlite_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    if not url.drivername.startswith("sqlite") or not url.database:
        return None
    if url.database == ":memory:":
        return None
    return Path(url.database).resolve()


def validate_database_startup(
    settings: Settings, engine: Engine
) -> DatabaseStartupState:
    """Valida conexão e schema sem criar ou aplicar migrations."""
    url = make_url(settings.database_url)
    is_sqlite = url.drivername.startswith("sqlite")
    engine_name = "SQLite" if is_sqlite else "PostgreSQL"
    database_path = effective_sqlite_path(settings.database_url)
    logger.info("Database engine: %s", engine_name)
    if database_path is not None:
        logger.info("Database path: %s", database_path)
        if not database_path.is_file():
            raise DatabaseStartupError(
                _message(database_path, "arquivo do banco não encontrado")
            )
    try:
        with engine.connect() as connection:
            table_names = set(inspect(connection).get_table_names())
            if "alembic_version" not in table_names:
                raise DatabaseStartupError(
                    _message(database_path, "banco sem controle de migrations")
                )
            revision = connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            if "entities" not in table_names:
                raise DatabaseStartupError(
                    _message(database_path, "schema incompleto: tabela entities ausente")
                )
            if revision != EXPECTED_SCHEMA_REVISION:
                raise DatabaseStartupError(
                    _message(
                        database_path,
                        f"migration atual {revision or 'ausente'}; "
                        f"esperada {EXPECTED_SCHEMA_REVISION}",
                    )
                )
    except DatabaseStartupError:
        raise
    except SQLAlchemyError as error:
        raise DatabaseStartupError(
            _message(database_path, f"falha de conexão: {error}")
        ) from error
    return DatabaseStartupState(
        engine_name, database_path, str(revision)
    )


def _message(database_path: Path | None, state: str) -> str:
    location = str(database_path) if database_path else "banco configurado"
    return (
        "Não foi possível iniciar o Finance. "
        f"Banco efetivo: {location}. Estado: {state}. "
        "Valide DATABASE_URL e execute com segurança, no workspace oficial: "
        "python -m alembic upgrade head"
    )
