"""Apuração trimestral do Ranking e Premiação Acelera Goiás."""

from dataclasses import dataclass
from decimal import Decimal

from app.models.target_entry import TargetIndicator
from app.models.ranking_parameter import RankingParameter
from app.repositories.association_repository import AssociationRepository
from app.repositories.ranking_parameter_repository import RankingParameterRepository
from app.repositories.target_repository import TargetRepository
from app.services.award_service import AwardService


QUARTER_MONTHS = {1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12)}


@dataclass(frozen=True, slots=True)
class RankingCategoryResult:
    category: str
    label: str
    metric: Decimal
    position: int
    award: Decimal | None


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
    strategy_year: int = 2026
    association_growth_percentage: Decimal | None = None
    average_ticket: Decimal | None = None
    category_results: tuple[RankingCategoryResult, ...] = ()

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


class RankingParametersNotConfiguredError(ValueError):
    pass


class RankingService:
    def __init__(
        self, targets: TargetRepository, associations: AssociationRepository,
        parameters: RankingParameterRepository | None = None,
    ):
        self.targets = targets
        self.associations = associations
        self.parameters = parameters

    def parameters_for_year(self, year: int) -> RankingParameter:
        if self.parameters is not None:
            value = self.parameters.get_by_year(year)
        else:
            value = RankingParameter.defaults_2026() if year == 2026 else None
        if value is None:
            raise RankingParametersNotConfiguredError(
                f"Os parâmetros do Ranking para {year} não foram configurados."
            )
        return value

    def available_years(self) -> list[int]:
        data_years = set(self.targets.available_years()) | set(
            self.associations.available_years()
        )
        parameter_years = (
            set(self.parameters.available_years()) if self.parameters is not None else {2026}
        )
        return sorted(data_years & ({2025} | parameter_years))

    @staticmethod
    def billing_points(
        achievement: Decimal | None, parameters: RankingParameter | None = None,
    ) -> int:
        parameters = parameters or RankingParameter.defaults_2026()
        if achievement is None or achievement < parameters.billing_level_1_min:
            return 0
        if achievement < parameters.billing_level_2_min:
            return parameters.billing_level_1_points
        if achievement < parameters.billing_level_3_min:
            return parameters.billing_level_2_points
        return parameters.billing_level_3_points

    @staticmethod
    def capture_points(
        captures: Decimal, parameters: RankingParameter | None = None,
    ) -> int:
        parameters = parameters or RankingParameter.defaults_2026()
        if captures < parameters.acquisition_level_1_min:
            return 0
        if captures < parameters.acquisition_level_2_min:
            return parameters.acquisition_level_1_points
        if captures < parameters.acquisition_level_3_min:
            return parameters.acquisition_level_2_points
        return parameters.acquisition_level_3_points

    @staticmethod
    def cancellation_points(
        cancellations: Decimal, parameters: RankingParameter | None = None,
    ) -> int:
        parameters = parameters or RankingParameter.defaults_2026()
        return (
            parameters.zero_cancellation_points
            if cancellations == 0 else parameters.positive_cancellation_points
        )

    def quarterly(self, year: int, quarter: int) -> list[RankingEntry]:
        if quarter not in QUARTER_MONTHS:
            raise ValueError("Trimestre deve estar entre 1 e 4.")
        if year == 2025:
            return self._quarterly_2025(quarter)
        return self._quarterly_2026(year, quarter)

    def _quarterly_2026(self, year: int, quarter: int) -> list[RankingEntry]:
        parameters = self.parameters_for_year(year)
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
            classified = (
                achievement is not None
                and achievement >= parameters.minimum_achievement_percent
            )
            billing = self.billing_points(achievement, parameters) if classified else 0
            capture = self.capture_points(item["cap"], parameters) if classified else 0
            cancellation = self.cancellation_points(item["can"], parameters) if classified else 0
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
            award = None if tied else AwardService.value_for_position(position, parameters)
            ranked.append(self._replace(row, position=position, technical_tie=tied, award=award))
        return ranked + sorted((row for row in entries if not row.classified),
                               key=lambda row: row.entity_code)

    def _quarterly_2025(self, quarter: int) -> list[RankingEntry]:
        months = QUARTER_MONTHS[quarter]
        target_rows = [
            row for row in self.targets.list_by_year(2025)
            if row.periodo_mes in months and row.entity.codigo_entidade != 7500
        ]
        all_associations = [
            row for row in self.associations.list_by_year(2025)
            if row.entity.codigo_entidade != 7500
        ]
        data = self._aggregate_2025(target_rows, all_associations, months)
        zero = Decimal("0")
        entries = []
        for entity_id, item in data.items():
            target = item["mq"] + item["mr"]
            actual = item["aq"] + item["ar"]
            achievement = None if target == 0 else actual / target * Decimal("100")
            classified = achievement is not None and achievement >= Decimal("100")
            executions = item["executions"]
            end_associations = executions.get(months[-1])
            if quarter == 1:
                january = executions.get(1)
                start_associations = (
                    None if january is None else
                    january - item["monthly_capture"].get(1, zero)
                    + item["monthly_cancellation"].get(1, zero)
                )
            else:
                start_associations = executions.get(months[0] - 1)
            growth = (
                None if start_associations in (None, zero) or end_associations is None
                else end_associations / start_associations * Decimal("100") - Decimal("100")
            )
            ticket = (
                None if end_associations in (None, zero)
                else actual / end_associations
            )
            entity = item["entity"]
            entries.append(RankingEntry(
                entity_id, entity.codigo_entidade, entity.nome_oficial or entity.nome,
                item["mq"], item["aq"], item["mr"], item["ar"], item["cap"],
                item["can"], achievement, 0, 0, 0, 0, classified,
                strategy_year=2025,
                association_growth_percentage=growth,
                average_ticket=ticket,
            ))
        ranked = self._rank_2025_categories(entries)
        return sorted(
            ranked,
            key=lambda row: (
                not row.classified,
                min((result.position for result in row.category_results), default=10_000),
                row.entity_code,
            ),
        )

    @staticmethod
    def _aggregate_2025(target_rows, association_rows, months):
        zero = Decimal("0")
        data: dict[int, dict] = {}

        def item_for(row):
            return data.setdefault(row.entity_id, {
                "entity": row.entity, "mq": zero, "aq": zero,
                "mr": zero, "ar": zero, "cap": zero, "can": zero,
                "executions": {}, "monthly_capture": {},
                "monthly_cancellation": {},
            })

        for row in target_rows:
            item = item_for(row)
            prefix = "q" if row.indicador == TargetIndicator.QUERIES.value else "r"
            item[f"m{prefix}"] += row.valor_meta
            item[f"a{prefix}"] += row.valor_realizado
        relevant_months = set(months)
        if months[0] > 1:
            relevant_months.add(months[0] - 1)
        for row in association_rows:
            if row.periodo_mes not in relevant_months:
                continue
            item = item_for(row)
            item["executions"][row.periodo_mes] = row.valor_execucao
            item["monthly_capture"][row.periodo_mes] = row.valor_captacao
            item["monthly_cancellation"][row.periodo_mes] = row.valor_cancelamento
            if row.periodo_mes in months:
                item["cap"] += row.valor_captacao
                item["can"] += row.valor_cancelamento
        return data

    @staticmethod
    def _rank_2025_categories(entries: list[RankingEntry]) -> list[RankingEntry]:
        definitions = (
            ("FATURAMENTO", "Faturamento", lambda row: row.achievement),
            ("ASSOCIADOS", "Associados", lambda row: row.association_growth_percentage),
            ("TICKET_MEDIO", "Ticket Médio", lambda row: row.average_ticket),
        )
        results: dict[int, list[RankingCategoryResult]] = {
            row.entity_id: [] for row in entries
        }
        eligible = [row for row in entries if row.classified]
        for category, label, metric_of in definitions:
            candidates = [row for row in eligible if metric_of(row) is not None]
            for row in candidates:
                metric = metric_of(row)
                position = 1 + sum(metric_of(other) > metric for other in candidates)
                results[row.entity_id].append(RankingCategoryResult(
                    category, label, metric, position,
                    AwardService.value_for_2025_category(category, position),
                ))
        ranked = []
        for row in entries:
            category_results = tuple(results[row.entity_id])
            award = sum(
                (result.award for result in category_results if result.award is not None),
                Decimal("0"),
            ) or None
            ranked.append(RankingService._replace(
                row, category_results=category_results, award=award,
            ))
        return ranked

    def annual(self, year: int) -> list[AnnualRankingEntry]:
        quarters = [self.quarterly(year, quarter) for quarter in range(1, 5)]
        entities = {row.entity_id: row for rows in quarters for row in rows}
        result = []
        for entity_id, entity in entities.items():
            per_quarter = [next((r for r in rows if r.entity_id == entity_id), None)
                           for rows in quarters]
            awards = [
                result.award
                for row in per_quarter if row
                for result in (
                    row.category_results
                    if row.strategy_year == 2025
                    else ()
                )
                if result.award is not None
            ]
            if year != 2025:
                awards = [
                    row.award for row in per_quarter
                    if row and row.award is not None
                ]
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
