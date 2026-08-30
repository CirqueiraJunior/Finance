from datetime import date
from decimal import Decimal

from app.importers.boe_importer import BOEImporter
from app.models.boe_entity_total import BOEEntityTotal
from app.models.boe_import import BOEImport
from app.models.entity import Entity
from app.models.target_entry import TargetEntry
from app.repositories.boe_repository import BOERepository
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.investment_repository import InvestmentRepository
from app.repositories.target_repository import TargetRepository
from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService
from app.services.cashflow_service import CashflowService
from app.services.dashboard_service import DashboardService
from app.services.financial_flow_service import FinancialFlowService
from app.services.investment_service import InvestmentService
from app.services.target_service import TargetService


def make_services(db_session):
    cashflow = CashflowService(CashflowRepository(db_session))
    investments = InvestmentService(InvestmentRepository(db_session))
    boe = BOEService(
        BOERepository(db_session), EntityRepository(db_session), BOEImporter(), cashflow
    )
    budget = BudgetService(BudgetRepository(db_session), CashflowRepository(db_session))
    targets = TargetService(TargetRepository(db_session), EntityRepository(db_session))
    dashboard = DashboardService(
        FinancialFlowService(cashflow, investments), boe, budget, targets
    )
    return dashboard, cashflow, investments, boe, budget, targets


def add_entities(db_session):
    entities = [
        Entity(codigo_entidade=7501 + index, nome=f"Entidade {index + 1}")
        for index in range(77)
    ]
    db_session.add_all(entities)
    db_session.commit()
    return entities


def add_boe(db_session, services, entities):
    _, cashflow, _, boe, _, _ = services
    imported = BOEImport(
        periodo_ano=2026,
        periodo_mes=7,
        nome_arquivo="BOE - 07.26.xlsx",
        caminho_origem="C:/fonte/BOE - 07.26.xlsx",
        hash_arquivo="9" * 64,
        quantidade_entidades=77,
        quantidade_inconsistencias=0,
        valor_total=Decimal("21967.2684"),
        status="imported",
    )
    boe.repository.add_import(imported)
    for index, entity in enumerate(entities):
        boe.repository.add_entity_total(
            BOEEntityTotal(
                boe_import_id=imported.id,
                entity_id=entity.id,
                codigo_entidade_origem=entity.codigo_entidade,
                nome_entidade_origem=entity.nome,
                quantidade_consultas=316988 if index == 0 else 0,
                valor_total=Decimal("21967.2684") if index == 0 else Decimal("0"),
            )
        )
    cashflow.create_direct_revenue_from_boe(imported, commit=False)
    db_session.commit()


def add_financial(services):
    _, cashflow, investments, _, budget, _ = services
    cashflow.create_indirect_revenue(
        year=2026, month=7, entry_date=date(2026, 7, 2),
        description="Receita indireta", value="100.0000",
    )
    cashflow.create_expense(
        year=2026, month=7, entry_date=date(2026, 7, 3),
        description="Despesa", category="ADMINISTRATIVO", value="500.0000",
    )
    investments.create_application(
        movement_date=date(2026, 7, 4), description="Aplicação", value="10000.0000"
    )
    investments.create_redemption(
        movement_date=date(2026, 7, 5), description="Resgate", value="2500.0000"
    )
    budget.create_budget(
        year=2026, month=7, entry_type="RECEITA",
        category="RECEITA_DIRETA", budgeted_value="20000.0000",
    )
    budget.create_budget(
        year=2026, month=7, entry_type="RECEITA",
        category="RECEITA_INDIRETA", budgeted_value="200.0000",
    )
    budget.create_budget(
        year=2026, month=7, entry_type="DESPESA",
        category="ADMINISTRATIVO", budgeted_value="2000.0000",
    )


def add_targets(db_session, entities):
    for indicator, target, actual in (
        ("CONSULTAS", Decimal("1271634.8800"), Decimal("1153124.2400")),
        ("REGISTROS", Decimal("166763.9400"), Decimal("173762.6500")),
    ):
        for index, entity in enumerate(entities):
            db_session.add(
                TargetEntry(
                    entity_id=entity.id,
                    periodo_ano=2026,
                    periodo_mes=7,
                    indicador=indicator,
                    valor_meta=target if index == 0 else Decimal("0"),
                    valor_realizado=actual if index == 0 else Decimal("0"),
                )
            )
    db_session.commit()


