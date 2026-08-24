from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.boe_import import BOEImport


class CashflowType(StrEnum):
    REVENUE = "RECEITA"


class CashflowOrigin(StrEnum):
    BOE = "BOE"
    MANUAL = "MANUAL"


class CashflowCategory(StrEnum):
    DIRECT_REVENUE = "RECEITA_DIRETA"
    INDIRECT_REVENUE = "RECEITA_INDIRETA"


class CashflowEntry(Base):
    __tablename__ = "cashflow_entries"
    __table_args__ = (
        CheckConstraint("periodo_mes BETWEEN 1 AND 12", name="ck_cashflow_entries_month"),
        CheckConstraint("periodo_ano BETWEEN 2000 AND 9999", name="ck_cashflow_entries_year"),
        CheckConstraint("valor > 0", name="ck_cashflow_entries_positive_value"),
        CheckConstraint("tipo = 'RECEITA'", name="ck_cashflow_entries_type"),
        CheckConstraint("origem IN ('BOE', 'MANUAL')", name="ck_cashflow_entries_origin"),
        CheckConstraint(
            "categoria IN ('RECEITA_DIRETA', 'RECEITA_INDIRETA')",
            name="ck_cashflow_entries_category",
        ),
        CheckConstraint(
            "(origem = 'BOE' AND categoria = 'RECEITA_DIRETA' AND boe_import_id IS NOT NULL) OR "
            "(origem = 'MANUAL' AND categoria = 'RECEITA_INDIRETA' AND boe_import_id IS NULL)",
            name="ck_cashflow_entries_source_consistency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    periodo_ano: Mapped[int] = mapped_column(Integer, nullable=False)
    periodo_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    data_lancamento: Mapped[date] = mapped_column(Date, nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    boe_import_id: Mapped[int | None] = mapped_column(
        ForeignKey("boe_imports.id", ondelete="RESTRICT"), unique=True, index=True
    )
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    boe_import: Mapped["BOEImport | None"] = relationship(back_populates="cashflow_entry")
