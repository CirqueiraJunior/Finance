"""Restrict cashflow and budget to official spreadsheet categories.

Revision ID: 20260830_14
Revises: 20260829_13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260830_14"
down_revision = "20260829_13"
branch_labels = None
depends_on = None


EXPENSE_SQL = (
    "'ADMINISTRATIVO', 'DIRETORIA', 'EVENTOS', 'OPERACIONAL', "
    "'PESSOAL', 'INVESTIMENTO', 'OUTROS'"
)


def upgrade() -> None:
    connection = op.get_bind()

    # Mapeamentos inequívocos da planilha oficial.
    connection.execute(sa.text(
        "UPDATE cashflow_entries SET categoria = 'ADMINISTRATIVO' "
        "WHERE categoria IN ('SOFTWARE', 'IMPOSTOS_E_TAXAS')"
    ))
    connection.execute(sa.text(
        "UPDATE budget_entries SET categoria = 'ADMINISTRATIVO' "
        "WHERE categoria IN ('SOFTWARE', 'IMPOSTOS_E_TAXAS')"
    ))

    # VIAGEM é descrição oficial com múltiplas categorias possíveis.
    # Nunca remapear silenciosamente.
    cashflow_travel = connection.execute(sa.text(
        "SELECT COUNT(*) FROM cashflow_entries WHERE categoria = 'VIAGEM'"
    )).scalar_one()
    budget_travel = connection.execute(sa.text(
        "SELECT COUNT(*) FROM budget_entries WHERE categoria = 'VIAGEM'"
    )).scalar_one()

    if cashflow_travel or budget_travel:
        raise RuntimeError(
            "Existem registros legados com categoria VIAGEM. "
            "Corrija manualmente para DIRETORIA, EVENTOS ou OPERACIONAL."
        )

    with op.batch_alter_table("cashflow_entries", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_cashflow_entries_category", type_="check"
        )
        batch_op.drop_constraint(
            "ck_cashflow_entries_source_consistency", type_="check"
        )

        batch_op.create_check_constraint(
            "ck_cashflow_entries_category",
            "categoria IN ("
            "'RECEITA_DIRETA', 'RECEITA_INDIRETA', "
            + EXPENSE_SQL +
            ")",
        )

        batch_op.create_check_constraint(
            "ck_cashflow_entries_source_consistency",
            "(tipo = 'RECEITA' AND origem = 'BOE' "
            "AND categoria = 'RECEITA_DIRETA' "
            "AND boe_import_id IS NOT NULL) OR "
            "(tipo = 'RECEITA' AND origem = 'MANUAL' "
            "AND categoria = 'RECEITA_INDIRETA' "
            "AND boe_import_id IS NULL) OR "
            "(tipo = 'DESPESA' AND origem = 'MANUAL' "
            "AND categoria IN (" + EXPENSE_SQL + ") "
            "AND boe_import_id IS NULL)",
        )

    with op.batch_alter_table("budget_entries", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_budget_entries_type_category", type_="check"
        )

        batch_op.create_check_constraint(
            "ck_budget_entries_type_category",
            "(tipo = 'RECEITA' AND categoria IN "
            "('RECEITA_DIRETA', 'RECEITA_INDIRETA')) OR "
            "(tipo = 'DESPESA' AND categoria IN (" + EXPENSE_SQL + "))",
        )


def downgrade() -> None:
    legacy_expense_sql = (
        "'ADMINISTRATIVO', 'DIRETORIA', 'EVENTOS', 'OPERACIONAL', "
        "'PESSOAL', 'INVESTIMENTO', 'IMPOSTOS_E_TAXAS', "
        "'SOFTWARE', 'VIAGEM', 'OUTROS'"
    )

    with op.batch_alter_table("cashflow_entries", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_cashflow_entries_category", type_="check"
        )
        batch_op.drop_constraint(
            "ck_cashflow_entries_source_consistency", type_="check"
        )

        batch_op.create_check_constraint(
            "ck_cashflow_entries_category",
            "categoria IN ("
            "'RECEITA_DIRETA', 'RECEITA_INDIRETA', "
            + legacy_expense_sql +
            ")",
        )

        batch_op.create_check_constraint(
            "ck_cashflow_entries_source_consistency",
            "(tipo = 'RECEITA' AND origem = 'BOE' "
            "AND categoria = 'RECEITA_DIRETA' "
            "AND boe_import_id IS NOT NULL) OR "
            "(tipo = 'RECEITA' AND origem = 'MANUAL' "
            "AND categoria = 'RECEITA_INDIRETA' "
            "AND boe_import_id IS NULL) OR "
            "(tipo = 'DESPESA' AND origem = 'MANUAL' "
            "AND categoria IN (" + legacy_expense_sql + ") "
            "AND boe_import_id IS NULL)",
        )

    with op.batch_alter_table("budget_entries", recreate="always") as batch_op:
        batch_op.drop_constraint(
            "ck_budget_entries_type_category", type_="check"
        )

        batch_op.create_check_constraint(
            "ck_budget_entries_type_category",
            "(tipo = 'RECEITA' AND categoria IN "
            "('RECEITA_DIRETA', 'RECEITA_INDIRETA')) OR "
            "(tipo = 'DESPESA' AND categoria IN ("
            + legacy_expense_sql +
            "))",
        )
