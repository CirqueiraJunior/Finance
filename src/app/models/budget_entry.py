from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BudgetEntry(Base):
    __tablename__ = "budget_entries"
    __table_args__ = (
        UniqueConstraint(
            "periodo_ano", "periodo_mes", "tipo", "categoria",
            name="uq_budget_entries_period_type_category",
        ),
        CheckConstraint(
            "periodo_ano BETWEEN 2000 AND 9999", name="ck_budget_entries_year"
        ),
        CheckConstraint(
            "periodo_mes BETWEEN 1 AND 12", name="ck_budget_entries_month"
        ),
        CheckConstraint(
            "tipo IN ('RECEITA', 'DESPESA')", name="ck_budget_entries_type"
        ),
        CheckConstraint("valor_orcado >= 0", name="ck_budget_entries_value"),
        CheckConstraint(
            "(tipo = 'RECEITA' AND categoria IN "
            "('RECEITA_DIRETA', 'RECEITA_INDIRETA')) OR "
            "(tipo = 'DESPESA' AND categoria IN "
            "('ADMINISTRATIVO', 'DIRETORIA', 'EVENTOS', 'OPERACIONAL', "
            "'PESSOAL', 'INVESTIMENTO', 'IMPOSTOS_E_TAXAS', 'SOFTWARE', "
            "'VIAGEM', 'OUTROS'))",
            name="ck_budget_entries_type_category",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    periodo_ano: Mapped[int] = mapped_column(Integer, nullable=False)
    periodo_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    categoria: Mapped[str] = mapped_column(String(30), nullable=False)
    valor_orcado: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
        onupdate=func.now(),
    )
