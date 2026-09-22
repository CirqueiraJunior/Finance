"""Guard the cashflow primary-key sequence after historical batch recreation.

Revision ID: 20260907_16
Revises: 20260831_15
"""

from alembic import op
import sqlalchemy as sa


revision = "20260907_16"
down_revision = "20260831_15"
branch_labels = None
depends_on = None


def synchronize_postgresql_sequence(connection, table_name: str, column_name: str) -> None:
    """Move a PostgreSQL-owned generator to the table maximum, if one exists."""
    if connection.dialect.name != "postgresql":
        return

    sequence_name = connection.scalar(
        sa.text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
        {"table_name": table_name, "column_name": column_name},
    )
    if sequence_name is None:
        raise RuntimeError(
            f"{table_name}.{column_name} não possui sequence PostgreSQL vinculada"
        )

    # The identifiers below are migration-owned constants, not external input.
    connection.execute(
        sa.text(
            f"SELECT setval(CAST(:sequence_name AS regclass), "
            f"COALESCE(MAX({column_name}), 1), MAX({column_name}) IS NOT NULL) "
            f"FROM {table_name}"
        ),
        {"sequence_name": sequence_name},
    )


def upgrade() -> None:
    synchronize_postgresql_sequence(op.get_bind(), "cashflow_entries", "id")


def downgrade() -> None:
    # Sequence synchronization is data-preserving and intentionally irreversible.
    pass
