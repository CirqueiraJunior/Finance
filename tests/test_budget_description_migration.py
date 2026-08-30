from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from app.core.config import get_settings


def test_upgrade_preserves_existing_budget_with_null_description(tmp_path, monkeypatch):
    database = tmp_path / "legacy_budget.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "20260828_12")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO budget_entries "
            "(periodo_ano, periodo_mes, tipo, categoria, valor_orcado) "
            "VALUES (2026, 8, 'DESPESA', 'ADMINISTRATIVO', 100)"
        ))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(text(
            "SELECT descricao, valor_orcado FROM budget_entries"
        )).one()
    assert row.descricao is None
    assert row.valor_orcado == 100
    engine.dispose()
    get_settings.cache_clear()
