from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.boe_import import BOEImport


class BOEImportIssue(Base):
    __tablename__ = "boe_import_issues"
    __table_args__ = (
        CheckConstraint(
            "severidade IN ('ERROR', 'WARNING')",
            name="ck_boe_import_issues_severity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    boe_import_id: Mapped[int] = mapped_column(
        ForeignKey("boe_imports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linha: Mapped[int | None] = mapped_column(Integer)
    codigo: Mapped[str | None] = mapped_column(String(50))
    mensagem: Mapped[str] = mapped_column(String(500), nullable=False)
    severidade: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    boe_import: Mapped["BOEImport"] = relationship(back_populates="issues")

