"""Adapters do Desktop para os services centralizados na Finance API."""

from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from app.importers.boe_types import (
    BOEIssueSeverity, BOEParsedRow, BOEValidationIssue, BOEValidationResult,
)
from app.services.budget_service import BudgetComparison, BudgetSummary, BudgetVsActual
from app.services.dashboard_service import (
    BOEDashboardSummary, BudgetDashboardSummary, DashboardSummary,
    FinancialDashboardSummary, IndicatorDashboardSummary, TargetDashboardSummary,
)
from app.services.financial_flow_service import FinancialFlowSummary, FinancialMovement
from app.services.ranking_service import AnnualRankingEntry, RankingEntry
from app.services.report_service import AnnualReport, MonthlyReportRow
from app.services.site_csv_service import CSVExportResult, CSVValidationResult
from app.services.target_service import TargetComparison, TargetSummary, TargetVsActual


class _Session:
    def rollback(self):
        return None


class _Repository:
    session = _Session()


def _decimal(value) -> Decimal:
    return Decimal(str(value))


def _entity(item: dict):
    return SimpleNamespace(**item)


def _entry(item: dict):
    converted = dict(item)
    for key in ("valor", "valor_orcado", "valor_meta", "valor_realizado", "valor_total"):
        if key in converted and converted[key] is not None:
            converted[key] = _decimal(converted[key])
    for key in ("data_lancamento", "data_movimento"):
        if key in converted and converted[key]:
            converted[key] = date.fromisoformat(converted[key])
    if isinstance(converted.get("entity"), dict):
        converted["entity"] = _entity(converted["entity"])
    return SimpleNamespace(**converted)


class RemoteCashflowService:
    repository = _Repository()

    def __init__(self, api): self.api = api

    def create_indirect_revenue(self, **values):
        return _entry(self.api.post("/api/v1/cashflow", {
            "periodo_ano": values["year"], "periodo_mes": values["month"],
            "data_lancamento": values["entry_date"].isoformat(),
            "descricao": values["description"], "tipo": "RECEITA",
            "categoria": "RECEITA_INDIRETA", "valor": str(values["value"]),
            "observacao": values.get("notes"), "boe": values.get("boe", False),
        }))

    def create_expense(self, **values):
        return _entry(self.api.post("/api/v1/cashflow", {
            "periodo_ano": values["year"], "periodo_mes": values["month"],
            "data_lancamento": values["entry_date"].isoformat(),
            "descricao": values["description"], "tipo": "DESPESA",
            "categoria": str(values["category"]), "valor": str(values["value"]),
            "observacao": values.get("notes"), "boe": values.get("boe", False),
        }))

    def validate_import(self, file_path):
        return self.api.upload(
            "/api/v1/financial-import/validate", str(file_path)
        )

    def import_file(self, file_path):
        return self.api.upload(
            "/api/v1/financial-import", str(file_path), import_file=True
        )


class RemoteInvestmentService:
    repository = _Repository()

    def __init__(self, api): self.api = api

    def _create(self, movement_type: str, **values):
        return _entry(self.api.post("/api/v1/investments", {
            "movement_type": movement_type,
            "movement_date": values["movement_date"].isoformat(),
            "description": values["description"], "value": str(values["value"]),
            "notes": values.get("notes"),
        }))

    def create_application(self, **values): return self._create("APLICACAO", **values)
    def create_redemption(self, **values): return self._create("RESGATE", **values)

    def get_applied_balance(self, end_date=None):
        data = self.api.get("/api/v1/financial-flow?year=9999&month=12")
        return _decimal(data["summary"]["applied_balance"])


class RemoteFinancialFlowService:
    def __init__(self, api): self.api = api

    def _data(self, year, month): return self.api.get(f"/api/v1/financial-flow?year={year}&month={month}")

    def list_by_period(self, year, month):
        return [FinancialMovement(date.fromisoformat(row["movement_date"]), row["movement_type"],
                                  row["description"], row.get("category"), row.get("origin"),
                                  _decimal(row["value"]), row.get("boe", False))
                for row in self._data(year, month)["items"]]

    def get_summary(self, year, month):
        value = self._data(year, month)["summary"]
        return FinancialFlowSummary(
            *(_decimal(value[key]) for key in (
                "direct_revenue", "indirect_revenue", "total_revenue", "total_expense",
                "applications", "redemptions", "operational_result", "cash_movement",
                "applied_balance",
            )),
            _decimal(value.get("boe_expense", 0)),
        )

    def get_position(self, year, month):
        value = self._data(year, month).get("position")
        if not value:
            return None
        return SimpleNamespace(
            year=value["year"], month=value["month"],
            opening_balance=_decimal(value["opening_balance"]),
            bank_balance=_decimal(value["bank_balance"]),
            net_revenue=_decimal(value["net_revenue"]),
            monthly_movement=_decimal(value["monthly_movement"]),
            applied_balance=_decimal(value["applied_balance"]) if value.get("applied_balance") is not None else None,
        )

    def create_application(self, **values): return RemoteInvestmentService(self.api).create_application(**values)
    def create_redemption(self, **values): return RemoteInvestmentService(self.api).create_redemption(**values)


