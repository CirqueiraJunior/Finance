from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class AssociationEntry(Base):
    __tablename__ = "association_entries"
    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "periodo_ano",
            "periodo_mes",
            name="uq_association_entries_entity_period",
        ),
        CheckConstraint(
            "periodo_ano BETWEEN 2000 AND 9999",
            name="ck_association_entries_year",
        ),
        CheckConstraint(
            "periodo_mes BETWEEN 1 AND 12",
            name="ck_association_entries_month",
        ),
        CheckConstraint(
            "valor_captacao >= 0",
            name="ck_association_entries_capture",
        ),
        CheckConstraint(
            "valor_execucao >= 0",
            name="ck_association_entries_execution",
        ),
        CheckConstraint(
            "valor_cancelamento >= 0",
            name="ck_association_entries_cancellation",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    periodo_ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    periodo_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_captacao: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    valor_execucao: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    valor_cancelamento: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, default=Decimal("0.0000"),
        server_default="0.0000",
    )
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
