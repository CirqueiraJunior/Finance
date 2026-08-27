from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AssociationValidationError
from app.models.association_entry import AssociationEntry
from app.repositories.association_repository import AssociationRepository
from app.repositories.entity_repository import EntityRepository


class AssociationService:
    def __init__(
        self,
        repository: AssociationRepository,
        entity_repository: EntityRepository,
    ) -> None:
        if repository.session is not entity_repository.session:
            raise ValueError("Associação e Entidades devem compartilhar a sessão.")
        self.repository = repository
        self.entity_repository = entity_repository

    def upsert(
        self,
        *,
        entity_id: int,
        year: int,
        month: int,
        capture_value: Decimal | str,
        execution_value: Decimal | str,
    ) -> AssociationEntry:
        entity = self.entity_repository.get_by_id(entity_id)
        if entity is None or not entity.ativa or entity.codigo_entidade == 7500:
            raise AssociationValidationError("Entidade inválida para Associação.")
        year = self._year(year)
        month = self._month(month)
        capture = self._decimal(capture_value)
        execution = self._decimal(execution_value)
        entry = self.repository.get_by_key(entity.id, year, month)
        if entry is None:
            entry = AssociationEntry(
                entity_id=entity.id,
                periodo_ano=year,
                periodo_mes=month,
                valor_captacao=capture,
                valor_execucao=execution,
            )
            self.repository.add(entry)
        else:
            entry.valor_captacao = capture
            entry.valor_execucao = execution
        try:
            self.repository.session.commit()
            self.repository.session.refresh(entry)
            return entry
        except IntegrityError as error:
            self.repository.session.rollback()
            raise AssociationValidationError(
                "Não foi possível salvar os dados de Associação."
            ) from error

    def list_by_year(self, year: int) -> list[AssociationEntry]:
        return self.repository.list_by_year(self._year(year))

    @staticmethod
    def _year(value: int) -> int:
        try:
            year = int(value)
        except (TypeError, ValueError) as error:
            raise AssociationValidationError("Ano inválido.") from error
        if not 2000 <= year <= 9999:
            raise AssociationValidationError("Ano inválido.")
        return year

    @staticmethod
    def _month(value: int) -> int:
        try:
            month = int(value)
        except (TypeError, ValueError) as error:
            raise AssociationValidationError("Mês inválido.") from error
        if not 1 <= month <= 12:
            raise AssociationValidationError("Mês inválido.")
        return month

    @staticmethod
    def _decimal(value: Decimal | str) -> Decimal:
        if isinstance(value, float):
            raise AssociationValidationError("Valores de Associação não aceitam float.")
        try:
            amount = Decimal(value).quantize(Decimal("0.0001"))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise AssociationValidationError("Valor de Associação inválido.") from error
        if not amount.is_finite() or amount < 0:
            raise AssociationValidationError("Valor de Associação não pode ser negativo.")
        return amount
