from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import select

from app.importers.historical_importer import HistoricalWorkbookImporter
from app.models.boe_import import BOEImport
from app.models.cashflow_entry import CashflowEntry
from app.models.financial_balance_entry import FinancialBalanceEntry
from app.models.investment_movement import InvestmentMovement
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.financial_balance_repository import FinancialBalanceRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.cashflow_service import CashflowService
from app.services.financial_balance_service import FinancialBalanceService
from app.services.financial_flow_service import FinancialFlowService
from app.services.historical_import_service import HistoricalImportService
from app.services.investment_service import InvestmentService


def _balance_service(session):
    flow = FinancialFlowService(CashflowService(CashflowRepository(session)),
                                InvestmentService(InvestmentRepository(session)))
    return FinancialBalanceService(FinancialBalanceRepository(session), flow)


def _official_fixture(session):
    session.add(FinancialBalanceEntry(
        year=2026, month=1, balance_type="SALDO_INICIAL", value=Decimal("4900.77"),
        description="Saldo Inicial", notes="Saldo Inicial = Saldo Final anterior"))
    sources = []
    for index, (year, month, value) in enumerate((
        (2025, 12, 0), (2026, 1, 0), (2026, 2, 0),
        (2026, 3, 100), (2026, 4, 0), (2026, 5, 0),
    )):
        sources.append(BOEImport(
            periodo_ano=year, periodo_mes=month, nome_arquivo=f"boe-{year}-{month}.xlsx",
            caminho_origem="fixture", hash_arquivo=f"{index + 1:064d}",
            quantidade_entidades=1, quantidade_inconsistencias=0,
            valor_total=value, status="imported",
        ))
    session.add_all(sources); session.flush()
    session.add_all([
        CashflowEntry(periodo_ano=2026, periodo_mes=4, data_lancamento=date(2026, 4, 1),
                      descricao="Receita Direta", tipo="RECEITA", origem="BOE",
                      categoria="RECEITA_DIRETA", valor=100,
                      boe_import_id=sources[3].id, boe=False),
        CashflowEntry(periodo_ano=2026, periodo_mes=4, data_lancamento=date(2026, 4, 2),
                      descricao="Despesa BOE", tipo="DESPESA", origem="MANUAL",
                      categoria="OPERACIONAL", valor=20, boe=True),
        CashflowEntry(periodo_ano=2026, periodo_mes=4, data_lancamento=date(2026, 4, 3),
                      descricao="Despesa comum", tipo="DESPESA", origem="MANUAL",
                      categoria="OPERACIONAL", valor=Decimal("4763.06"), boe=False),
        CashflowEntry(periodo_ano=2026, periodo_mes=5, data_lancamento=date(2026, 5, 1),
                      descricao="Receita Indireta", tipo="RECEITA", origem="MANUAL",
                      categoria="RECEITA_INDIRETA", valor=Decimal("10960.49"), boe=False),
        CashflowEntry(periodo_ano=2026, periodo_mes=6, data_lancamento=date(2026, 6, 1),
                      descricao="Despesa", tipo="DESPESA", origem="MANUAL",
                      categoria="OPERACIONAL", valor=Decimal("9314.74"), boe=False),
        InvestmentMovement(data_movimento=date(2026, 6, 2), periodo_ano=2026,
                           periodo_mes=6, tipo="APLICACAO", descricao="Aplicação", valor=100),
        FinancialBalanceEntry(year=2026, month=6, balance_type="SALDO_APLICADO",
                              value=500, description="Saldo Aplicado"),
    ])
    session.commit()


def test_official_balance_rollforward_and_formulas(db_session):
    _official_fixture(db_session)
    service = _balance_service(db_session)
    april, may, june = (service.position(2026, month) for month in (4, 5, 6))

    assert april.net_revenue == Decimal("80.0000")
    assert april.monthly_movement == Decimal("-4683.0600")
    assert (april.opening_balance, april.bank_balance) == (
        Decimal("4900.7700"), Decimal("217.7100"))
    assert (may.opening_balance, may.bank_balance) == (
        Decimal("217.7100"), Decimal("11178.2000"))
    assert (june.opening_balance, june.bank_balance) == (
        Decimal("11178.2000"), Decimal("1763.4600"))
    assert june.applied_balance == Decimal("500.0000")


