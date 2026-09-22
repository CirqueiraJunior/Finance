"""add entity region

Revision ID: 20260914_22
Revises: 20260910_21
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_22"
down_revision = "20260910_21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "entities",
        sa.Column("regiao", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    with op.batch_alter_table("entities") as batch_op:
        batch_op.drop_column("regiao")
