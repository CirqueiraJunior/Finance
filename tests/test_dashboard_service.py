from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import event
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


def test_financial_dashboard_reports_missing_base_without_silent_zero(db_session):
    dashboard, cashflow, *_ = make_services(db_session)
    cashflow.create_indirect_revenue(
        year=2026, month=1, entry_date=date(2026, 1, 10),
        description="Receita", value="100", boe=False,
    )

    result = dashboard.get_financial_dashboard(2026, 1)

    assert result["balance_available"] is False
    assert result["kpis"]["opening_balance"] is None
    assert result["kpis"]["bank_balance"] is None
    assert len(result["monthly"]) == 12


def test_boe_dashboard_unit_value_is_safe_without_queries(db_session):
    dashboard, *_ = make_services(db_session)

    result = dashboard.get_boe_dashboard(2026, 1)

    assert result["queries"] == 0
    assert result["unit_value"] is None


def test_targets_dashboard_todas_and_zero_divisors(db_session):
    dashboard, *_ = make_services(db_session)

    result = dashboard.get_targets_dashboard(2026, 1, indicator="TODAS")

    assert result["indicator"] == "TODAS"
    assert result["total"]["target"] == 0
    assert result["total"]["achievement_percentage"] is None
    assert result["average_ticket"] is None


def test_targets_indicator_filter_changes_total_without_breaking_todas(db_session):
    dashboard, *_ = make_services(db_session)
    entity = Entity(codigo_entidade=7501, nome="Entidade")
    db_session.add(entity); db_session.flush()
    db_session.add_all([
        TargetEntry(entity_id=entity.id, periodo_ano=2026, periodo_mes=5,
                    indicador="CONSULTAS", valor_meta=100, valor_realizado=80),
        TargetEntry(entity_id=entity.id, periodo_ano=2026, periodo_mes=5,
                    indicador="REGISTROS", valor_meta=20, valor_realizado=10),
    ])
    db_session.commit()

    queries = dashboard.get_targets_dashboard(2026, 5, indicator="CONSULTAS")
    all_indicators = dashboard.get_targets_dashboard(2026, 5, indicator="TODAS")

    assert queries["total"]["target"] == Decimal("100.0000")
    assert all_indicators["total"]["target"] == Decimal("120.0000")


def test_financial_dashboard_filters_are_applied_in_sql(db_session):
    dashboard, cashflow, *_ = make_services(db_session)
    cashflow.create_indirect_revenue(
        year=2026, month=5, entry_date=date(2026, 5, 1),
        description="Indireta", value="100", boe=False,
    )
    cashflow.create_expense(
        year=2026, month=5, entry_date=date(2026, 5, 2),
        description="Administrativo", category="ADMINISTRATIVO", value="30",
    )

    revenue = dashboard.get_financial_dashboard(2026, 5, entry_type="RECEITA")
    administrative = dashboard.get_financial_dashboard(
        2026, 5, category="ADMINISTRATIVO"
    )

    assert revenue["kpis"]["indirect_revenue"] == Decimal("100.0000")
    assert revenue["kpis"]["total_expense"] == 0
    assert administrative["kpis"]["total_expense"] == Decimal("30.0000")
    assert administrative["kpis"]["total_revenue"] == 0


def test_financial_dashboard_query_count_is_constant_not_monthly_n_plus_one(db_session):
    dashboard, *_ = make_services(db_session)
    statements = []
    engine = db_session.get_bind()
    listener = lambda *args: statements.append(args[2])
    event.listen(engine, "before_cursor_execute", listener)
    try:
        dashboard.get_financial_dashboard(2026, 6)
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert len(statements) <= 10


def test_boe_dashboard_contract_never_contains_products(db_session):
    dashboard, *_ = make_services(db_session)
    payload = dashboard.get_boe_dashboard(2026, 5)
    serialized_keys = {str(key).lower() for key in payload}
    assert "product" not in serialized_keys
    assert "produto" not in serialized_keys


