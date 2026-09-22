"""Add isolated technical financial balances.

Revision ID: 20260831_15
Revises: 20260830_14
"""
from alembic import op
import sqlalchemy as sa

revision = "20260831_15"
down_revision = "20260830_14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "financial_balance_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("balance_type", sa.String(30), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("year BETWEEN 2000 AND 9999", name="ck_financial_balance_year"),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_financial_balance_month"),
        sa.CheckConstraint("value >= 0", name="ck_financial_balance_value"),
        sa.CheckConstraint("balance_type IN ('SALDO_INICIAL', 'SALDO_APLICADO')",
                           name="ck_financial_balance_type"),
        sa.UniqueConstraint("year", "month", "balance_type",
                            name="uq_financial_balance_period_type"),
    )
    op.create_index("ix_financial_balance_entries_year", "financial_balance_entries", ["year"])


def downgrade() -> None:
    op.drop_index("ix_financial_balance_entries_year", table_name="financial_balance_entries")
    op.drop_table("financial_balance_entries")
