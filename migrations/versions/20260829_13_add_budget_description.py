"""add description to budget entries

Revision ID: 20260829_13
Revises: 20260828_12
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_13"
down_revision = "20260828_12"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "budget_entries",
        sa.Column("descricao", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("budget_entries", "descricao")
