from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class TargetIndicator(StrEnum):
    QUERIES = "CONSULTAS"
    REGISTRATIONS = "REGISTROS"


class TargetEntry(Base):
    __tablename__ = "target_entries"
    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "periodo_ano",
            "periodo_mes",
            "indicador",
            name="uq_target_entries_entity_period_indicator",
        ),
        CheckConstraint(
            "periodo_ano BETWEEN 2000 AND 9999", name="ck_target_entries_year"
        ),
        CheckConstraint(
            "periodo_mes BETWEEN 1 AND 12", name="ck_target_entries_month"
        ),
        CheckConstraint(
            "indicador IN ('CONSULTAS', 'REGISTROS')",
            name="ck_target_entries_indicator",
        ),
        CheckConstraint("valor_meta >= 0", name="ck_target_entries_target_value"),
        CheckConstraint(
            "valor_realizado >= 0", name="ck_target_entries_actual_value"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    periodo_ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    periodo_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    indicador: Mapped[str] = mapped_column(String(20), nullable=False)
    valor_meta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    valor_realizado: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    observacao: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    entity: Mapped["Entity"] = relationship()


from app.models.entity import Entity  # noqa: E402
