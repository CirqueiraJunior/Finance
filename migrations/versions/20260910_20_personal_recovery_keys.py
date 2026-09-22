"""personal recovery keys

Revision ID: 20260910_20
Revises: 20260909_19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260910_20"
down_revision = "20260909_19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "personal_recovery_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_recovery_keys_user_id", "personal_recovery_keys", ["user_id"])
    op.create_index("ix_personal_recovery_keys_key_hash", "personal_recovery_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_personal_recovery_keys_key_hash", table_name="personal_recovery_keys")
    op.drop_index("ix_personal_recovery_keys_user_id", table_name="personal_recovery_keys")
    op.drop_table("personal_recovery_keys")
