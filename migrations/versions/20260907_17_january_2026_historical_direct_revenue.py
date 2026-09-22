"""Allow the one-time January 2026 historical direct revenue.

Revision ID: 20260907_17
Revises: 20260907_16
"""

from alembic import op


revision = "20260907_17"
down_revision = "20260907_16"
branch_labels = None
depends_on = None


EXPENSE_SQL = (
    "'ADMINISTRATIVO', 'DIRETORIA', 'EVENTOS', 'OPERACIONAL', "
    "'PESSOAL', 'INVESTIMENTO', 'OUTROS'"
)


def _constraint(*, allow_january_2026: bool) -> str:
    historical = (
        "(tipo = 'RECEITA' AND origem = 'MANUAL' "
        "AND categoria = 'RECEITA_DIRETA' AND periodo_ano = 2026 "
        "AND periodo_mes = 1 AND boe_import_id IS NULL) OR "
        if allow_january_2026 else ""
    )
    return (
        "(tipo = 'RECEITA' AND origem = 'BOE' "
        "AND categoria = 'RECEITA_DIRETA' AND boe_import_id IS NOT NULL) OR "
        "(tipo = 'RECEITA' AND origem = 'MANUAL' "
        "AND categoria = 'RECEITA_INDIRETA' AND boe_import_id IS NULL) OR "
        + historical
        + "(tipo = 'DESPESA' AND origem = 'MANUAL' AND categoria IN ("
        + EXPENSE_SQL
        + ") AND boe_import_id IS NULL)"
    )


def _replace_constraint(*, allow_january_2026: bool) -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("cashflow_entries", recreate="always") as batch_op:
            batch_op.drop_constraint(
                "ck_cashflow_entries_source_consistency", type_="check"
            )
            batch_op.create_check_constraint(
                "ck_cashflow_entries_source_consistency",
                _constraint(allow_january_2026=allow_january_2026),
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
        _constraint(allow_january_2026=allow_january_2026),
    )


def upgrade() -> None:
    _replace_constraint(allow_january_2026=True)


def downgrade() -> None:
    _replace_constraint(allow_january_2026=False)
