"""add association cancellations

Revision ID: 20260828_10
Revises: 20260827_09
"""

from alembic import op
import sqlalchemy as sa

revision = "20260828_10"
down_revision = "20260827_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("association_entries") as batch:
        batch.add_column(sa.Column(
            "valor_cancelamento", sa.Numeric(18, 4),
            server_default="0.0000", nullable=False,
        ))
        batch.create_check_constraint(
            "ck_association_entries_cancellation", "valor_cancelamento >= 0"
        )


def downgrade() -> None:
    with op.batch_alter_table("association_entries") as batch:
        batch.drop_constraint(
            "ck_association_entries_cancellation", type_="check"
        )
        batch.drop_column("valor_cancelamento")
