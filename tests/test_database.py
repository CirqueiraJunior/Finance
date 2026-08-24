from sqlalchemy import text

from app.database.session import get_engine


def test_database_engine_executes_query() -> None:
    with get_engine().connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1

