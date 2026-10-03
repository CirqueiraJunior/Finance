from collections import defaultdict
from decimal import Decimal

from sqlalchemy import case, func, select, union
from sqlalchemy.orm import Session

from app.models.association_entry import AssociationEntry
from app.models.boe_entity_total import BOEEntityTotal
from app.models.boe_import import BOEImport
from app.models.budget_entry import BudgetEntry
from app.models.cashflow_entry import CashflowEntry
from app.models.entity import Entity
from app.models.financial_balance_entry import FinancialBalanceEntry
from app.models.investment_movement import InvestmentMovement
from app.models.target_entry import TargetEntry


ZERO = Decimal("0.0000")


class DashboardRepository:
    """Read-only SQL aggregates used by the three Dashboard areas."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def available_years(self) -> dict[str, list[int]]:
        financial_years_query = union(
            select(CashflowEntry.periodo_ano),
            select(InvestmentMovement.periodo_ano),
            select(BudgetEntry.periodo_ano),
            select(FinancialBalanceEntry.year.label("periodo_ano")),
            select(BOEImport.periodo_ano).where(
                BOEImport.status == "imported"
            ),
            select((BOEImport.periodo_ano + 1).label("periodo_ano")).where(
                BOEImport.status == "imported",
                BOEImport.periodo_mes == 12,
            ),
        ).subquery()
        financial_years = list(self.session.scalars(
            select(financial_years_query.c.periodo_ano).order_by(
                financial_years_query.c.periodo_ano
            )
        ))

        boe_years = list(self.session.scalars(
            select(BOEImport.periodo_ano).where(
                BOEImport.status == "imported"
            ).distinct().order_by(BOEImport.periodo_ano)
        ))
        target_years_query = union(
            select(TargetEntry.periodo_ano).join(
                Entity, Entity.id == TargetEntry.entity_id
            ).where(Entity.codigo_entidade != 7500),
            select(AssociationEntry.periodo_ano).join(
                Entity, Entity.id == AssociationEntry.entity_id
            ).where(Entity.codigo_entidade != 7500),
        ).subquery()
        target_years = list(self.session.scalars(
            select(target_years_query.c.periodo_ano).order_by(
                target_years_query.c.periodo_ano
            )
        ))
        return {
            "financial_years": financial_years,
            "boe_years": boe_years,
            "target_years": target_years,
        }

    def financial_period(
        self, start_year: int, start_month: int,
        end_year: int, end_month: int,
        category: str | None = None,
        entry_type: str | None = None,
    ) -> dict:
        start_key = start_year * 100 + start_month
        end_key = end_year * 100 + end_month

        cash_period = CashflowEntry.periodo_ano * 100 + CashflowEntry.periodo_mes
        cash = select(
            CashflowEntry.periodo_ano,
            CashflowEntry.periodo_mes,
            func.sum(case((CashflowEntry.categoria == "RECEITA_INDIRETA",
                           CashflowEntry.valor), else_=0)).label("indirect"),
            func.sum(case((CashflowEntry.tipo == "DESPESA",
                           CashflowEntry.valor), else_=0)).label("expense"),
            func.sum(case(((CashflowEntry.tipo == "DESPESA") & CashflowEntry.boe,
                           CashflowEntry.valor), else_=0)).label("boe_expense"),
        ).where(
            cash_period.between(start_key, end_key),
            CashflowEntry.categoria != "RECEITA_DIRETA",
        )
        if category:
            cash = cash.where(CashflowEntry.categoria == category)
        if entry_type:
            cash = cash.where(CashflowEntry.tipo == entry_type)
        cash_rows = {
            (row.periodo_ano, row.periodo_mes): row
            for row in self.session.execute(
                cash.group_by(CashflowEntry.periodo_ano, CashflowEntry.periodo_mes)
            )
        }

        investment_period = InvestmentMovement.periodo_ano * 100 + InvestmentMovement.periodo_mes
        investments = select(
            InvestmentMovement.periodo_ano,
            InvestmentMovement.periodo_mes,
            func.sum(case((InvestmentMovement.tipo == "APLICACAO",
                           InvestmentMovement.valor), else_=0)).label("applications"),
            func.sum(case((InvestmentMovement.tipo == "RESGATE",
                           InvestmentMovement.valor), else_=0)).label("redemptions"),
        ).where(
            investment_period.between(start_key, end_key)
        ).group_by(
            InvestmentMovement.periodo_ano, InvestmentMovement.periodo_mes
        )
        investment_rows = {
            (row.periodo_ano, row.periodo_mes): row
            for row in self.session.execute(investments)
        }

        budget_period = BudgetEntry.periodo_ano * 100 + BudgetEntry.periodo_mes
        budget = select(
            BudgetEntry.periodo_ano, BudgetEntry.periodo_mes, BudgetEntry.tipo,
            func.sum(BudgetEntry.valor_orcado).label("value"),
        ).where(budget_period.between(start_key, end_key))
        if category:
            budget = budget.where(BudgetEntry.categoria == category)
        if entry_type:
            budget = budget.where(BudgetEntry.tipo == entry_type)
        budget_rows = defaultdict(lambda: {"RECEITA": ZERO, "DESPESA": ZERO})
        for row in self.session.execute(
            budget.group_by(
                BudgetEntry.periodo_ano, BudgetEntry.periodo_mes, BudgetEntry.tipo
            )
        ):
            budget_rows[(row.periodo_ano, row.periodo_mes)][row.tipo] = row.value

        if start_month == 1:
            source_start_year, source_start_month = start_year - 1, 12
        else:
            source_start_year, source_start_month = start_year, start_month - 1
        if end_month == 1:
            source_end_year, source_end_month = end_year - 1, 12
        else:
            source_end_year, source_end_month = end_year, end_month - 1

        source_period = BOEImport.periodo_ano * 100 + BOEImport.periodo_mes
        source = select(
            BOEImport.periodo_ano, BOEImport.periodo_mes, BOEImport.valor_total
        ).where(
            BOEImport.status == "imported",
            source_period.between(
                source_start_year * 100 + source_start_month,
                source_end_year * 100 + source_end_month,
            ),
        )

        direct = {}
        if category in (None, "RECEITA_DIRETA") and entry_type in (None, "RECEITA"):
            for row in self.session.execute(source):
                competence_year = row.periodo_ano + (1 if row.periodo_mes == 12 else 0)
                competence_month = 1 if row.periodo_mes == 12 else row.periodo_mes + 1
                competence_key = competence_year * 100 + competence_month
                if start_key <= competence_key <= end_key:
                    direct[(competence_year, competence_month)] = row.valor_total

            historical_period = CashflowEntry.periodo_ano * 100 + CashflowEntry.periodo_mes
            historical_query = (
                select(
                    CashflowEntry.periodo_ano,
                    CashflowEntry.periodo_mes,
                    func.sum(CashflowEntry.valor).label("value"),
                )
                .where(
                    historical_period.between(start_key, end_key),
                    historical_period <= 202601,
                    CashflowEntry.categoria == "RECEITA_DIRETA",
                    CashflowEntry.origem == "MANUAL",
                )
                .group_by(CashflowEntry.periodo_ano, CashflowEntry.periodo_mes)
            )
            for historical_row in self.session.execute(historical_query):
                direct.setdefault(
                    (historical_row.periodo_ano, historical_row.periodo_mes),
                    historical_row.value,
                )

        applied_period = FinancialBalanceEntry.year * 100 + FinancialBalanceEntry.month
        applied = {
            (row.year, row.month): row.value
            for row in self.session.execute(
                select(
                    FinancialBalanceEntry.year,
                    FinancialBalanceEntry.month,
                    FinancialBalanceEntry.value,
                ).where(
                    applied_period.between(start_key, end_key),
                    FinancialBalanceEntry.balance_type == "SALDO_APLICADO",
                )
            )
        }

        distributions = {"revenue": defaultdict(Decimal), "expense": defaultdict(Decimal)}
        distribution_query = select(
            CashflowEntry.tipo, CashflowEntry.categoria,
            func.sum(CashflowEntry.valor).label("value"),
        ).where(
            cash_period.between(start_key, end_key),
            CashflowEntry.categoria != "RECEITA_DIRETA",
        )
        if category:
            distribution_query = distribution_query.where(CashflowEntry.categoria == category)
        if entry_type:
            distribution_query = distribution_query.where(CashflowEntry.tipo == entry_type)
        for row in self.session.execute(
            distribution_query.group_by(CashflowEntry.tipo, CashflowEntry.categoria)
        ):
            distributions["revenue" if row.tipo == "RECEITA" else "expense"][row.categoria] += row.value
        if direct:
            distributions["revenue"]["RECEITA_DIRETA"] = sum(direct.values(), ZERO)

        return {
            "cash": cash_rows,
            "investments": investment_rows,
            "budget": budget_rows,
            "direct": direct,
            "applied": applied,
            "distributions": distributions,
        }

    def financial_year(
        self, year: int, category: str | None = None,
        entry_type: str | None = None,
    ) -> dict:
        period = self.financial_period(year, 1, year, 12, category, entry_type)
        return {
            "cash": {m: v for (y, m), v in period["cash"].items() if y == year},
            "investments": {m: v for (y, m), v in period["investments"].items() if y == year},
            "budget": defaultdict(
                lambda: {"RECEITA": ZERO, "DESPESA": ZERO},
                {m: v for (y, m), v in period["budget"].items() if y == year},
            ),
            "direct": {m: v for (y, m), v in period["direct"].items() if y == year},
            "applied": {m: v for (y, m), v in period["applied"].items() if y == year},
            "distributions": period["distributions"],
        }

    def boe_period(
        self, start_year: int, start_month: int,
        end_year: int, end_month: int,
        entity_id: int | None = None,
    ) -> dict:
        period = BOEImport.periodo_ano * 100 + BOEImport.periodo_mes
        statement = select(
            BOEImport.periodo_ano, BOEImport.periodo_mes,
            Entity.id, Entity.codigo_entidade, Entity.nome,
            func.count(BOEEntityTotal.id).label("records"),
            func.sum(BOEEntityTotal.quantidade_consultas).label("queries"),
            func.sum(BOEEntityTotal.valor_total).label("value"),
        ).join(BOEEntityTotal, BOEEntityTotal.boe_import_id == BOEImport.id).join(
            Entity, Entity.id == BOEEntityTotal.entity_id
        ).where(
            BOEImport.status == "imported",
            period.between(start_year * 100 + start_month,
                           end_year * 100 + end_month),
        )
        if entity_id is not None:
            statement = statement.where(Entity.id == entity_id)
        rows = list(self.session.execute(statement.group_by(
            BOEImport.periodo_ano, BOEImport.periodo_mes,
            Entity.id, Entity.codigo_entidade, Entity.nome
        )))
        entities = {(row.id, row.codigo_entidade, row.nome) for row in rows}
        return {"rows": rows, "entities": sorted(entities, key=lambda x: x[1])}

    def boe_year(self, year: int, entity_id: int | None = None) -> dict:
        return self.boe_period(year, 1, year, 12, entity_id)

    def targets_period(
        self, start_year: int, start_month: int,
        end_year: int, end_month: int,
        entity_id: int | None = None,
        region: str | None = None,
    ) -> dict:
        target_period = TargetEntry.periodo_ano * 100 + TargetEntry.periodo_mes
        association_period = (
            AssociationEntry.periodo_ano * 100 + AssociationEntry.periodo_mes
        )
        statement = select(
            TargetEntry.periodo_ano, TargetEntry.periodo_mes,
            TargetEntry.indicador,
            func.count(TargetEntry.id).label("records"),
            func.sum(TargetEntry.valor_meta).label("target"),
            func.sum(TargetEntry.valor_realizado).label("actual"),
        ).join(Entity, Entity.id == TargetEntry.entity_id).where(
            target_period.between(start_year * 100 + start_month,
                                  end_year * 100 + end_month),
            Entity.codigo_entidade != 7500,
        )
        association = select(
            AssociationEntry.periodo_ano, AssociationEntry.periodo_mes,
            func.sum(AssociationEntry.valor_execucao).label("associations"),
        ).join(Entity, Entity.id == AssociationEntry.entity_id).where(
            association_period.between(start_year * 100 + start_month,
                                       end_year * 100 + end_month),
            Entity.codigo_entidade != 7500,
        )
        if entity_id is not None:
            statement = statement.where(TargetEntry.entity_id == entity_id)
            association = association.where(AssociationEntry.entity_id == entity_id)
        if region is not None:
            statement = statement.where(Entity.regiao == region)
            association = association.where(Entity.regiao == region)
        rows = list(self.session.execute(statement.group_by(
            TargetEntry.periodo_ano, TargetEntry.periodo_mes,
            TargetEntry.indicador)))
        association_rows = {
            (row.periodo_ano, row.periodo_mes): row.associations
            for row in self.session.execute(association.group_by(
                AssociationEntry.periodo_ano, AssociationEntry.periodo_mes
            ))
        }
        entities_query = select(
            Entity.id, Entity.codigo_entidade, Entity.nome, Entity.regiao
        ).where(Entity.codigo_entidade != 7500)
        if region is not None:
            entities_query = entities_query.where(Entity.regiao == region)
        entities = list(self.session.execute(
            entities_query.order_by(Entity.codigo_entidade)
        ))
        return {"rows": rows, "associations": association_rows, "entities": entities}

    def targets_year(self, year: int, entity_id: int | None = None) -> dict:
        return self.targets_period(year, 1, year, 12, entity_id)