class RemoteCatalogService:
    def __init__(self, api): self.api = api
    def list_options(self):
        return tuple(SimpleNamespace(description=row["descricao"], category=row.get("categoria"),
                                     movement_type=row.get("tipo"), active=row["ativa"])
                     for row in self.api.get("/api/v1/catalog") if row["ativa"])
    def list_budget_options(self):
        return tuple(SimpleNamespace(description=row["descricao"], category=row["categoria"],
                                     movement_type=row["tipo"])
                     for row in self.api.get("/api/v1/catalog")
                     if row["ativa"] and row["tipo"] in {"RECEITA", "DESPESA"})


class RemoteBOEService:
    repository = _Repository()
    def __init__(self, api): self.api = api

    def validate_file(self, path):
        data = self.api.upload("/api/v1/boe/validate", str(path))
        return BOEValidationResult(Path(data["caminho_arquivo"]), data["nome_arquivo"], data.get("hash_arquivo"),
            data.get("periodo_ano"), data.get("periodo_mes"),
            [BOEParsedRow(r["linha"], r["codigo_entidade"], r["nome_entidade"], r["quantidade_consultas"], _decimal(r["valor_total"])) for r in data["linhas"]],
            [BOEValidationIssue(i["mensagem"], BOEIssueSeverity(i["severidade"]), i.get("linha"), i.get("codigo")) for i in data["inconsistencias"]],
            data.get("quantidade_consolidada"), _decimal(data["valor_consolidado"]) if data.get("valor_consolidado") is not None else None)

    def import_file(self, path): return _entry(self.api.upload("/api/v1/boe/import", str(path)))
    def list_imports(self): return [_entry(row) for row in self.api.get("/api/v1/boe")]
    def get_import_details(self, import_id):
        data = self.api.get(f"/api/v1/boe/{import_id}")
        return SimpleNamespace(boe_import=_entry(data["boe_import"]),
            entities=tuple(SimpleNamespace(**{**row, "value": _decimal(row["value"])}) for row in data["entities"]),
            total_entities=data["total_entities"], total_queries=data["total_queries"],
            total_value=_decimal(data["total_value"]),
            inconsistencies=tuple(SimpleNamespace(**row) for row in data["inconsistencies"]))

    def list_operational_entities(self):
        return tuple(
            (row["id"], row["name"])
            for row in self.api.get("/api/v1/boe/operations/entities")
        )

    def query_operations(self, start_year, start_month, end_year, end_month,
                         entity_id=None):
        path = (
            "/api/v1/boe/operations"
            f"?start_year={start_year}&start_month={start_month}"
            f"&end_year={end_year}&end_month={end_month}"
        )
        if entity_id is not None:
            path += f"&entity_id={entity_id}"
        data = self.api.get(path)
        return SimpleNamespace(
            rows=tuple(SimpleNamespace(
                **{**row, "unit_value": _decimal(row["unit_value"]),
                   "total_value": _decimal(row["total_value"])}
            ) for row in data["rows"]),
            total_queries=data["total_queries"],
            unit_value=_decimal(data["unit_value"]),
            total_value=_decimal(data["total_value"]),
        )


class RemoteBudgetService:
    repository = _Repository()
    def __init__(self, api): self.api = api
    def _data(self, year, month=None):
        suffix = f"?year={year}" + ("" if month is None else f"&month={month}")
        return self.api.get("/api/v1/budgets" + suffix)
    def list_by_period(self, year, month): return [_entry(x) for x in self._data(year, month)["items"]]
    def list_by_year(self, year): return [_entry(x) for x in self._data(year)["items"]]
    def get_budget(self, budget_id): return _entry(self.api.get(f"/api/v1/budgets/{budget_id}"))
    def create_budget(self, **values):
        description = values.get("descricao", values.get("description"))
        payload = {"year": values["year"], "month": values["month"], "entry_type": str(values["entry_type"]),
                   "description": description, "category": str(values["category"]),
                   "budgeted_value": str(values["budgeted_value"]), "notes": values.get("notes")}
        return _entry(self.api.post("/api/v1/budgets", payload))
    def update_budget(self, budget_id, **values):
        description = values.get("descricao", values.get("description"))
        return _entry(self.api.patch(f"/api/v1/budgets/{budget_id}", {
            "description": description,
            "budgeted_value": str(values["budgeted_value"]), "notes": values.get("notes")}))
    def validate_import(self, file_path):
        return self.api.upload(
            "/api/v1/budgets/import/validate", str(file_path)
        )
    def import_file(self, file_path):
        return self.api.upload(
            "/api/v1/budgets/import", str(file_path), import_file=True
        )
    def get_budget_vs_actual(self, year, month=None):
        data = self._data(year, month)["comparison"]
        comparisons = tuple(BudgetComparison(x["entry_type"], x.get("description"), x["category"], _decimal(x["budgeted"]),
            _decimal(x["actual"]), _decimal(x["absolute_variance"]),
            _decimal(x["percentage_variance"]) if x["percentage_variance"] is not None else None) for x in data["comparisons"])
        s = data["summary"]
        return BudgetVsActual(comparisons, BudgetSummary(*(_decimal(s[k]) for k in (
            "budgeted_revenue", "actual_revenue", "budgeted_expense", "actual_expense", "budgeted_result", "actual_result"))))


