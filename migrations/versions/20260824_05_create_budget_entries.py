"""create budget entries

Revision ID: 20260824_05
Revises: 20260824_04
Create Date: 2026-08-24
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_05"
down_revision: str | None = "20260824_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "budget_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("periodo_ano", sa.Integer(), nullable=False),
        sa.Column("periodo_mes", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("valor_orcado", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.CheckConstraint(
            "periodo_ano BETWEEN 2000 AND 9999", name="ck_budget_entries_year"
        ),
        sa.CheckConstraint(
            "periodo_mes BETWEEN 1 AND 12", name="ck_budget_entries_month"
        ),
        sa.CheckConstraint(
            "tipo IN ('RECEITA', 'DESPESA')", name="ck_budget_entries_type"
        ),
        sa.CheckConstraint("valor_orcado >= 0", name="ck_budget_entries_value"),
        sa.CheckConstraint(
            "(tipo = 'RECEITA' AND categoria IN "
            "('RECEITA_DIRETA', 'RECEITA_INDIRETA')) OR "
            "(tipo = 'DESPESA' AND categoria IN "
            "('ADMINISTRATIVO', 'DIRETORIA', 'EVENTOS', 'OPERACIONAL', "
            "'PESSOAL', 'INVESTIMENTO', 'IMPOSTOS_E_TAXAS', 'SOFTWARE', "
            "'VIAGEM', 'OUTROS'))",
            name="ck_budget_entries_type_category",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "periodo_ano", "periodo_mes", "tipo", "categoria",
            name="uq_budget_entries_period_type_category",
        ),
    )


def downgrade() -> None:
    op.drop_table("budget_entries")
