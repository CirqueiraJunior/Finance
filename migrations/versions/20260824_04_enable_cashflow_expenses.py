"""enable minimal cashflow expenses

Revision ID: 20260824_04
Revises: 20260824_03
Create Date: 2026-08-24
"""

from typing import Sequence

from alembic import op


revision: str = "20260824_04"
down_revision: str | None = "20260824_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPENSE_CATEGORY_SQL = (
    "'ADMINISTRATIVO', 'DIRETORIA', 'EVENTOS', 'OPERACIONAL', 'PESSOAL', "
    "'INVESTIMENTO', 'IMPOSTOS_E_TAXAS', 'SOFTWARE', 'VIAGEM', 'OUTROS'"
)


def upgrade() -> None:
    with op.batch_alter_table("cashflow_entries", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_cashflow_entries_type", type_="check")
        batch_op.drop_constraint("ck_cashflow_entries_category", type_="check")
        batch_op.drop_constraint(
            "ck_cashflow_entries_source_consistency", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_cashflow_entries_type", "tipo IN ('RECEITA', 'DESPESA')"
        )
        batch_op.create_check_constraint(
            "ck_cashflow_entries_category",
            "categoria IN ('RECEITA_DIRETA', 'RECEITA_INDIRETA', "
            f"{EXPENSE_CATEGORY_SQL})",
        )
        batch_op.create_check_constraint(
            "ck_cashflow_entries_source_consistency",
            "(tipo = 'RECEITA' AND origem = 'BOE' "
            "AND categoria = 'RECEITA_DIRETA' AND boe_import_id IS NOT NULL) OR "
            "(tipo = 'RECEITA' AND origem = 'MANUAL' "
            "AND categoria = 'RECEITA_INDIRETA' AND boe_import_id IS NULL) OR "
            "(tipo = 'DESPESA' AND origem = 'MANUAL' AND categoria IN ("
            f"{EXPENSE_CATEGORY_SQL}) AND boe_import_id IS NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("cashflow_entries", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_cashflow_entries_type", type_="check")
        batch_op.drop_constraint("ck_cashflow_entries_category", type_="check")
        batch_op.drop_constraint(
            "ck_cashflow_entries_source_consistency", type_="check"
        )
        batch_op.create_check_constraint(
            "ck_cashflow_entries_type", "tipo = 'RECEITA'"
        )
        batch_op.create_check_constraint(
            "ck_cashflow_entries_category",
            "categoria IN ('RECEITA_DIRETA', 'RECEITA_INDIRETA')",
        )
        batch_op.create_check_constraint(
            "ck_cashflow_entries_source_consistency",
            "(origem = 'BOE' AND categoria = 'RECEITA_DIRETA' "
            "AND boe_import_id IS NOT NULL) OR "
            "(origem = 'MANUAL' AND categoria = 'RECEITA_INDIRETA' "
            "AND boe_import_id IS NULL)",
        )
