"""SQLAlchemy model registry."""

from app.models.entity import Entity
from app.models.entity_alias import EntityAlias

__all__ = ["Entity", "EntityAlias"]