class RemoteTargetService:
    repository = _Repository()
    def __init__(self, api): self.api = api; self._entities = []
    def _data(self, year, month, indicator, entity_id=None):
        path = f"/api/v1/targets?year={year}&month={month}&indicator={indicator}"
        if entity_id is not None:
            ids = entity_id if isinstance(entity_id, (tuple, list, set)) else (entity_id,)
            path += "".join(f"&entity_id={int(value)}" for value in ids)
        data = self.api.get(path); self._entities = [_entity(x) for x in data["entities"]]; return data
    def list_entities(self):
        if not self._entities:
            self._entities = [
                _entity(x)
                for x in self.api.get("/api/v1/entities")
                if x.get("codigo_entidade") != 7500
            ]
        return self._entities

    def get_target(self, target_id): return _entry(self.api.get(f"/api/v1/targets/{target_id}"))
    def create_target(self, **values):
        payload = {**values, "indicator": str(values["indicator"]), "target_value": str(values["target_value"]),
                   "actual_value": str(values.get("actual_value", 0))}
        return _entry(self.api.post("/api/v1/targets", payload))
    def update_target(self, target_id, **values):
        return _entry(self.api.patch(f"/api/v1/targets/{target_id}", {"target_value": str(values["target_value"]), "notes": values.get("notes")}))
    def validate_import(self, file_path):
        return self.api.upload("/api/v1/targets/import/validate", str(file_path))
    def import_file(self, file_path):
        return self.api.upload(
            "/api/v1/targets/import", str(file_path), import_file=True
        )
    def get_target_vs_actual(self, year, month, indicator, entity_id=None):
        data = self._data(year, month, str(indicator), entity_id)["comparison"]
        rows = tuple(
            TargetComparison(
                x["target_id"],
                x["entity_code"],
                x["entity_name"],
                x["indicator"],
                _decimal(x["target"]),
                _decimal(x["actual"]),
                _decimal(x["difference"]),
                _decimal(x["achievement_percentage"])
                if x["achievement_percentage"] is not None else None,
                x.get("notes"),
            )
            for x in data["comparisons"]
        )
        s = data["summary"]
        return TargetVsActual(
            rows,
            TargetSummary(
                s["entity_count"],
                _decimal(s["target_total"]),
                _decimal(s["actual_total"]),
                _decimal(s["difference_total"]),
                _decimal(s["achievement_percentage"])
                if s["achievement_percentage"] is not None else None,
            ),
        )

class RemoteRankingService:
    def __init__(self, api): self.api = api
    def _data(self, year, quarter): return self.api.get(f"/api/v1/ranking?year={year}&quarter={quarter}")
    def quarterly(self, year, quarter):
        return [RankingEntry(x["entity_id"], x["entity_code"], x["entity_name"], *(_decimal(x[k]) for k in (
            "meta_queries", "actual_queries", "meta_registrations", "actual_registrations", "captures", "cancellations")),
            _decimal(x["achievement"]) if x["achievement"] is not None else None, x["billing_points"], x["capture_points"],
            x["cancellation_points"], x["score"], x["classified"], x.get("position"), x["technical_tie"],
            _decimal(x["award"]) if x.get("award") is not None else None) for x in self._data(year, quarter)["quarterly"]]
    def annual(self, year):
        return [AnnualRankingEntry(x["entity_id"], x["entity_code"], x["entity_name"], tuple(x["positions"]),
            x["classified_quarters"], x["award_count"], _decimal(x["award_total"])) for x in self._data(year, 1)["annual"]]


