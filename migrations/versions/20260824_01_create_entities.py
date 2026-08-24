"""create entities and entity aliases

Revision ID: 20260824_01
Revises:
Create Date: 2026-08-24
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260824_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("codigo_entidade", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("nome_oficial", sa.String(length=255), nullable=True),
        sa.Column("municipio", sa.String(length=150), nullable=True),
        sa.Column("uf", sa.String(length=2), nullable=True),
        sa.Column("sigla", sa.String(length=50), nullable=True),
        sa.Column(
            "ativa",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_entities_codigo_entidade"),
        "entities",
        ["codigo_entidade"],
        unique=True,
    )

    op.create_table(
        "entity_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("origem", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_id",
            "alias",
            name="uq_entity_aliases_entity_alias",
        ),
    )
    op.create_index(
        op.f("ix_entity_aliases_entity_id"),
        "entity_aliases",
        ["entity_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_entity_aliases_entity_id"),
        table_name="entity_aliases",
    )
    op.drop_table("entity_aliases")
    op.drop_index(op.f("ix_entities_codigo_entidade"), table_name="entities")
    op.drop_table("entities")
