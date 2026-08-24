from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import InvestmentBalanceError, InvestmentValidationError
from app.repositories.investment_repository import InvestmentRepository
from app.services.investment_service import InvestmentService


@pytest.fixture
def service(db_session):
    return InvestmentService(InvestmentRepository(db_session))


def test_create_application_redemption_and_lists(service):
    application = service.create_application(
        movement_date=date(2026, 7, 1), description=" Aplicação ",
        value=Decimal("10000.0000"), notes=" Banco ",
    )
    redemption = service.create_redemption(
        movement_date=date(2026, 7, 10), description="Resgate",
        value="3000.0000",
    )
    assert application.periodo_ano == 2026 and application.periodo_mes == 7
    assert application.descricao == "Aplicação" and application.observacao == "Banco"
    assert redemption.tipo == "RESGATE"
    assert service.get_movement(application.id) is application
    assert service.list_movements() == [application, redemption]
    assert service.list_by_period(2026, 7) == [application, redemption]
    assert service.get_applied_balance() == Decimal("7000.0000")


def test_multiple_movements_and_equal_balance_redemption(service):
    service.create_application(
        movement_date=date(2026, 7, 1), description="A1", value=Decimal("6000")
    )
    service.create_application(
        movement_date=date(2026, 7, 2), description="A2", value=Decimal("4000")
    )
    service.create_redemption(
        movement_date=date(2026, 7, 3), description="R1", value=Decimal("2500")
    )
    service.create_redemption(
        movement_date=date(2026, 7, 4), description="R2", value=Decimal("7500")
    )
    assert service.get_applied_balance() == Decimal("0.0000")


def test_redemption_greater_than_or_without_balance_is_rejected(service):
    with pytest.raises(InvestmentBalanceError):
        service.create_redemption(
            movement_date=date(2026, 7, 1), description="Sem saldo", value="1"
        )
    service.create_application(
        movement_date=date(2026, 7, 1), description="Aplicação", value="100"
    )
    with pytest.raises(InvestmentBalanceError, match="Saldo disponível"):
        service.create_redemption(
            movement_date=date(2026, 7, 2), description="Excessivo", value="101"
        )


def test_temporal_order_does_not_use_future_application(service):
    service.create_application(
        movement_date=date(2026, 7, 1), description="Primeira", value="10000"
    )
    service.create_application(
        movement_date=date(2026, 7, 20), description="Futura", value="5000"
    )
    assert service.get_applied_balance(date(2026, 7, 10)) == Decimal("10000.0000")
    with pytest.raises(InvestmentBalanceError):
        service.create_redemption(
            movement_date=date(2026, 7, 10), description="Resgate", value="12000"
        )
    assert service.get_applied_balance(date(2026, 7, 31)) == Decimal("15000.0000")


def test_backdated_redemption_cannot_make_future_balance_negative(service):
    service.create_application(
        movement_date=date(2026, 7, 1), description="Aplicação", value="10000"
    )
    service.create_redemption(
        movement_date=date(2026, 7, 20), description="Resgate futuro", value="8000"
    )
    with pytest.raises(InvestmentBalanceError):
        service.create_redemption(
            movement_date=date(2026, 7, 10), description="Retroativo", value="5000"
        )
    assert service.get_applied_balance() == Decimal("2000.0000")


def test_monthly_summary_uses_history_until_period_end(service):
    service.create_application(
        movement_date=date(2026, 6, 30), description="Anterior", value="1000"
    )
    service.create_application(
        movement_date=date(2026, 7, 5), description="Aplicação", value="10000"
    )
    service.create_redemption(
        movement_date=date(2026, 7, 20), description="Resgate", value="2500"
    )
    summary = service.get_monthly_summary(2026, 7)
    assert summary.applications == Decimal("10000.0000")
    assert summary.redemptions == Decimal("2500.0000")
    assert summary.net_movement == Decimal("7500.0000")
    assert summary.applied_balance == Decimal("8500.0000")


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1"), 1.5])
def test_service_rejects_invalid_values(service, value):
    with pytest.raises(InvestmentValidationError):
        service.create_application(
            movement_date=date(2026, 7, 1), description="Teste", value=value
        )


def test_service_rejects_blank_description_and_invalid_period(service):
    with pytest.raises(InvestmentValidationError):
        service.create_application(
            movement_date=date(2026, 7, 1), description=" ", value="1"
        )
    with pytest.raises(InvestmentValidationError):
        service.list_by_period(1999, 7)
    with pytest.raises(InvestmentValidationError):
        service.list_by_period(2026, 13)
