"""create target entries

Revision ID: 20260825_07
Revises: 20260824_06
Create Date: 2026-08-25
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260825_07"
down_revision: str | None = "20260824_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "target_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("periodo_ano", sa.Integer(), nullable=False),
        sa.Column("periodo_mes", sa.Integer(), nullable=False),
        sa.Column("indicador", sa.String(length=20), nullable=False),
        sa.Column("valor_meta", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("valor_realizado", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "periodo_ano BETWEEN 2000 AND 9999", name="ck_target_entries_year"
        ),
        sa.CheckConstraint(
            "periodo_mes BETWEEN 1 AND 12", name="ck_target_entries_month"
        ),
        sa.CheckConstraint(
            "indicador IN ('CONSULTAS', 'REGISTROS')",
            name="ck_target_entries_indicator",
        ),
        sa.CheckConstraint(
            "valor_meta >= 0", name="ck_target_entries_target_value"
        ),
        sa.CheckConstraint(
            "valor_realizado >= 0", name="ck_target_entries_actual_value"
        ),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_id",
            "periodo_ano",
            "periodo_mes",
            "indicador",
            name="uq_target_entries_entity_period_indicator",
        ),
    )
    op.create_index(
        op.f("ix_target_entries_entity_id"), "target_entries", ["entity_id"]
    )
    op.create_index(
        op.f("ix_target_entries_periodo_ano"), "target_entries", ["periodo_ano"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_target_entries_periodo_ano"), table_name="target_entries")
    op.drop_index(op.f("ix_target_entries_entity_id"), table_name="target_entries")
    op.drop_table("target_entries")
