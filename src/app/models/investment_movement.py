from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class InvestmentMovementType(StrEnum):
    APPLICATION = "APLICACAO"
    REDEMPTION = "RESGATE"


class InvestmentMovement(Base):
    __tablename__ = "investment_movements"
    __table_args__ = (
        CheckConstraint("periodo_ano BETWEEN 2000 AND 9999", name="ck_investment_year"),
        CheckConstraint("periodo_mes BETWEEN 1 AND 12", name="ck_investment_month"),
        CheckConstraint(
            "tipo IN ('APLICACAO', 'RESGATE')", name="ck_investment_type"
        ),
        CheckConstraint("valor > 0", name="ck_investment_value"),
        CheckConstraint("length(trim(descricao)) > 0", name="ck_investment_description"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    data_movimento: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_ano: Mapped[int] = mapped_column(Integer, nullable=False)
    periodo_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(String(255), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
