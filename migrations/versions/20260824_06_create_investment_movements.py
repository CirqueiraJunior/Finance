"""create investment movements

Revision ID: 20260824_06
Revises: 20260824_05
Create Date: 2026-08-24
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260824_06"
down_revision: str | None = "20260824_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investment_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("data_movimento", sa.Date(), nullable=False),
        sa.Column("periodo_ano", sa.Integer(), nullable=False),
        sa.Column("periodo_mes", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        sa.Column("valor", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("periodo_ano BETWEEN 2000 AND 9999", name="ck_investment_year"),
        sa.CheckConstraint("periodo_mes BETWEEN 1 AND 12", name="ck_investment_month"),
        sa.CheckConstraint("tipo IN ('APLICACAO', 'RESGATE')", name="ck_investment_type"),
        sa.CheckConstraint("valor > 0", name="ck_investment_value"),
        sa.CheckConstraint("length(trim(descricao)) > 0", name="ck_investment_description"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("investment_movements")
