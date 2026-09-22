"""remove duplicate assisted recovery request unique constraint

Revision ID: 20260922_24
Revises: 20260915_23
"""

from alembic import op


revision = "20260922_24"
down_revision = "20260915_23"
branch_labels = None
depends_on = None

_CONSTRAINT = "uq_assisted_recovery_request_id"
_TABLE = "assisted_recovery_requests"


def upgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.drop_constraint(_CONSTRAINT, type_="unique")
    else:
        op.drop_constraint(_CONSTRAINT, _TABLE, type_="unique")


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.create_unique_constraint(_CONSTRAINT, ["request_id"])
    else:
        op.create_unique_constraint(
            _CONSTRAINT,
            _TABLE,
            ["request_id"],
        )
