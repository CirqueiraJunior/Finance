from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FinancialBalanceType(StrEnum):
    INITIAL = "SALDO_INICIAL"
    APPLIED = "SALDO_APLICADO"


class FinancialBalanceEntry(Base):
    __tablename__ = "financial_balance_entries"
    __table_args__ = (
        UniqueConstraint("year", "month", "balance_type", name="uq_financial_balance_period_type"),
        CheckConstraint("year BETWEEN 2000 AND 9999", name="ck_financial_balance_year"),
        CheckConstraint("month BETWEEN 1 AND 12", name="ck_financial_balance_month"),
        CheckConstraint("value >= 0", name="ck_financial_balance_value"),
        CheckConstraint("balance_type IN ('SALDO_INICIAL', 'SALDO_APLICADO')",
                        name="ck_financial_balance_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_type: Mapped[str] = mapped_column(String(30), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                  server_default=func.now(), onupdate=func.now())
