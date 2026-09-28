from decimal import Decimal
from types import SimpleNamespace

from openpyxl import Workbook
from sqlalchemy import select

from app.models.cashflow_entry import CashflowEntry
from app.models.financial_balance_entry import FinancialBalanceEntry
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.financial_balance_repository import FinancialBalanceRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.cashflow_service import CashflowService
from app.services.financial_balance_service import FinancialBalanceService
from app.services.financial_flow_service import FinancialFlowService
from app.services.financial_import_service import FinancialImportService
from app.services.investment_service import InvestmentService


class CatalogStub:
    @staticmethod
    def list_entries():
        return [
            SimpleNamespace(
                descricao="Repasse CDL's Estado GO",
                categoria="RECEITA_DIRETA",
                tipo="RECEITA",
                ativa=True,
            )
        ]


def test_import_persists_historical_direct_and_opens_financial_position(
    db_session, tmp_path,
):
    path = tmp_path / "fluxo_historico.xlsx"

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lancamentos"

    sheet.append([])
    sheet.append([
        "Ano", "Mes", "Descricao", "Observacao",
        "Categoria", "Tipo", "Valor", "BOE",
    ])

    sheet.append([
        2025, "JAN", None, "Saldo Inicial",
        None, None, 17174.42, "Nao",
    ])

    sheet.append([
        2025, "JAN", "Repasse CDL's Estado GO", None,
        "Receita Direta", "Receita", 14691.49, "Nao",
    ])

    workbook.save(path)

    service = FinancialImportService(db_session, CatalogStub())

    validation, entries = service.stage_import(path)
    assert validation.can_import is True

    db_session.commit()

    balance = db_session.scalar(
        select(FinancialBalanceEntry).where(
            FinancialBalanceEntry.year == 2025,
            FinancialBalanceEntry.month == 1,
            FinancialBalanceEntry.balance_type == "SALDO_INICIAL",
        )
    )

    direct = db_session.scalar(
        select(CashflowEntry).where(
            CashflowEntry.periodo_ano == 2025,
            CashflowEntry.periodo_mes == 1,
            CashflowEntry.categoria == "RECEITA_DIRETA",
            CashflowEntry.origem == "MANUAL",
        )
    )

    assert balance is not None
    assert balance.value == Decimal("17174.4200")

    assert direct is not None
    assert direct.valor == Decimal("14691.4900")

    cashflow = CashflowService(CashflowRepository(db_session))
    investments = InvestmentService(InvestmentRepository(db_session))
    flow = FinancialFlowService(cashflow, investments)

    position = FinancialBalanceService(
        FinancialBalanceRepository(db_session),
        flow,
    ).position(2025, 1)

    assert position is not None
    assert position.opening_balance == Decimal("17174.4200")
