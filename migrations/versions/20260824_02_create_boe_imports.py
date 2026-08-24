"""create BOE import history and entity totals

Revision ID: 20260824_02
Revises: 20260824_01
Create Date: 2026-08-24
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_02"
down_revision: str | None = "20260824_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "boe_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("periodo_ano", sa.Integer(), nullable=False),
        sa.Column("periodo_mes", sa.Integer(), nullable=False),
        sa.Column("nome_arquivo", sa.String(length=255), nullable=False),
        sa.Column("caminho_origem", sa.String(length=1024), nullable=False),
        sa.Column("hash_arquivo", sa.String(length=64), nullable=False),
        sa.Column(
            "data_importacao",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("quantidade_entidades", sa.Integer(), nullable=False),
        sa.Column("quantidade_inconsistencias", sa.Integer(), nullable=False),
        sa.Column("valor_total", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "periodo_mes BETWEEN 1 AND 12",
            name="ck_boe_imports_month",
        ),
        sa.CheckConstraint(
            "status IN ('validated', 'imported', 'failed', 'cancelled')",
            name="ck_boe_imports_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "periodo_ano",
            "periodo_mes",
            name="uq_boe_imports_period",
        ),
    )
    op.create_index(
        op.f("ix_boe_imports_hash_arquivo"),
        "boe_imports",
        ["hash_arquivo"],
        unique=True,
    )

    op.create_table(
        "boe_entity_totals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("boe_import_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("codigo_entidade_origem", sa.Integer(), nullable=False),
        sa.Column("nome_entidade_origem", sa.String(length=255), nullable=False),
        sa.Column("quantidade_consultas", sa.Integer(), nullable=False),
        sa.Column("valor_total", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "quantidade_consultas >= 0",
            name="ck_boe_entity_totals_quantity",
        ),
        sa.CheckConstraint(
            "valor_total >= 0",
            name="ck_boe_entity_totals_value",
        ),
        sa.ForeignKeyConstraint(
            ["boe_import_id"],
            ["boe_imports.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "boe_import_id",
            "entity_id",
            name="uq_boe_entity_totals_import_entity",
        ),
    )
    op.create_index(
        op.f("ix_boe_entity_totals_boe_import_id"),
        "boe_entity_totals",
        ["boe_import_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_boe_entity_totals_entity_id"),
        "boe_entity_totals",
        ["entity_id"],
        unique=False,
    )

    op.create_table(
        "boe_import_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("boe_import_id", sa.Integer(), nullable=False),
        sa.Column("linha", sa.Integer(), nullable=True),
        sa.Column("codigo", sa.String(length=50), nullable=True),
        sa.Column("mensagem", sa.String(length=500), nullable=False),
        sa.Column("severidade", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "severidade IN ('ERROR', 'WARNING')",
            name="ck_boe_import_issues_severity",
        ),
        sa.ForeignKeyConstraint(
            ["boe_import_id"],
            ["boe_imports.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_boe_import_issues_boe_import_id"),
        "boe_import_issues",
        ["boe_import_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_boe_import_issues_boe_import_id"),
        table_name="boe_import_issues",
    )
    op.drop_table("boe_import_issues")
    op.drop_index(
        op.f("ix_boe_entity_totals_entity_id"),
        table_name="boe_entity_totals",
    )
    op.drop_index(
        op.f("ix_boe_entity_totals_boe_import_id"),
        table_name="boe_entity_totals",
    )
    op.drop_table("boe_entity_totals")
    op.drop_index(op.f("ix_boe_imports_hash_arquivo"), table_name="boe_imports")
    op.drop_table("boe_imports")

