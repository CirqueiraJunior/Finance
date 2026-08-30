"""Apuração trimestral do Ranking e Premiação Acelera Goiás."""

from dataclasses import dataclass
from decimal import Decimal

from app.models.target_entry import TargetIndicator
from app.repositories.association_repository import AssociationRepository
from app.repositories.target_repository import TargetRepository
from app.services.award_service import AwardService


QUARTER_MONTHS = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}


@dataclass(frozen=True, slots=True)
class RankingEntry:
    entity_id: int
    entity_code: int
    entity_name: str
    meta_queries: Decimal
    actual_queries: Decimal
    meta_registrations: Decimal
    actual_registrations: Decimal
    captures: Decimal
    cancellations: Decimal
    achievement: Decimal | None
    billing_points: int
    capture_points: int
    cancellation_points: int
    score: int
    classified: bool
    position: int | None = None
    technical_tie: bool = False
    award: Decimal | None = None

    @property
    def target_total(self) -> Decimal:
        return self.meta_queries + self.meta_registrations

    @property
    def actual_total(self) -> Decimal:
        return self.actual_queries + self.actual_registrations


@dataclass(frozen=True, slots=True)
class AnnualRankingEntry:
    entity_id: int
    entity_code: int
    entity_name: str
    positions: tuple[int | None, int | None, int | None, int | None]
    classified_quarters: int
    award_count: int
    award_total: Decimal


class RankingService:
    def __init__(self, targets: TargetRepository, associations: AssociationRepository):
        self.targets = targets
        self.associations = associations

    @staticmethod
    def billing_points(achievement: Decimal | None) -> int:
        if achievement is None or achievement < Decimal("100"):
            return 0
        if achievement < Decimal("110"):
            return 5
        if achievement < Decimal("150"):
            return 6
        return 7

    @staticmethod
    def capture_points(captures: Decimal) -> int:
        if captures < 1:
            return 0
        if captures < 8:
            return 2
        if captures < 16:
            return 3
        return 4

    @staticmethod
    def cancellation_points(cancellations: Decimal) -> int:
        return 1 if cancellations == 0 else 0

    def quarterly(self, year: int, quarter: int) -> list[RankingEntry]:
        if quarter not in QUARTER_MONTHS:
            raise ValueError("Trimestre deve estar entre 1 e 4.")
        months = QUARTER_MONTHS[quarter]
        target_rows = [row for row in self.targets.list_by_year(year)
                       if row.periodo_mes in months and row.entity.codigo_entidade != 7500]
        association_rows = [row for row in self.associations.list_by_year(year)
                            if row.periodo_mes in months and row.entity.codigo_entidade != 7500]
        data: dict[int, dict] = {}
        zero = Decimal("0")
        for row in target_rows:
            item = data.setdefault(row.entity_id, {
                "entity": row.entity, "mq": zero, "aq": zero,
                "mr": zero, "ar": zero, "cap": zero, "can": zero,
            })
            prefix = "q" if row.indicador == TargetIndicator.QUERIES.value else "r"
            item[f"m{prefix}"] += row.valor_meta
            item[f"a{prefix}"] += row.valor_realizado
        for row in association_rows:
            item = data.setdefault(row.entity_id, {
                "entity": row.entity, "mq": zero, "aq": zero,
                "mr": zero, "ar": zero, "cap": zero, "can": zero,
            })
            item["cap"] += row.valor_captacao
            item["can"] += row.valor_cancelamento
        entries = []
        for entity_id, item in data.items():
            target = item["mq"] + item["mr"]
            actual = item["aq"] + item["ar"]
            achievement = None if target == 0 else actual / target * Decimal("100")
            classified = achievement is not None and achievement >= Decimal("100")
            billing = self.billing_points(achievement) if classified else 0
            capture = self.capture_points(item["cap"]) if classified else 0
            cancellation = self.cancellation_points(item["can"]) if classified else 0
            entity = item["entity"]
            entries.append(RankingEntry(
                entity_id, entity.codigo_entidade, entity.nome_oficial or entity.nome,
                item["mq"], item["aq"], item["mr"], item["ar"], item["cap"],
                item["can"], achievement, billing, capture, cancellation,
                billing + capture + cancellation, classified,
            ))
        classified = sorted(
            (row for row in entries if row.classified),
            key=lambda row: (
                -row.score,
                -(row.achievement or zero),
                -row.captures,
                row.cancellations,
                row.entity_code,
            ),
        )
        ranked = []
        for index, row in enumerate(classified):
            key = (
                row.score, row.achievement, row.captures, row.cancellations,
            )
            previous_key = (
                (
                    classified[index - 1].score,
                    classified[index - 1].achievement,
                    classified[index - 1].captures,
                    classified[index - 1].cancellations,
                )
                if index else None
            )
            position = ranked[-1].position if previous_key == key else index + 1
            tied = sum(
                (
                    candidate.score,
                    candidate.achievement,
                    candidate.captures,
                    candidate.cancellations,
                ) == key
                for candidate in classified
            ) > 1
            award = None if tied else AwardService.value_for_position(position)
            ranked.append(self._replace(row, position=position, technical_tie=tied, award=award))
        return ranked + sorted((row for row in entries if not row.classified),
                               key=lambda row: row.entity_code)

    def annual(self, year: int) -> list[AnnualRankingEntry]:
        quarters = [self.quarterly(year, quarter) for quarter in range(1, 5)]
        entities = {row.entity_id: row for rows in quarters for row in rows}
        result = []
        for entity_id, entity in entities.items():
            per_quarter = [next((r for r in rows if r.entity_id == entity_id), None)
                           for rows in quarters]
            awards = [row.award for row in per_quarter if row and row.award is not None]
            result.append(AnnualRankingEntry(
                entity_id, entity.entity_code, entity.entity_name,
                tuple(row.position if row else None for row in per_quarter),
                sum(bool(row and row.classified) for row in per_quarter),
                len(awards), sum(awards, Decimal("0")),
            ))
        return sorted(result, key=lambda row: row.entity_code)

    @staticmethod
    def _replace(row: RankingEntry, **changes) -> RankingEntry:
        values = {field: getattr(row, field) for field in row.__dataclass_fields__}
        values.update(changes)
        return RankingEntry(**values)
