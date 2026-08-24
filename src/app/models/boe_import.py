from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.boe_entity_total import BOEEntityTotal
    from app.models.boe_import_issue import BOEImportIssue


class BOEImport(Base):
    __tablename__ = "boe_imports"
    __table_args__ = (
        UniqueConstraint(
            "periodo_ano",
            "periodo_mes",
            name="uq_boe_imports_period",
        ),
        CheckConstraint(
            "periodo_mes BETWEEN 1 AND 12",
            name="ck_boe_imports_month",
        ),
        CheckConstraint(
            "status IN ('validated', 'imported', 'failed', 'cancelled')",
            name="ck_boe_imports_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    periodo_ano: Mapped[int] = mapped_column(Integer, nullable=False)
    periodo_mes: Mapped[int] = mapped_column(Integer, nullable=False)
    nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
    caminho_origem: Mapped[str] = mapped_column(String(1024), nullable=False)
    hash_arquivo: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    data_importacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    quantidade_entidades: Mapped[int] = mapped_column(Integer, nullable=False)
    quantidade_inconsistencias: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    entity_totals: Mapped[list["BOEEntityTotal"]] = relationship(
        back_populates="boe_import",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    issues: Mapped[list["BOEImportIssue"]] = relationship(
        back_populates="boe_import",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

