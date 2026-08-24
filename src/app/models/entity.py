from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.entity_alias import EntityAlias


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo_entidade: Mapped[int] = mapped_column(
        Integer, nullable=False, unique=True, index=True
    )
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_oficial: Mapped[str | None] = mapped_column(String(255))
    municipio: Mapped[str | None] = mapped_column(String(150))
    uf: Mapped[str | None] = mapped_column(String(2))
    sigla: Mapped[str | None] = mapped_column(String(50))
    ativa: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=func.true(),
    )
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

    aliases: Mapped[list["EntityAlias"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
