"""Permite FCDL 7600 exclusiva do contexto BOE.

Revision ID: 20260927_26
Revises: 20260927_25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260927_26"
down_revision = "20260927_25"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("boe_entity_totals") as batch_op:
        batch_op.alter_column(
            "entity_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.create_check_constraint(
            "ck_boe_entity_totals_entity_scope",
            (
                "(codigo_entidade_origem = 7600 AND entity_id IS NULL) "
                "OR "
                "(codigo_entidade_origem <> 7600 AND entity_id IS NOT NULL)"
            ),
        )


def downgrade() -> None:
    # O modelo anterior n?o consegue representar a FCDL sem Entity.
    # Remove apenas registros exclusivos do BOE antes de restaurar NOT NULL.
    op.execute(
        sa.text(
            "DELETE FROM boe_entity_totals "
            "WHERE codigo_entidade_origem = 7600 "
            "AND entity_id IS NULL"
        )
    )

    with op.batch_alter_table("boe_entity_totals") as batch_op:
        batch_op.drop_constraint(
            "ck_boe_entity_totals_entity_scope",
            type_="check",
        )
        batch_op.alter_column(
            "entity_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
