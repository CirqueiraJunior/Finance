from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class CSVExport(Base):
    __tablename__ = "csv_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ano: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    diretorio: Mapped[str] = mapped_column(Text, nullable=False)
    arquivos: Mapped[str | None] = mapped_column(Text)
    relatorio: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