def test_complete_dashboard_summary_uses_existing_services(db_session):
    services = make_services(db_session)
    entities = add_entities(db_session)
    add_boe(db_session, services, entities)
    add_financial(services)
    add_targets(db_session, entities)

    summary = services[0].get_dashboard_summary(2026, 7)

    assert summary.financial.total_revenue == Decimal("22067.2684")
    assert summary.financial.total_expense == Decimal("500.0000")
    assert summary.financial.operational_result == Decimal("21567.2684")
    assert summary.financial.applications == Decimal("10000.0000")
    assert summary.financial.redemptions == Decimal("2500.0000")
    assert summary.financial.cash_movement == Decimal("14067.2684")
    assert summary.financial.applied_balance == Decimal("7500.0000")
    assert summary.boe.entities == 77
    assert summary.boe.queries == 316988
    assert summary.boe.total_value == Decimal("21967.2684")
    assert summary.budget.budgeted_revenue == Decimal("20200.0000")
    assert summary.budget.actual_revenue == Decimal("22067.2684")
    assert summary.budget.budgeted_expense == Decimal("2000.0000")
    assert summary.budget.actual_expense == Decimal("500.0000")
    assert summary.budget.budgeted_result == Decimal("18200.0000")
    assert summary.budget.actual_result == Decimal("21567.2684")
    assert summary.targets.queries.target == Decimal("1271634.8800")
    assert summary.targets.queries.actual == Decimal("1153124.2400")
    assert summary.targets.queries.achievement_percentage == Decimal("90.6805")
    assert summary.targets.registrations.target == Decimal("166763.9400")
    assert summary.targets.registrations.actual == Decimal("173762.6500")
    assert summary.targets.registrations.achievement_percentage == Decimal("104.1968")
    assert isinstance(summary.financial.total_revenue, Decimal)


def test_empty_period_returns_zeros_and_absence_states(db_session):
    dashboard, *_ = make_services(db_session)
    summary = dashboard.get_dashboard_summary(2026, 8)

    assert summary.financial.total_revenue == Decimal("0.0000")
    assert summary.financial.applied_balance == Decimal("0.0000")
    assert not summary.boe.has_data
    assert summary.budget.budgeted_revenue == Decimal("0.0000")
    assert not summary.targets.queries.has_data
    assert not summary.targets.registrations.has_data


def test_period_without_boe_does_not_block_financial_data(db_session):
    services = make_services(db_session)
    _, cashflow, *_ = services
    cashflow.create_indirect_revenue(
        year=2026, month=7, entry_date=date(2026, 7, 1),
        description="Receita", value="100",
    )

    summary = services[0].get_dashboard_summary(2026, 7)

    assert summary.financial.total_revenue == Decimal("100.0000")
    assert not summary.boe.has_data


def test_period_without_budget_keeps_actual_values(db_session):
    services = make_services(db_session)
    _, cashflow, *_ = services
    cashflow.create_expense(
        year=2026, month=7, entry_date=date(2026, 7, 1),
        description="Despesa", category="ADMINISTRATIVO", value="50",
    )

    summary = services[0].get_dashboard_summary(2026, 7)

    assert summary.budget.budgeted_expense == Decimal("0.0000")
    assert summary.budget.actual_expense == Decimal("50.0000")


def test_period_without_targets_keeps_other_modules(db_session):
    services = make_services(db_session)
    _, cashflow, *_ = services
    cashflow.create_indirect_revenue(
        year=2026, month=7, entry_date=date(2026, 7, 1),
        description="Receita", value="100",
    )

    summary = services[0].get_dashboard_summary(2026, 7)

    assert summary.financial.total_revenue == Decimal("100.0000")
    assert not summary.targets.queries.has_data


def test_zero_target_has_null_achievement(db_session):
    services = make_services(db_session)
    entity = add_entities(db_session)[0]
    services[-1].create_target(
        entity_id=entity.id, year=2026, month=7, indicator="CONSULTAS",
        target_value="0", actual_value="10",
    )

    summary = services[0].get_dashboard_summary(2026, 7)

    assert summary.targets.queries.has_data
    assert summary.targets.queries.achievement_percentage is None
