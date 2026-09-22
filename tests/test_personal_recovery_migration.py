from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.core.config import get_settings


def test_personal_recovery_migration_preserves_users_and_starts_without_keys(tmp_path, monkeypatch):
    database = tmp_path / "personal-recovery.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    get_settings.cache_clear()
    try:
        config = Config("alembic.ini")
        command.upgrade(config, "20260909_19")
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (nome, email, username, password_hash, perfil, ativo, "
                "must_change_password) VALUES ('Existente', 'existing@example.com', "
                "'existing', 'hash', 'ADMINISTRADOR', 1, 0)"
            ))
        engine.dispose()

        command.upgrade(config, "20260910_20")
        engine = create_engine(f"sqlite:///{database.as_posix()}")
        with engine.connect() as connection:
            assert "personal_recovery_keys" in inspect(connection).get_table_names()
            assert connection.scalar(text("SELECT COUNT(*) FROM users")) == 1
            assert connection.scalar(text("SELECT COUNT(*) FROM personal_recovery_keys")) == 0
        engine.dispose()
    finally:
        get_settings.cache_clear()
