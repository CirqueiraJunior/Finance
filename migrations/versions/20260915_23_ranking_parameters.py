"""annual ranking parameters

Revision ID: 20260915_23
Revises: 20260914_22
"""

from alembic import op
import sqlalchemy as sa


revision = "20260915_23"
down_revision = "20260914_22"
branch_labels = None
depends_on = None


LEGACY_COLUMNS = (
    "id",
    "year",
    "billing_100_109",
    "billing_110_149",
    "billing_150_plus",
    "capture_1_7",
    "capture_8_15",
    "capture_16_plus",
    "cancellation_zero",
    "award_first",
    "award_second",
    "award_third",
    "created_at",
    "updated_at",
)


def _abort_legacy_drift(reason: str) -> None:
    raise RuntimeError(
        "Migration 20260915_23 abortada: a tabela ranking_parameters existente "
        f"não corresponde ao drift legado vazio conhecido ({reason}). Nenhuma tabela foi removida."
    )


def _assert_starting_revision(bind) -> None:
    revisions = bind.execute(sa.text("SELECT version_num FROM alembic_version")).scalars().all()
    if revisions != ["20260914_22"]:
        raise RuntimeError(
            "Migration 20260915_23 requer alembic_version 20260914_22; "
            f"estado encontrado: {revisions!r}."
        )


def _validate_and_remove_known_legacy_table(bind) -> None:
    if bind.dialect.name != "sqlite":
        _abort_legacy_drift(f"dialeto não reconhecido: {bind.dialect.name}")
    inspector = sa.inspect(bind)
    count = bind.scalar(sa.text("SELECT COUNT(*) FROM ranking_parameters"))
    if count != 0:
        _abort_legacy_drift(f"quantidade de registros: {count}")

    columns = inspector.get_columns("ranking_parameters")
    names = tuple(column["name"] for column in columns)
    if names != LEGACY_COLUMNS:
        _abort_legacy_drift(f"colunas encontradas: {names!r}")

    by_name = {column["name"]: column for column in columns}
    integer_columns = LEGACY_COLUMNS[0:9]
    if any(not isinstance(by_name[name]["type"], sa.Integer) for name in integer_columns):
        _abort_legacy_drift("uma coluna inteira possui tipo incompatível")
    if any(by_name[name]["nullable"] for name in integer_columns):
        _abort_legacy_drift("uma coluna inteira obrigatória aceita NULL")

    expected_defaults = {
        "id": None,
        "year": None,
        "billing_100_109": "5",
        "billing_110_149": "6",
        "billing_150_plus": "7",
        "capture_1_7": "2",
        "capture_8_15": "3",
        "capture_16_plus": "4",
        "cancellation_zero": "1",
        "award_first": "3000",
        "award_second": "2000",
        "award_third": "1000",
        "created_at": "CURRENT_TIMESTAMP",
        "updated_at": "CURRENT_TIMESTAMP",
    }
    for name, expected in expected_defaults.items():
        actual = by_name[name].get("default")
        normalized = None if actual is None else str(actual).strip("'\"() ").upper()
        if normalized != expected:
            _abort_legacy_drift(f"default incompatível em {name}: {actual!r}")

    for name in ("award_first", "award_second", "award_third"):
        column_type = by_name[name]["type"]
        if not isinstance(column_type, sa.Numeric):
            _abort_legacy_drift(f"{name} não é NUMERIC")
        if (column_type.precision, column_type.scale) != (14, 2):
            _abort_legacy_drift(f"{name} não possui precisão NUMERIC(14, 2)")
        if by_name[name]["nullable"]:
            _abort_legacy_drift(f"{name} aceita NULL")

    for name in ("created_at", "updated_at"):
        if not isinstance(by_name[name]["type"], sa.DateTime):
            _abort_legacy_drift(f"{name} não é DATETIME")
        if not by_name[name]["nullable"]:
            _abort_legacy_drift(f"{name} deveria aceitar NULL no schema legado")

    primary_key = inspector.get_pk_constraint("ranking_parameters")
    if primary_key.get("constrained_columns") != ["id"]:
        _abort_legacy_drift("chave primária diferente de id")

    unique_columns = {
        tuple(constraint.get("column_names") or ())
        for constraint in inspector.get_unique_constraints("ranking_parameters")
    }
    if unique_columns != {("year",)}:
        _abort_legacy_drift(f"constraints UNIQUE incompatíveis: {sorted(unique_columns)!r}")
    if inspector.get_foreign_keys("ranking_parameters"):
        _abort_legacy_drift("foreign key inesperada")
    if inspector.get_check_constraints("ranking_parameters"):
        _abort_legacy_drift("check constraint inesperada")

    indexes = {
        (index["name"], tuple(index["column_names"]), bool(index["unique"]))
        for index in inspector.get_indexes("ranking_parameters")
    }
    if indexes != {("ix_ranking_parameters_year", ("year",), False)}:
        _abort_legacy_drift(f"índices incompatíveis: {sorted(indexes)!r}")

    op.drop_table("ranking_parameters")


