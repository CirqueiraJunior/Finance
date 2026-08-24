"""create cashflow entries

Revision ID: 20260824_03
Revises: 20260824_02
Create Date: 2026-08-24
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_03"
down_revision: str | None = "20260824_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cashflow_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("periodo_ano", sa.Integer(), nullable=False),
        sa.Column("periodo_mes", sa.Integer(), nullable=False),
        sa.Column("data_lancamento", sa.Date(), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("valor", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("boe_import_id", sa.Integer(), nullable=True),
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
            "periodo_mes BETWEEN 1 AND 12", name="ck_cashflow_entries_month"
        ),
        sa.CheckConstraint(
            "periodo_ano BETWEEN 2000 AND 9999", name="ck_cashflow_entries_year"
        ),
        sa.CheckConstraint(
            "valor > 0", name="ck_cashflow_entries_positive_value"
        ),
        sa.CheckConstraint("tipo = 'RECEITA'", name="ck_cashflow_entries_type"),
        sa.CheckConstraint(
            "origem IN ('BOE', 'MANUAL')", name="ck_cashflow_entries_origin"
        ),
        sa.CheckConstraint(
            "categoria IN ('RECEITA_DIRETA', 'RECEITA_INDIRETA')",
            name="ck_cashflow_entries_category",
        ),
        sa.CheckConstraint(
            "(origem = 'BOE' AND categoria = 'RECEITA_DIRETA' "
            "AND boe_import_id IS NOT NULL) OR "
            "(origem = 'MANUAL' AND categoria = 'RECEITA_INDIRETA' "
            "AND boe_import_id IS NULL)",
            name="ck_cashflow_entries_source_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["boe_import_id"], ["boe_imports.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_cashflow_entries_boe_import_id"),
        "cashflow_entries",
        ["boe_import_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cashflow_entries_boe_import_id"),
        table_name="cashflow_entries",
    )
    op.drop_table("cashflow_entries")
