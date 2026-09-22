from collections import defaultdict
from decimal import Decimal

from sqlalchemy import case, func, select
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

    def financial_year(self, year: int, category: str | None = None,
                       entry_type: str | None = None) -> dict:
        cash = select(
            CashflowEntry.periodo_mes,
            func.sum(case((CashflowEntry.categoria == "RECEITA_INDIRETA",
                           CashflowEntry.valor), else_=0)).label("indirect"),
            func.sum(case((CashflowEntry.tipo == "DESPESA",
                           CashflowEntry.valor), else_=0)).label("expense"),
            func.sum(case(((CashflowEntry.tipo == "DESPESA") & CashflowEntry.boe,
                           CashflowEntry.valor), else_=0)).label("boe_expense"),
        ).where(
            CashflowEntry.periodo_ano == year,
            CashflowEntry.categoria != "RECEITA_DIRETA",
        )
        if category:
            cash = cash.where(CashflowEntry.categoria == category)
        if entry_type:
            cash = cash.where(CashflowEntry.tipo == entry_type)
        cash = cash.group_by(CashflowEntry.periodo_mes)
        cash_rows = {row.periodo_mes: row for row in self.session.execute(cash)}

        investments = select(
            InvestmentMovement.periodo_mes,
            func.sum(case((InvestmentMovement.tipo == "APLICACAO",
                           InvestmentMovement.valor), else_=0)).label("applications"),
            func.sum(case((InvestmentMovement.tipo == "RESGATE",
                           InvestmentMovement.valor), else_=0)).label("redemptions"),
        ).where(InvestmentMovement.periodo_ano == year).group_by(
            InvestmentMovement.periodo_mes
        )
        investment_rows = {row.periodo_mes: row for row in self.session.execute(investments)}

        budget = select(
            BudgetEntry.periodo_mes, BudgetEntry.tipo,
            func.sum(BudgetEntry.valor_orcado).label("value"),
        ).where(BudgetEntry.periodo_ano == year)
        if category:
            budget = budget.where(BudgetEntry.categoria == category)
        if entry_type:
            budget = budget.where(BudgetEntry.tipo == entry_type)
        budget_rows = defaultdict(lambda: {"RECEITA": ZERO, "DESPESA": ZERO})
        for row in self.session.execute(budget.group_by(BudgetEntry.periodo_mes,
                                                        BudgetEntry.tipo)):
            budget_rows[row.periodo_mes][row.tipo] = row.value

        source = select(BOEImport.periodo_ano, BOEImport.periodo_mes,
                        BOEImport.valor_total).where(
            BOEImport.status == "imported",
            ((BOEImport.periodo_ano == year) |
             ((BOEImport.periodo_ano == year - 1) & (BOEImport.periodo_mes == 12))),
        )
        direct = {}
        if category in (None, "RECEITA_DIRETA") and entry_type in (None, "RECEITA"):
            for row in self.session.execute(source):
                competence = 1 if row.periodo_mes == 12 else row.periodo_mes + 1
                competence_year = row.periodo_ano + 1 if row.periodo_mes == 12 else row.periodo_ano
                if competence_year == year:
                    direct[competence] = row.valor_total

        applied = {
            row.month: row.value for row in self.session.execute(select(
                FinancialBalanceEntry.month, FinancialBalanceEntry.value
            ).where(FinancialBalanceEntry.year == year,
                    FinancialBalanceEntry.balance_type == "SALDO_APLICADO"))
        }
        distributions = {"revenue": defaultdict(Decimal), "expense": defaultdict(Decimal)}
        distribution_query = select(
            CashflowEntry.tipo, CashflowEntry.categoria,
            func.sum(CashflowEntry.valor).label("value"),
        ).where(CashflowEntry.periodo_ano == year,
                CashflowEntry.categoria != "RECEITA_DIRETA")
        if category:
            distribution_query = distribution_query.where(CashflowEntry.categoria == category)
        if entry_type:
            distribution_query = distribution_query.where(CashflowEntry.tipo == entry_type)
        for row in self.session.execute(distribution_query.group_by(
                CashflowEntry.tipo, CashflowEntry.categoria)):
            distributions["revenue" if row.tipo == "RECEITA" else "expense"][row.categoria] += row.value
        if direct:
            distributions["revenue"]["RECEITA_DIRETA"] = sum(direct.values(), ZERO)
        return {"cash": cash_rows, "investments": investment_rows,
                "budget": budget_rows, "direct": direct, "applied": applied,
                "distributions": distributions}

    def boe_year(self, year: int, entity_id: int | None = None) -> dict:
        statement = select(
            BOEImport.periodo_mes, Entity.id, Entity.codigo_entidade, Entity.nome,
            func.count(BOEEntityTotal.id).label("records"),
            func.sum(BOEEntityTotal.quantidade_consultas).label("queries"),
            func.sum(BOEEntityTotal.valor_total).label("value"),
        ).join(BOEEntityTotal, BOEEntityTotal.boe_import_id == BOEImport.id).join(
            Entity, Entity.id == BOEEntityTotal.entity_id
        ).where(BOEImport.periodo_ano == year, BOEImport.status == "imported")
        if entity_id is not None:
            statement = statement.where(Entity.id == entity_id)
        rows = list(self.session.execute(statement.group_by(
            BOEImport.periodo_mes, Entity.id, Entity.codigo_entidade, Entity.nome
        )))
        entities = {(row.id, row.codigo_entidade, row.nome) for row in rows}
        return {"rows": rows, "entities": sorted(entities, key=lambda x: x[1])}

    def targets_year(self, year: int, entity_id: int | None = None) -> dict:
        statement = select(
            TargetEntry.periodo_mes, TargetEntry.indicador,
            func.count(TargetEntry.id).label("records"),
            func.sum(TargetEntry.valor_meta).label("target"),
            func.sum(TargetEntry.valor_realizado).label("actual"),
        ).where(TargetEntry.periodo_ano == year)
        association = select(
            AssociationEntry.periodo_mes,
            func.sum(AssociationEntry.valor_execucao).label("associations"),
        ).where(AssociationEntry.periodo_ano == year)
        if entity_id is not None:
            statement = statement.where(TargetEntry.entity_id == entity_id)
            association = association.where(AssociationEntry.entity_id == entity_id)
        rows = list(self.session.execute(statement.group_by(
            TargetEntry.periodo_mes, TargetEntry.indicador)))
        association_rows = {row.periodo_mes: row.associations for row in self.session.execute(
            association.group_by(AssociationEntry.periodo_mes))}
        entities = list(self.session.execute(select(
            Entity.id, Entity.codigo_entidade, Entity.nome
        ).where(Entity.codigo_entidade != 7500).order_by(Entity.codigo_entidade)))
        return {"rows": rows, "associations": association_rows, "entities": entities}
