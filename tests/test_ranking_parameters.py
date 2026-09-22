from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.models.ranking_parameter import RankingParameter


LEGACY_COLUMNS = (
    "id", "year", "billing_100_109", "billing_110_149", "billing_150_plus",
    "capture_1_7", "capture_8_15", "capture_16_plus", "cancellation_zero",
    "award_first", "award_second", "award_third", "created_at", "updated_at",
)


def _database(tmp_path, monkeypatch, name="ranking-parameters.db"):
    database = tmp_path / name
    url = f"sqlite:///{database.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "20260914_22")
    return url, config


def _create_legacy(engine, *, extra_column=False, missing_column=None, with_row=False):
    definitions = {
        "id": "id INTEGER NOT NULL PRIMARY KEY",
        "year": "year INTEGER NOT NULL",
        "billing_100_109": "billing_100_109 INTEGER DEFAULT '5' NOT NULL",
        "billing_110_149": "billing_110_149 INTEGER DEFAULT '6' NOT NULL",
        "billing_150_plus": "billing_150_plus INTEGER DEFAULT '7' NOT NULL",
        "capture_1_7": "capture_1_7 INTEGER DEFAULT '2' NOT NULL",
        "capture_8_15": "capture_8_15 INTEGER DEFAULT '3' NOT NULL",
        "capture_16_plus": "capture_16_plus INTEGER DEFAULT '4' NOT NULL",
        "cancellation_zero": "cancellation_zero INTEGER DEFAULT '1' NOT NULL",
        "award_first": "award_first NUMERIC(14, 2) DEFAULT '3000' NOT NULL",
        "award_second": "award_second NUMERIC(14, 2) DEFAULT '2000' NOT NULL",
        "award_third": "award_third NUMERIC(14, 2) DEFAULT '1000' NOT NULL",
        "created_at": "created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
        "updated_at": "updated_at DATETIME DEFAULT CURRENT_TIMESTAMP",
    }
    columns = [definitions[name] for name in LEGACY_COLUMNS if name != missing_column]
    if extra_column:
        columns.append("unexpected INTEGER")
    columns.append("CONSTRAINT uq_ranking_parameters_year UNIQUE (year)")
    with engine.begin() as connection:
        connection.execute(text(f"CREATE TABLE ranking_parameters ({', '.join(columns)})"))
        connection.execute(text(
            "CREATE INDEX ix_ranking_parameters_year ON ranking_parameters (year)"
        ))
        if with_row:
            connection.execute(text("INSERT INTO ranking_parameters (id, year) VALUES (1, 2026)"))


def _assert_official_seed(engine):
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260915_23"
        columns = {column["name"] for column in inspect(connection).get_columns("ranking_parameters")}
        assert "minimum_achievement_percent" in columns
        assert "billing_100_109" not in columns
        row = connection.execute(text(
            "SELECT * FROM ranking_parameters WHERE year = 2026"
        )).mappings().one()
        assert Decimal(str(row["minimum_achievement_percent"])) == Decimal("100")
        assert [Decimal(str(row[f"billing_level_{level}_min"])) for level in (1, 2, 3)] == [
            Decimal("100"), Decimal("110"), Decimal("150"),
        ]
        assert [row[f"billing_level_{level}_points"] for level in (1, 2, 3)] == [5, 6, 7]
        assert [Decimal(str(row[f"acquisition_level_{level}_min"])) for level in (1, 2, 3)] == [
            Decimal("1"), Decimal("8"), Decimal("16"),
        ]
        assert [row[f"acquisition_level_{level}_points"] for level in (1, 2, 3)] == [2, 3, 4]
        assert row["zero_cancellation_points"] == 1
        assert row["positive_cancellation_points"] == 0
        assert [Decimal(str(row[name])) for name in (
            "first_place_award", "second_place_award", "third_place_award",
        )] == [Decimal("3000"), Decimal("2000"), Decimal("1000")]


def test_clean_22_upgrade_creates_official_schema_and_seed(tmp_path, monkeypatch):
    url, config = _database(tmp_path, monkeypatch)
    engine = create_engine(url)
    try:
        command.upgrade(config, "20260915_23")
        _assert_official_seed(engine)
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text(
                    "INSERT INTO ranking_parameters (year, minimum_achievement_percent, "
                    "billing_level_1_min, billing_level_1_points, billing_level_2_min, "
                    "billing_level_2_points, billing_level_3_min, billing_level_3_points, "
                    "acquisition_level_1_min, acquisition_level_1_points, "
                    "acquisition_level_2_min, acquisition_level_2_points, "
                    "acquisition_level_3_min, acquisition_level_3_points, "
                    "zero_cancellation_points, positive_cancellation_points, "
                    "first_place_award, second_place_award, third_place_award) "
                    "SELECT 2026, minimum_achievement_percent, billing_level_1_min, "
                    "billing_level_1_points, billing_level_2_min, billing_level_2_points, "
                    "billing_level_3_min, billing_level_3_points, acquisition_level_1_min, "
                    "acquisition_level_1_points, acquisition_level_2_min, "
                    "acquisition_level_2_points, acquisition_level_3_min, "
                    "acquisition_level_3_points, zero_cancellation_points, "
                    "positive_cancellation_points, first_place_award, second_place_award, "
                    "third_place_award FROM ranking_parameters WHERE year = 2026"
                ))
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_exact_empty_legacy_drift_is_replaced(tmp_path, monkeypatch):
    url, config = _database(tmp_path, monkeypatch)
    engine = create_engine(url)
    try:
        _create_legacy(engine)
        command.upgrade(config, "20260915_23")
        _assert_official_seed(engine)
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.mark.parametrize("variant", ["row", "extra", "missing", "official"])
def test_unrecognized_existing_table_aborts_without_drop(tmp_path, monkeypatch, variant):
    url, config = _database(tmp_path, monkeypatch, f"ranking-{variant}.db")
    engine = create_engine(url)
    try:
        if variant == "official":
            RankingParameter.__table__.create(engine)
        else:
            _create_legacy(
                engine,
                with_row=variant == "row",
                extra_column=variant == "extra",
                missing_column="capture_16_plus" if variant == "missing" else None,
            )
        before_columns = tuple(
            column["name"] for column in inspect(engine).get_columns("ranking_parameters")
        )
        with engine.connect() as connection:
            before_count = connection.scalar(text("SELECT COUNT(*) FROM ranking_parameters"))

        with pytest.raises(RuntimeError, match="Nenhuma tabela foi removida"):
            command.upgrade(config, "20260915_23")

        assert tuple(
            column["name"] for column in inspect(engine).get_columns("ranking_parameters")
        ) == before_columns
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT COUNT(*) FROM ranking_parameters")) == before_count
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260914_22"
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_downgrade_removes_only_official_table_and_clean_cycle_repeats(tmp_path, monkeypatch):
    url, config = _database(tmp_path, monkeypatch)
    engine = create_engine(url)
    try:
        command.upgrade(config, "20260915_23")
        command.downgrade(config, "20260914_22")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20260914_22"
            assert not inspect(connection).has_table("ranking_parameters")

        command.upgrade(config, "20260915_23")
        _assert_official_seed(engine)
    finally:
        engine.dispose()
        get_settings.cache_clear()