def test_missing_initial_balance_is_explicit(db_session):
    assert _balance_service(db_session).position(2026, 1) is None


def test_missing_previous_boe_is_explicit_even_with_initial_balance(db_session):
    db_session.add(FinancialBalanceEntry(
        year=2026, month=1, balance_type="SALDO_INICIAL",
        value=Decimal("4900.77"), description="Saldo Inicial",
    ))
    db_session.commit()
    assert _balance_service(db_session).position(2026, 1) is None


def test_latest_initial_balance_allows_controlled_january_2026_cutover(db_session):
    db_session.add_all([
        FinancialBalanceEntry(
            year=2025, month=1, balance_type="SALDO_INICIAL",
            value=Decimal("17174.42"), description="Saldo Inicial 2025",
        ),
        FinancialBalanceEntry(
            year=2026, month=1, balance_type="SALDO_INICIAL",
            value=Decimal("639.20"), description="Saldo Inicial 2026",
        ),
        CashflowEntry(
            periodo_ano=2026, periodo_mes=1, data_lancamento=date(2026, 1, 1),
            descricao="Repasse histórico", tipo="RECEITA", origem="MANUAL",
            categoria="RECEITA_DIRETA", valor=Decimal("12870.01"), boe=False,
        ),
        CashflowEntry(
            periodo_ano=2026, periodo_mes=1, data_lancamento=date(2026, 1, 2),
            descricao="Despesa BOE", tipo="DESPESA", origem="MANUAL",
            categoria="PESSOAL", valor=Decimal("10618.08"), boe=True,
        ),
        CashflowEntry(
            periodo_ano=2026, periodo_mes=1, data_lancamento=date(2026, 1, 3),
            descricao="Despesa comum", tipo="DESPESA", origem="MANUAL",
            categoria="ADMINISTRATIVO", valor=Decimal("1099.03"), boe=False,
        ),
        InvestmentMovement(
            data_movimento=date(2026, 1, 4), periodo_ano=2026,
            periodo_mes=1, tipo="RESGATE", descricao="Resgate", valor=500,
        ),
    ])
    db_session.commit()

    position = _balance_service(db_session).position(2026, 1)

    assert position.net_revenue == Decimal("2251.9300")
    assert position.monthly_movement == Decimal("1652.9000")
    assert position.opening_balance == Decimal("639.2000")
    assert position.bank_balance == Decimal("2292.1000")


def test_parser_and_import_service_preserve_technical_balances_idempotently(
    db_session, tmp_path,
):
    path = tmp_path / "fluxo.xlsx"
    workbook = Workbook(); sheet = workbook.active; sheet.title = "Lançamentos"
    sheet.append([])
    sheet.append(["Ano", "Mês", "Descrição", "Observação", "Categoria", "Tipo", "Valor", "BOE"])
    sheet.append([2026, "JAN", None, "Saldo Inicial", None, None, 4900.77, "Não"])
    sheet.append([2026, "JUN", "Saldo Aplicado", None, "Saldo Aplicado", "Saldo", 500, "Não"])
    workbook.save(path)
    importer = HistoricalWorkbookImporter()
    preview = importer.parse(path)
    service = HistoricalImportService(db_session, importer, None, None, None, None)
    service._validate_cashflow(preview)
    assert {row["balance_type"] for row in preview.rows} == {"SALDO_INICIAL", "SALDO_APLICADO"}
    service._mark_duplicates(preview)
    for row in preview.rows: service._persist("FLUXO_CAIXA", row)
    db_session.commit()
    assert db_session.scalars(select(FinancialBalanceEntry)).all()
    assert db_session.scalars(select(CashflowEntry)).all() == []
    second = importer.parse(path); service._validate_cashflow(second); service._mark_duplicates(second)
    assert second.duplicates == 2
