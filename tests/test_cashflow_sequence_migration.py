import importlib.util
from pathlib import Path
from types import SimpleNamespace

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import get_settings


ROOT = Path(__file__).resolve().parents[1]


def _load_guard_migration():
    path = ROOT / "migrations/versions/20260907_16_guard_cashflow_sequence.py"
    spec = importlib.util.spec_from_file_location("cashflow_sequence_guard", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakePostgresqlConnection:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, sequence_name="public._alembic_tmp_cashflow_entries_id_seq1"):
        self.sequence_name = sequence_name
        self.calls = []

    def scalar(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        return self.sequence_name

    def execute(self, statement, parameters):
        self.calls.append((str(statement), parameters))


def test_postgresql_guard_discovers_owned_sequence_and_synchronizes_to_maximum():
    migration = _load_guard_migration()
    connection = _FakePostgresqlConnection()

    migration.synchronize_postgresql_sequence(connection, "cashflow_entries", "id")

    assert "pg_get_serial_sequence" in connection.calls[0][0]
    assert connection.calls[0][1] == {
        "table_name": "cashflow_entries",
        "column_name": "id",
    }
    synchronization_sql, parameters = connection.calls[1]
    assert "COALESCE(MAX(id), 1)" in synchronization_sql
    assert "MAX(id) IS NOT NULL" in synchronization_sql
    assert parameters["sequence_name"].endswith("_cashflow_entries_id_seq1")


def test_non_postgresql_guard_is_a_noop():
    migration = _load_guard_migration()
    connection = _FakePostgresqlConnection()
    connection.dialect.name = "sqlite"

    migration.synchronize_postgresql_sequence(connection, "cashflow_entries", "id")

    assert connection.calls == []


def test_sqlite_batch_recreation_keeps_next_primary_key_above_existing_max(
    tmp_path, monkeypatch
):
    database = tmp_path / "cashflow_sequence.db"
    database_url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "20260824_03")
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO cashflow_entries "
            "(id, periodo_ano, periodo_mes, data_lancamento, descricao, tipo, "
            "origem, categoria, valor) VALUES "
            "(4, 2026, 8, '2026-08-01', 'Legado', 'RECEITA', "
            "'MANUAL', 'RECEITA_INDIRETA', 10)"
        ))

    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO cashflow_entries "
            "(periodo_ano, periodo_mes, data_lancamento, descricao, tipo, "
            "origem, categoria, valor) VALUES "
            "(2026, 9, '2026-09-01', 'Novo', 'RECEITA', "
            "'MANUAL', 'RECEITA_INDIRETA', 20)"
        ))
        ids = connection.scalars(text(
            "SELECT id FROM cashflow_entries ORDER BY id"
        )).all()

    assert ids == [4, 5]
    engine.dispose()
    get_settings.cache_clear()
