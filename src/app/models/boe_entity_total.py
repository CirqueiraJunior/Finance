from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.boe_import import BOEImport
    from app.models.entity import Entity


class BOEEntityTotal(Base):
    __tablename__ = "boe_entity_totals"
    __table_args__ = (
        UniqueConstraint(
            "boe_import_id",
            "entity_id",
            name="uq_boe_entity_totals_import_entity",
        ),
        CheckConstraint(
            "quantidade_consultas >= 0",
            name="ck_boe_entity_totals_quantity",
        ),
        CheckConstraint("valor_total >= 0", name="ck_boe_entity_totals_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    boe_import_id: Mapped[int] = mapped_column(
        ForeignKey("boe_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_id: Mapped[int] = mapped_column(
        ForeignKey("entities.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    codigo_entidade_origem: Mapped[int] = mapped_column(Integer, nullable=False)
    nome_entidade_origem: Mapped[str] = mapped_column(String(255), nullable=False)
    quantidade_consultas: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    boe_import: Mapped["BOEImport"] = relationship(back_populates="entity_totals")
    entity: Mapped["Entity"] = relationship(back_populates="boe_totals")