def _create_official_table():
    table = op.create_table(
        "ranking_parameters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("minimum_achievement_percent", sa.Numeric(9, 4), nullable=False),
        sa.Column("billing_level_1_min", sa.Numeric(9, 4), nullable=False),
        sa.Column("billing_level_1_points", sa.Integer(), nullable=False),
        sa.Column("billing_level_2_min", sa.Numeric(9, 4), nullable=False),
        sa.Column("billing_level_2_points", sa.Integer(), nullable=False),
        sa.Column("billing_level_3_min", sa.Numeric(9, 4), nullable=False),
        sa.Column("billing_level_3_points", sa.Integer(), nullable=False),
        sa.Column("acquisition_level_1_min", sa.Numeric(18, 4), nullable=False),
        sa.Column("acquisition_level_1_points", sa.Integer(), nullable=False),
        sa.Column("acquisition_level_2_min", sa.Numeric(18, 4), nullable=False),
        sa.Column("acquisition_level_2_points", sa.Integer(), nullable=False),
        sa.Column("acquisition_level_3_min", sa.Numeric(18, 4), nullable=False),
        sa.Column("acquisition_level_3_points", sa.Integer(), nullable=False),
        sa.Column("zero_cancellation_points", sa.Integer(), nullable=False),
        sa.Column("positive_cancellation_points", sa.Integer(), nullable=False),
        sa.Column("first_place_award", sa.Numeric(18, 2), nullable=False),
        sa.Column("second_place_award", sa.Numeric(18, 2), nullable=False),
        sa.Column("third_place_award", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("year BETWEEN 2000 AND 9999", name="ck_ranking_parameters_year"),
        sa.CheckConstraint("minimum_achievement_percent >= 0", name="ck_ranking_parameters_minimum_achievement"),
        sa.CheckConstraint(
            "billing_level_1_min >= 0 AND billing_level_1_min < billing_level_2_min "
            "AND billing_level_2_min < billing_level_3_min",
            name="ck_ranking_parameters_billing_levels",
        ),
        sa.CheckConstraint(
            "acquisition_level_1_min >= 0 AND acquisition_level_1_min < acquisition_level_2_min "
            "AND acquisition_level_2_min < acquisition_level_3_min",
            name="ck_ranking_parameters_acquisition_levels",
        ),
        sa.CheckConstraint(
            "billing_level_1_points >= 0 AND billing_level_2_points >= 0 "
            "AND billing_level_3_points >= 0 AND acquisition_level_1_points >= 0 "
            "AND acquisition_level_2_points >= 0 AND acquisition_level_3_points >= 0 "
            "AND zero_cancellation_points >= 0 AND positive_cancellation_points >= 0",
            name="ck_ranking_parameters_nonnegative_points",
        ),
        sa.CheckConstraint(
            "first_place_award >= 0 AND second_place_award >= 0 AND third_place_award >= 0",
            name="ck_ranking_parameters_nonnegative_awards",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", name="uq_ranking_parameters_year"),
    )
    op.create_index("ix_ranking_parameters_year", "ranking_parameters", ["year"])
    return table


def upgrade() -> None:
    bind = op.get_bind()
    _assert_starting_revision(bind)
    if sa.inspect(bind).has_table("ranking_parameters"):
        _validate_and_remove_known_legacy_table(bind)
    table = _create_official_table()
    op.bulk_insert(table, [{
        "year": 2026,
        "minimum_achievement_percent": 100,
        "billing_level_1_min": 100, "billing_level_1_points": 5,
        "billing_level_2_min": 110, "billing_level_2_points": 6,
        "billing_level_3_min": 150, "billing_level_3_points": 7,
        "acquisition_level_1_min": 1, "acquisition_level_1_points": 2,
        "acquisition_level_2_min": 8, "acquisition_level_2_points": 3,
        "acquisition_level_3_min": 16, "acquisition_level_3_points": 4,
        "zero_cancellation_points": 1,
        "positive_cancellation_points": 0,
        "first_place_award": 3000,
        "second_place_award": 2000,
        "third_place_award": 1000,
    }])


def downgrade() -> None:
    op.drop_index("ix_ranking_parameters_year", table_name="ranking_parameters")
    op.drop_table("ranking_parameters")
