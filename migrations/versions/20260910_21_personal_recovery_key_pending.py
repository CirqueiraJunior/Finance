"""personal recovery key pending

Revision ID: 20260910_21
Revises: 20260910_20
"""

from alembic import op
import sqlalchemy as sa


revision = "20260910_21"
down_revision = "20260910_20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "personal_recovery_key_pending",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("personal_recovery_key_pending")