class RemoteDashboardService:
    def __init__(self, api, areas=None):
        self.api = api
        self.areas = set(areas or {"financial", "boe", "targets"})
    def get_dashboard_data(self, year, month, **filters):
        result = {}
        if "financial" in self.areas:
            path = f"/api/v1/dashboard/financial?year={year}&month={month}"
            if filters.get("category"):
                path += f"&category={filters['category']}"
            if filters.get("entry_type"):
                path += f"&entry_type={filters['entry_type']}"
            result["financial"] = self.api.get(path)
        if "boe" in self.areas:
            path = f"/api/v1/dashboard/boe?year={year}&month={month}"
            if filters.get("boe_start_month"):
                path += f"&start_month={filters['boe_start_month']}"
            if filters.get("boe_end_month"):
                path += f"&end_month={filters['boe_end_month']}"
            if filters.get("boe_entity_id"):
                path += f"&entity_id={filters['boe_entity_id']}"
            result["boe"] = self.api.get(path)
        if "targets" in self.areas:
            indicator = filters.get("indicator", "TODAS")
            path = (f"/api/v1/dashboard/targets?year={year}&month={month}"
                    f"&indicator={indicator}")
            if filters.get("target_start_month"):
                path += f"&start_month={filters['target_start_month']}"
            if filters.get("target_end_month"):
                path += f"&end_month={filters['target_end_month']}"
            if filters.get("target_entity_id"):
                path += f"&entity_id={filters['target_entity_id']}"
            result["targets"] = self.api.get(path)
        return result
    def get_dashboard_summary(self, year, month):
        zero = Decimal("0")
        financial = FinancialDashboardSummary(zero, zero, zero, zero, zero, zero, zero)
        budget = BudgetDashboardSummary(zero, zero, zero, zero, zero, zero)
        boe = BOEDashboardSummary(False, 0, 0, zero)
        empty_indicator = IndicatorDashboardSummary(False, zero, zero, None)
        targets = TargetDashboardSummary(empty_indicator, empty_indicator)
        if "financial" in self.areas:
            data = self.api.get(f"/api/v1/dashboard/financial?year={year}&month={month}")
            if not data.get("balance_available", True):
                raise RuntimeError("Saldo Inicial Base não cadastrado para o período.")
            k, b = data["kpis"], data["budget"]
            financial = FinancialDashboardSummary(
                _decimal(k["total_revenue"]), _decimal(k["total_expense"]),
                _decimal(k["total_revenue"]) - _decimal(k["total_expense"]),
                _decimal(k["applications"]), _decimal(k["redemptions"]),
                _decimal(k["bank_balance"]) - _decimal(k["opening_balance"]),
                _decimal(k["applied_balance"]),
            )
            budget = BudgetDashboardSummary(
                _decimal(b["budgeted_revenue"]), _decimal(b["actual_revenue"]),
                _decimal(b["budgeted_expense"]), _decimal(b["actual_expense"]),
                _decimal(b["result"]) - _decimal(b["variance"]),
                _decimal(b["result"]),
            )
        if "boe" in self.areas:
            data = self.api.get(f"/api/v1/dashboard/boe?year={year}&month={month}")
            boe = BOEDashboardSummary(bool(data["entities"]), data["entity_count"],
                                      data["queries"], _decimal(data["total_value"]))
        if "targets" in self.areas:
            data = self.api.get(f"/api/v1/dashboard/targets?year={year}&month={month}&indicator=TODAS")
            def indicator(value):
                return IndicatorDashboardSummary(
                    bool(value["target"] or value["actual"]), _decimal(value["target"]),
                    _decimal(value["actual"]),
                    _decimal(value["achievement_percentage"])
                    if value["achievement_percentage"] is not None else None,
                )
            targets = TargetDashboardSummary(indicator(data["queries"]), indicator(data["registrations"]))
        return DashboardSummary(year, month, financial, boe, budget, targets)


class RemoteReportService:
    def __init__(self, api): self.api = api
    def get_annual_report(self, year):
        d = self.api.get(f"/api/v1/reports/annual?year={year}")
        return AnnualReport(d["year"], tuple(MonthlyReportRow(x["month"], *(_decimal(x[k]) for k in (
            "total_revenue", "total_expense", "operational_result", "applications", "redemptions", "cash_movement", "applied_balance", "boe_value", "budgeted_result"))) for x in d["rows"]))


class RemoteCSVService:
    export_repository = _Repository()
    def __init__(self, api): self.api = api
    def validate_period(self, year):
        d = self.api.get(f"/api/v1/reports/csv-validation?year={year}")
        return CSVValidationResult(d["year"], d["valid"], tuple(d["errors"]), d["entity_count"], d["target_rows"], d["association_rows"])
    def export_all(self, year, destination):
        destination = Path(destination); archive_bytes = self.api.download("/api/v1/reports/csv-export", {"year": year})
        with ZipFile(BytesIO(archive_bytes)) as archive:
            archive.extractall(destination)
            names = archive.namelist()
        files = tuple(destination / name for name in names if name.endswith(".csv"))
        report = next(destination / name for name in names if not name.endswith(".csv"))
        return CSVExportResult(year, destination, files, report, self.validate_period(year))