def _add_period_dashboard_data(db_session):
    entities = [
        Entity(codigo_entidade=7501, nome="Entidade 1"),
        Entity(codigo_entidade=7502, nome="Entidade 2"),
    ]
    db_session.add_all(entities)
    db_session.flush()
    for selected_month in (2, 7):
        imported = BOEImport(
            periodo_ano=2026,
            periodo_mes=selected_month,
            nome_arquivo=f"BOE - {selected_month:02d}.26.xlsx",
            caminho_origem=f"C:/fonte/BOE - {selected_month:02d}.26.xlsx",
            hash_arquivo=str(selected_month) * 64,
            quantidade_entidades=2,
            quantidade_inconsistencias=0,
            valor_total=Decimal(selected_month * 10),
            status="imported",
        )
        db_session.add(imported)
        db_session.flush()
        for index, entity in enumerate(entities, start=1):
            db_session.add(BOEEntityTotal(
                boe_import_id=imported.id,
                entity_id=entity.id,
                codigo_entidade_origem=entity.codigo_entidade,
                nome_entidade_origem=entity.nome,
                quantidade_consultas=selected_month * index,
                valor_total=Decimal(selected_month * index * 10),
            ))
            db_session.add(TargetEntry(
                entity_id=entity.id,
                periodo_ano=2026,
                periodo_mes=selected_month,
                indicador="CONSULTAS",
                valor_meta=Decimal(selected_month * index * 100),
                valor_realizado=Decimal(selected_month * index * 80),
            ))
    db_session.commit()
    return entities


def test_boe_dashboard_period_is_optional_inclusive_and_keeps_selected_month(db_session):
    dashboard, *_ = make_services(db_session)
    entity = _add_period_dashboard_data(db_session)[0]

    legacy = dashboard.get_boe_dashboard(2026, 7, entity.id)
    filtered = dashboard.get_boe_dashboard(2026, 7, entity.id, 2, 7)

    assert [row["month"] for row in legacy["monthly"]] == list(range(1, 13))
    assert [row["month"] for row in filtered["monthly"]] == list(range(2, 8))
    assert filtered["monthly"][0]["queries"] == 2
    assert filtered["monthly"][-1]["queries"] == 7
    assert filtered["queries"] == legacy["queries"] == 7
    assert filtered["total_value"] == legacy["total_value"] == Decimal("70.0000")
    assert [row["id"] for row in filtered["entities"]] == [entity.id]


def test_targets_dashboard_period_is_optional_inclusive_and_keeps_selected_month(db_session):
    dashboard, *_ = make_services(db_session)
    entity = _add_period_dashboard_data(db_session)[0]

    legacy = dashboard.get_targets_dashboard(2026, 7, entity.id, "TODAS")
    filtered = dashboard.get_targets_dashboard(2026, 7, entity.id, "TODAS", 2, 7)

    assert [row["month"] for row in legacy["monthly"]] == list(range(1, 13))
    assert [row["month"] for row in filtered["monthly"]] == list(range(2, 8))
    assert filtered["monthly"][0]["queries_target"] == Decimal("200.0000")
    assert filtered["monthly"][-1]["queries_target"] == Decimal("700.0000")
    assert filtered["total"] == legacy["total"]
    assert filtered["queries"] == legacy["queries"]


@pytest.mark.parametrize("start_month,end_month", [(0, 12), (1, 13), (8, 7)])
@pytest.mark.parametrize("method", ["get_boe_dashboard", "get_targets_dashboard"])
def test_dashboard_period_rejects_invalid_limits(
    db_session, method, start_month, end_month,
):
    dashboard, *_ = make_services(db_session)

    with pytest.raises(ValueError):
        getattr(dashboard, method)(
            2026, 7, start_month=start_month, end_month=end_month
        )


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
    revenue_source = BOEImport(
        periodo_ano=2026,
        periodo_mes=6,
        nome_arquivo="BOE - 06.26.xlsx",
        caminho_origem="C:/fonte/BOE - 06.26.xlsx",
        hash_arquivo="8" * 64,
        quantidade_entidades=0,
        quantidade_inconsistencias=0,
        valor_total=Decimal("21967.2684"),
        status="imported",
    )
    boe.repository.add_import(revenue_source)
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
    cashflow.create_direct_revenue_from_boe(revenue_source, commit=False)
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


def test_dashboard_data_forwards_period_filters(db_session, monkeypatch):
    dashboard, *_ = make_services(db_session)
    captured = {}
    monkeypatch.setattr(dashboard, "get_financial_dashboard", lambda *a, **k: {})
    def boe(year, month, entity_id=None, start_month=None, end_month=None):
        captured["boe"]=(year,month,entity_id,start_month,end_month); return {}
    def targets(year, month, entity_id=None, indicator="TODAS", start_month=None, end_month=None):
        captured["targets"]=(year,month,entity_id,indicator,start_month,end_month); return {}
    monkeypatch.setattr(dashboard, "get_boe_dashboard", boe)
    monkeypatch.setattr(dashboard, "get_targets_dashboard", targets)
    dashboard.get_dashboard_data(2026,7,boe_entity_id=10,boe_start_month=2,boe_end_month=7,target_entity_id=20,target_start_month=3,target_end_month=8,indicator="CONSULTAS")
    assert captured["boe"] == (2026,7,10,2,7)
    assert captured["targets"] == (2026,7,20,"CONSULTAS",3,8)
