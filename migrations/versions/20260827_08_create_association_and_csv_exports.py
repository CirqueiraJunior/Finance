"""create association entries and csv export history

Revision ID: 20260827_08
Revises: 20260825_07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260827_08"
down_revision: Union[str, None] = "20260825_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "association_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("periodo_ano", sa.Integer(), nullable=False),
        sa.Column("periodo_mes", sa.Integer(), nullable=False),
        sa.Column("valor_captacao", sa.Numeric(18, 4), nullable=False),
        sa.Column("valor_execucao", sa.Numeric(18, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("periodo_ano BETWEEN 2000 AND 9999", name="ck_association_entries_year"),
        sa.CheckConstraint("periodo_mes BETWEEN 1 AND 12", name="ck_association_entries_month"),
        sa.CheckConstraint("valor_captacao >= 0", name="ck_association_entries_capture"),
        sa.CheckConstraint("valor_execucao >= 0", name="ck_association_entries_execution"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", "periodo_ano", "periodo_mes", name="uq_association_entries_entity_period"),
    )
    op.create_index(op.f("ix_association_entries_entity_id"), "association_entries", ["entity_id"])
    op.create_index(op.f("ix_association_entries_periodo_ano"), "association_entries", ["periodo_ano"])

    op.create_table(
        "csv_exports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ano", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("diretorio", sa.Text(), nullable=False),
        sa.Column("arquivos", sa.Text(), nullable=True),
        sa.Column("relatorio", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_csv_exports_ano"), "csv_exports", ["ano"])


def downgrade() -> None:
    op.drop_index(op.f("ix_csv_exports_ano"), table_name="csv_exports")
    op.drop_table("csv_exports")
    op.drop_index(op.f("ix_association_entries_periodo_ano"), table_name="association_entries")
    op.drop_index(op.f("ix_association_entries_entity_id"), table_name="association_entries")
    op.drop_table("association_entries")
