"""align cashflow with official spreadsheet catalog

Revision ID: 20260827_09
Revises: 20260827_08
Create Date: 2026-08-27
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260827_09"
down_revision: str | None = "20260827_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATALOG_ROWS = [
    ('Alimentação/Refeição', 'DIRETORIA', 'DESPESA'),
    ('Alimentação/Refeição', 'OPERACIONAL', 'DESPESA'),
    ('Alimentação/Refeição', 'EVENTOS', 'DESPESA'),
    ('Aplicação', 'INVESTIMENTO', 'APLICACAO'),
    ('Correios', 'ADMINISTRATIVO', 'DESPESA'),
    ('Hospedagem', 'DIRETORIA', 'DESPESA'),
    ('Hospedagem', 'OPERACIONAL', 'DESPESA'),
    ('Hospedagem', 'EVENTOS', 'DESPESA'),
    ('Impostos e Taxas', 'ADMINISTRATIVO', 'DESPESA'),
    ('IPVA', 'ADMINISTRATIVO', 'DESPESA'),
    ('Manutenção', 'ADMINISTRATIVO', 'DESPESA'),
    ('Manutenção', 'OPERACIONAL', 'DESPESA'),
    ('Materais Gráficos e Escritório', 'ADMINISTRATIVO', 'DESPESA'),
    ('Materais Gráficos e Escritório', 'EVENTOS', 'DESPESA'),
    ('Modernização', 'OUTROS', 'DESPESA'),
    ('Outros', 'OUTROS', 'DESPESA'),
    ('Palestra/Workshop', 'DIRETORIA', 'DESPESA'),
    ('Palestra/Workshop', 'EVENTOS', 'DESPESA'),
    ('Premiação', 'DIRETORIA', 'DESPESA'),
    ('Premiação', 'PESSOAL', 'DESPESA'),
    ('Premiação', 'EVENTOS', 'DESPESA'),
    ('Reembolso', 'DIRETORIA', 'DESPESA'),
    ('Reembolso', 'OPERACIONAL', 'DESPESA'),
    ('Reembolso', 'RECEITA_INDIRETA', 'RECEITA'),
    ("Repasse CDL's Estado GO", 'RECEITA_DIRETA', 'RECEITA'),
    ('Resgate de Aplicação', 'RESGATE', 'RESGATE'),
    ('Salários e Encargos', 'PESSOAL', 'DESPESA'),
    ('Saldo Aplicado', 'SALDO_APLICADO', 'SALDO'),
    ('Seguro', 'ADMINISTRATIVO', 'DESPESA'),
    ('Software', 'ADMINISTRATIVO', 'DESPESA'),
    ('Suprimento de Caixa', 'ADMINISTRATIVO', 'DESPESA'),
    ('Telefone', 'ADMINISTRATIVO', 'DESPESA'),
    ('Venda de Produtos/Serviços', 'RECEITA_INDIRETA', 'RECEITA'),
    ('Viagem', 'DIRETORIA', 'DESPESA'),
    ('Viagem', 'EVENTOS', 'DESPESA'),
    ('Viagem', 'OPERACIONAL', 'DESPESA')
]


def upgrade() -> None:
    op.create_table(
        "cashflow_catalog_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("descricao", sa.String(length=255), nullable=False),
        sa.Column("categoria", sa.String(length=50), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("ativa", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "descricao", "categoria", "tipo",
            name="uq_cashflow_catalog_description_category_type",
        ),
    )

    catalog = sa.table(
        "cashflow_catalog_entries",
        sa.column("descricao", sa.String),
        sa.column("categoria", sa.String),
        sa.column("tipo", sa.String),
        sa.column("ativa", sa.Boolean),
    )
    op.bulk_insert(
        catalog,
        [
            {"descricao": d, "categoria": c, "tipo": t, "ativa": True}
            for d, c, t in CATALOG_ROWS
        ],
    )

    with op.batch_alter_table("cashflow_entries") as batch_op:
        batch_op.add_column(
            sa.Column("boe", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("cashflow_entries") as batch_op:
        batch_op.drop_column("boe")
    op.drop_table("cashflow_catalog_entries")
