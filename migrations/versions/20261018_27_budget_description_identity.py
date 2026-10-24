"""Allow detailed budgets by normalized description.

Revision ID: 20261018_27
Revises: 20260927_26
"""

from alembic import op
import sqlalchemy as sa

revision = "20261018_27"
down_revision = "20260927_26"
branch_labels = None
depends_on = None

TABLE = "budget_entries"
OLD = "uq_budget_entries_period_type_category"
NEW = "uq_budget_entries_period_type_category_description"
KEY = ["periodo_ano", "periodo_mes", "tipo", "categoria"]


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(TABLE) as batch:
            batch.drop_constraint(OLD, type_="unique")
    else:
        op.drop_constraint(OLD, TABLE, type_="unique")

    op.create_index(
        NEW,
        TABLE,
        KEY + [sa.text("lower(trim(coalesce(descricao, '')))")],
        unique=True,
    )


def downgrade():
    bind = op.get_bind()
    duplicates = bind.execute(sa.text("""
        SELECT 1 FROM budget_entries
        GROUP BY periodo_ano, periodo_mes, tipo, categoria
        HAVING COUNT(*) > 1
        LIMIT 1
    """)).first()
    if duplicates:
        raise RuntimeError(
            "Detailed budgets exist; consolidate before downgrade."
        )

    op.drop_index(NEW, table_name=TABLE)
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(TABLE) as batch:
            batch.create_unique_constraint(OLD, KEY)
    else:
        op.create_unique_constraint(OLD, TABLE, KEY)
