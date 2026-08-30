"""cashflow authorship and optimistic concurrency

Revision ID: 20260828_12
Revises: 20260828_11
"""

from alembic import op
import sqlalchemy as sa

revision = "20260828_12"
down_revision = "20260828_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cashflow_entries") as batch:
        batch.add_column(sa.Column("created_by_user_id", sa.Integer()))
        batch.add_column(sa.Column("updated_by_user_id", sa.Integer()))
        batch.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_index("ix_cashflow_entries_created_by_user_id", ["created_by_user_id"])
        batch.create_index("ix_cashflow_entries_updated_by_user_id", ["updated_by_user_id"])


def downgrade() -> None:
    with op.batch_alter_table("cashflow_entries") as batch:
        batch.drop_index("ix_cashflow_entries_updated_by_user_id")
        batch.drop_index("ix_cashflow_entries_created_by_user_id")
        batch.drop_column("version")
        batch.drop_column("updated_by_user_id")
        batch.drop_column("created_by_user_id")
