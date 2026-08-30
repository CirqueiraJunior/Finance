from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import TargetDuplicateError, TargetValidationError
from app.models.entity import Entity
from app.models.target_entry import TargetEntry, TargetIndicator
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository


@dataclass(frozen=True, slots=True)
class TargetComparison:
    target_id: int
    entity_code: int
    entity_name: str
    indicator: str
    target: Decimal
    actual: Decimal
    difference: Decimal
    achievement_percentage: Decimal | None
    notes: str | None


@dataclass(frozen=True, slots=True)
class TargetSummary:
    entity_count: int
    target_total: Decimal
    actual_total: Decimal
    difference_total: Decimal
    achievement_percentage: Decimal | None


@dataclass(frozen=True, slots=True)
class TargetVsActual:
    comparisons: tuple[TargetComparison, ...]
    summary: TargetSummary


class TargetService:
    def __init__(
        self,
        repository: TargetRepository,
        entity_repository: EntityRepository,
    ) -> None:
        if repository.session is not entity_repository.session:
            raise ValueError("Metas e Entidades devem compartilhar a mesma sessão.")
        self.repository = repository
        self.entity_repository = entity_repository

    def create_target(
        self,
        *,
        entity_id: int,
        year: int,
        month: int,
        indicator: TargetIndicator | str,
        target_value: Decimal | str,
        actual_value: Decimal | str = Decimal("0.0000"),
        notes: str | None = None,
    ) -> TargetEntry:
        entity = self._valid_entity(entity_id)
        normalized_year = self._valid_year(year)
        normalized_month = self._valid_month(month)
        normalized_indicator = self._valid_indicator(indicator)
        if self.repository.exists(
            entity.id, normalized_year, normalized_month, normalized_indicator.value
        ):
            raise TargetDuplicateError(
                "Já existe Meta para esta Entidade, período e indicador."
            )
        target = TargetEntry(
            entity_id=entity.id,
            periodo_ano=normalized_year,
            periodo_mes=normalized_month,
            indicador=normalized_indicator.value,
            valor_meta=self._non_negative_decimal(target_value, "Meta"),
            valor_realizado=self._non_negative_decimal(actual_value, "Realizado"),
            observacao=self._optional_text(notes),
        )
        try:
            self.repository.add(target)
            self.repository.session.commit()
            self.repository.session.refresh(target)
            return target
        except IntegrityError as error:
            self.repository.session.rollback()
            raise TargetDuplicateError(
                "Já existe Meta para esta Entidade, período e indicador."
            ) from error

    def update_target(
        self,
        target_id: int,
        *,
        target_value: Decimal | str,
        notes: str | None = None,
    ) -> TargetEntry:
        target = self.repository.get_by_id(target_id)
        if target is None:
            raise TargetValidationError("Meta não encontrada.")
        target.valor_meta = self._non_negative_decimal(target_value, "Meta")
        target.observacao = self._optional_text(notes)
        self.repository.session.commit()
        self.repository.session.refresh(target)
        return target

    def get_target(self, target_id: int) -> TargetEntry | None:
        return self.repository.get_by_id(target_id)

    def list_by_period(self, year: int, month: int) -> list[TargetEntry]:
        return self.repository.list_by_period(
            self._valid_year(year), self._valid_month(month)
        )

    def list_by_entity(self, entity_id: int) -> list[TargetEntry]:
        entity = self._valid_entity(entity_id)
        return self.repository.list_by_entity(entity.id)

    def list_by_year(self, year: int) -> list[TargetEntry]:
        return self.repository.list_by_year(self._valid_year(year))

    def list_entities(self) -> list[Entity]:
        return [
            entity
            for entity in self.entity_repository.list_all()
            if entity.codigo_entidade != 7500
        ]

    def get_target_vs_actual(
        self,
        year: int,
        month: int,
        indicator: TargetIndicator | str,
        entity_id: int | None = None,
    ) -> TargetVsActual:
        normalized_indicator = self._valid_indicator(indicator)
        entries = self.list_by_period(year, month)
        if entity_id is not None:
            self._valid_entity(entity_id)
        entries = [
            entry
            for entry in entries
            if entry.indicador == normalized_indicator.value
            and entry.entity.codigo_entidade != 7500
            and (entity_id is None or entry.entity_id == entity_id)
        ]
        comparisons = tuple(self._comparison(entry) for entry in entries)
        zero = Decimal("0.0000")
        target_total = sum((item.target for item in comparisons), zero)
        actual_total = sum((item.actual for item in comparisons), zero)
        difference_total = actual_total - target_total
        achievement = self._achievement(actual_total, target_total)
        return TargetVsActual(
            comparisons,
            TargetSummary(
                len({item.entity_code for item in comparisons}),
                target_total,
                actual_total,
                difference_total,
                achievement,
            ),
        )

    @classmethod
    def _comparison(cls, entry: TargetEntry) -> TargetComparison:
        target = entry.valor_meta
        actual = entry.valor_realizado
        return TargetComparison(
            target_id=entry.id,
            entity_code=entry.entity.codigo_entidade,
            entity_name=entry.entity.nome_oficial or entry.entity.nome,
            indicator=entry.indicador,
            target=target,
            actual=actual,
            difference=actual - target,
            achievement_percentage=cls._achievement(actual, target),
            notes=entry.observacao,
        )

    @staticmethod
    def _achievement(actual: Decimal, target: Decimal) -> Decimal | None:
        if target == 0:
            return None
        return (actual / target * Decimal("100")).quantize(Decimal("0.0001"))

    def _valid_entity(self, entity_id: int) -> Entity:
        entity = self.entity_repository.get_by_id(entity_id)
        if entity is None:
            raise TargetValidationError("Entidade não encontrada.")
        if entity.codigo_entidade == 7500:
            raise TargetValidationError("O código 7500 é consolidado, não Entidade.")
        return entity

    @staticmethod
    def _valid_indicator(value: TargetIndicator | str) -> TargetIndicator:
        try:
            return TargetIndicator(value)
        except ValueError as error:
            raise TargetValidationError("Indicador inválido.") from error

    @staticmethod
    def _valid_year(value: int) -> int:
        try:
            year = int(value)
        except (TypeError, ValueError) as error:
            raise TargetValidationError("Ano inválido.") from error
        if not 2000 <= year <= 9999:
            raise TargetValidationError("Ano inválido.")
        return year

    @staticmethod
    def _valid_month(value: int) -> int:
        try:
            month = int(value)
        except (TypeError, ValueError) as error:
            raise TargetValidationError("Mês inválido.") from error
        if not 1 <= month <= 12:
            raise TargetValidationError("Mês inválido.")
        return month

    @staticmethod
    def _non_negative_decimal(value: Decimal | str, label: str) -> Decimal:
        if isinstance(value, float):
            raise TargetValidationError(f"{label} não pode usar float.")
        try:
            amount = Decimal(value).quantize(Decimal("0.0001"))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise TargetValidationError(f"{label} inválido.") from error
        if not amount.is_finite() or amount < 0:
            raise TargetValidationError(f"{label} não pode ser negativo.")
        return amount

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        normalized = value.strip() if isinstance(value, str) else ""
        return normalized or None
