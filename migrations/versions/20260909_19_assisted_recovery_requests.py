"""Add assisted recovery requests for Finance.

Revision ID: 20260909_19
Revises: 20260909_18
"""

from alembic import op
import sqlalchemy as sa


revision = "20260909_19"
down_revision = "20260909_18"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assisted_recovery_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(length=96), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", name="uq_assisted_recovery_request_id"),
    )
    op.create_index(
        "ix_assisted_recovery_requests_request_id",
        "assisted_recovery_requests",
        ["request_id"],
        unique=True,
    )
    op.create_index(
        "ix_assisted_recovery_requests_user_id",
        "assisted_recovery_requests",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assisted_recovery_requests_user_id",
        table_name="assisted_recovery_requests",
    )
    op.drop_index(
        "ix_assisted_recovery_requests_request_id",
        table_name="assisted_recovery_requests",
    )
    op.drop_table("assisted_recovery_requests")
