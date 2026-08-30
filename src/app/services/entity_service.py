from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    EntityAliasAlreadyExistsError,
    EntityCodeAlreadyExistsError,
    InvalidEntityCodeError,
)
from app.models.entity import Entity
from app.models.entity_alias import EntityAlias
from app.repositories.entity_repository import EntityRepository


CONSOLIDATED_ENTITY_CODE = 7500


class EntityService:
    def __init__(self, repository: EntityRepository) -> None:
        self.repository = repository

    def create_entity(
        self,
        *,
        codigo_entidade: int,
        nome: str,
        nome_oficial: str | None = None,
        municipio: str | None = None,
        uf: str | None = None,
        sigla: str | None = None,
        ativa: bool = True,
        observacao: str | None = None,
    ) -> Entity:
        code = int(codigo_entidade)
        self._validate_code(code)
        if self.repository.exists_by_code(code):
            raise EntityCodeAlreadyExistsError(
                f"O código de Entidade {code} já está cadastrado."
            )

        entity = Entity(
            codigo_entidade=code,
            nome=self._required_text(nome, "nome"),
            nome_oficial=self._optional_text(nome_oficial),
            municipio=self._optional_text(municipio),
            uf=self._normalize_uf(uf),
            sigla=self._optional_text(sigla),
            ativa=ativa,
            observacao=self._optional_text(observacao),
        )
        try:
            self.repository.add(entity)
            self.repository.session.commit()
        except IntegrityError as error:
            self.repository.session.rollback()
            raise EntityCodeAlreadyExistsError(
                f"O código de Entidade {code} já está cadastrado."
            ) from error
        self.repository.session.refresh(entity)
        return entity

    def get_entity_by_code(self, codigo_entidade: int) -> Entity | None:
        return self.repository.get_by_code(int(codigo_entidade))

    def list_entities(self) -> list[Entity]:
        return self.repository.list_all()

    def update_entity(
        self,
        entity_id: int,
        *,
        nome: str,
        nome_oficial: str | None = None,
        municipio: str | None = None,
        uf: str | None = None,
        sigla: str | None = None,
        ativa: bool | None = None,
    ) -> Entity:
        entity = self.repository.get_by_id(entity_id)
        if entity is None:
            raise ValueError("Entidade não encontrada.")
        entity.nome = self._required_text(nome, "nome")
        entity.nome_oficial = self._optional_text(nome_oficial)
        entity.municipio = self._optional_text(municipio)
        entity.uf = self._normalize_uf(uf)
        entity.sigla = self._optional_text(sigla)
        if ativa is not None:
            entity.ativa = bool(ativa)
        self.repository.session.commit()
        self.repository.session.refresh(entity)
        return entity

    def set_active(self, entity_id: int, active: bool) -> Entity:
        entity = self.repository.get_by_id(entity_id)
        if entity is None:
            raise ValueError("Entidade não encontrada.")
        entity.ativa = bool(active)
        self.repository.session.commit()
        return entity

    def add_alias(
        self, entity: Entity, alias: str, origem: str | None = None
    ) -> EntityAlias:
        normalized_alias = self._required_text(alias, "alias")
        if entity.id is None:
            raise ValueError("A Entidade deve estar persistida antes de receber aliases.")
        if self.repository.alias_exists(entity.id, normalized_alias):
            raise EntityAliasAlreadyExistsError(
                f'O alias "{normalized_alias}" já está cadastrado para esta Entidade.'
            )

        entity_alias = EntityAlias(
            entity_id=entity.id,
            alias=normalized_alias,
            origem=self._optional_text(origem),
        )
        try:
            self.repository.add_alias(entity_alias)
            self.repository.session.commit()
        except IntegrityError as error:
            self.repository.session.rollback()
            raise EntityAliasAlreadyExistsError(
                f'O alias "{normalized_alias}" já está cadastrado para esta Entidade.'
            ) from error
        self.repository.session.refresh(entity_alias)
        return entity_alias

    @staticmethod
    def _validate_code(codigo_entidade: int) -> None:
        if codigo_entidade == CONSOLIDATED_ENTITY_CODE:
            raise InvalidEntityCodeError(
                "O código 7500 representa o consolidado geral e não pode ser "
                "cadastrado como Entidade."
            )

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"O campo {field_name} é obrigatório.")
        return normalized

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @classmethod
    def _normalize_uf(cls, value: str | None) -> str | None:
        normalized = cls._optional_text(value)
        if normalized is None:
            return None
        if len(normalized) != 2:
            raise ValueError("A UF deve possuir exatamente 2 caracteres.")
        return normalized.upper()
