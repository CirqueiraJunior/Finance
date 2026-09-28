"""Allow historical manual direct revenue through January 2026.

Revision ID: 20260927_25
Revises: 20260922_24
"""

from alembic import op


revision = "20260927_25"
down_revision = "20260922_24"
branch_labels = None
depends_on = None


EXPENSE_SQL = (
    "'ADMINISTRATIVO', 'DIRETORIA', 'EVENTOS', 'OPERACIONAL', "
    "'PESSOAL', 'INVESTIMENTO', 'OUTROS'"
)


def _constraint(*, historical_until_cutover: bool) -> str:
    if historical_until_cutover:
        historical = (
            "(tipo = 'RECEITA' AND origem = 'MANUAL' "
            "AND categoria = 'RECEITA_DIRETA' "
            "AND (periodo_ano < 2026 OR "
            "(periodo_ano = 2026 AND periodo_mes = 1)) "
            "AND boe_import_id IS NULL) OR "
        )
    else:
        historical = (
            "(tipo = 'RECEITA' AND origem = 'MANUAL' "
            "AND categoria = 'RECEITA_DIRETA' "
            "AND periodo_ano = 2026 AND periodo_mes = 1 "
            "AND boe_import_id IS NULL) OR "
        )

    return (
        "(tipo = 'RECEITA' AND origem = 'BOE' "
        "AND categoria = 'RECEITA_DIRETA' "
        "AND boe_import_id IS NOT NULL) OR "
        "(tipo = 'RECEITA' AND origem = 'MANUAL' "
        "AND categoria = 'RECEITA_INDIRETA' "
        "AND boe_import_id IS NULL) OR "
        + historical
        + "(tipo = 'DESPESA' AND origem = 'MANUAL' "
        "AND categoria IN ("
        + EXPENSE_SQL
        + ") AND boe_import_id IS NULL)"
    )


def _replace_constraint(*, historical_until_cutover: bool) -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(
            "cashflow_entries",
            recreate="always",
        ) as batch_op:
            batch_op.drop_constraint(
                "ck_cashflow_entries_source_consistency",
                type_="check",
            )
            batch_op.create_check_constraint(
                "ck_cashflow_entries_source_consistency",
                _constraint(
                    historical_until_cutover=historical_until_cutover
                ),
            )
        return

    op.drop_constraint(
        "ck_cashflow_entries_source_consistency",
        "cashflow_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_cashflow_entries_source_consistency",
        "cashflow_entries",
        _constraint(
            historical_until_cutover=historical_until_cutover
        ),
    )


def upgrade() -> None:
    _replace_constraint(historical_until_cutover=True)


def downgrade() -> None:
    _replace_constraint(historical_until_cutover=False)
