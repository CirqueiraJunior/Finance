from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entity import Entity
from app.models.entity_alias import EntityAlias
from app.repositories.base import BaseRepository


class EntityRepository(BaseRepository[Entity]):
    def __init__(self, session: Session) -> None:
        super().__init__(session)

    def get_by_id(self, entity_id: int) -> Entity | None:
        return self.session.get(Entity, entity_id)

    def get_by_code(self, codigo_entidade: int) -> Entity | None:
        statement = (
            select(Entity)
            .options(selectinload(Entity.aliases))
            .where(Entity.codigo_entidade == codigo_entidade)
        )
        return self.session.scalar(statement)

    def list_all(self) -> list[Entity]:
        statement = (
            select(Entity)
            .options(selectinload(Entity.aliases))
            .order_by(Entity.codigo_entidade)
        )
        return list(self.session.scalars(statement))

    def exists_by_code(self, codigo_entidade: int) -> bool:
        statement = select(Entity.id).where(
            Entity.codigo_entidade == codigo_entidade
        )
        return self.session.scalar(statement) is not None

    def add(self, entity: Entity) -> Entity:
        self.session.add(entity)
        self.session.flush()
        return entity

    def alias_exists(self, entity_id: int, alias: str) -> bool:
        statement = select(EntityAlias.id).where(
            EntityAlias.entity_id == entity_id,
            EntityAlias.alias == alias,
        )
        return self.session.scalar(statement) is not None

    def add_alias(self, entity_alias: EntityAlias) -> EntityAlias:
        self.session.add(entity_alias)
        self.session.flush()
        return entity_alias

