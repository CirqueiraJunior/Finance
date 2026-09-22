"""Add mandatory first-login password change state.

Revision ID: 20260909_18
Revises: 20260907_17
"""

from alembic import op
import sqlalchemy as sa


revision = "20260909_18"
down_revision = "20260907_17"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "must_change_password",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("must_change_password")
