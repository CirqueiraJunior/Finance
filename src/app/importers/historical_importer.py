from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
import re

from openpyxl import load_workbook

from app.importers.historical_parser import (
    BudgetImportData, HistoricalParseResult, HistoricalWorkbookParser,
    TargetImportData, decimal_value, normalized,
)


MONTHS = {
    "JAN": 1, "JANEIRO": 1, "FEV": 2, "FEVEREIRO": 2,
    "MAR": 3, "MARCO": 3, "ABR": 4, "ABRIL": 4,
    "MAI": 5, "MAIO": 5, "JUN": 6, "JUNHO": 6,
    "JUL": 7, "JULHO": 7, "AGO": 8, "AGOSTO": 8,
    "SET": 9, "SETEMBRO": 9, "OUT": 10, "OUTUBRO": 10,
    "NOV": 11, "NOVEMBRO": 11, "DEZ": 12, "DEZEMBRO": 12,
}


@dataclass(slots=True)
class HistoricalPreview:
    file_path: Path
    detected_type: str
    year: int | None
    rows: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duplicates: int = 0
    total: Decimal = Decimal("0.0000")

    @property
    def valid_rows(self) -> int:
        return sum(
            not row.get("duplicate") and not row.get("skip") for row in self.rows
        )

    @property
    def can_import(self) -> bool:
        return bool(self.rows) and not self.errors


class HistoricalWorkbookImporter:
    """Leitor conservador. Nunca persiste dados e nunca altera a planilha."""

    def __init__(self, parser: HistoricalWorkbookParser | None = None) -> None:
        self.parser = parser or HistoricalWorkbookParser()

    def parse(self, file_path: str | Path) -> HistoricalPreview:
        path = Path(file_path)
        if path.suffix.lower() not in {".xlsx", ".xlsm"} or not path.is_file():
            return HistoricalPreview(path, "DESCONHECIDO", None,
                                     errors=["Arquivo Excel inválido ou inexistente."])
        operational = self.parser.parse(path)
        if operational.metadata.detected_type != "DESCONHECIDO":
            return self._operational_preview(operational)
        workbook = load_workbook(path, read_only=True, data_only=True)
        names = {normalized(name): name for name in workbook.sheetnames}
        if "LANCAMENTOS" in names:
            return self._cashflow(path, workbook[names["LANCAMENTOS"]])
        if "TAXA BOE" in names:
            return HistoricalPreview(path, "BOE", None)
        return HistoricalPreview(path, "DESCONHECIDO", None,
                                 errors=["Estrutura oficial não reconhecida."])

    def parse_association(self, file_path: str | Path) -> HistoricalPreview:
        path = Path(file_path)
        workbook = load_workbook(path, read_only=True, data_only=True)
        sheet_name = next((name for name in workbook.sheetnames
                           if normalized(name) == "ASSOCIACOES"), None)
        if sheet_name is None:
            return HistoricalPreview(path, "ASSOCIACAO", None,
                                     errors=["A aba Associações não foi encontrada."])
        sheet = workbook[sheet_name]
        preview = HistoricalPreview(path, "ASSOCIACAO", self._year_from_name(path) or 2026)
        rows = sheet.iter_rows(values_only=True)
        next(rows, None)
        next(rows, None)
        for line, values in enumerate(rows, start=3):
            code = values[0] if values else None
            if not isinstance(code, (int, float)) or int(code) < 7501:
                continue
            if int(code) == 7500:
                continue
            for month in range(1, 13):
                base = 2 + (month - 1) * 4
                cancellation = values[base] if len(values) > base else None
                capture = values[base + 1] if len(values) > base + 1 else None
                execution = values[base + 3] if len(values) > base + 3 else None
                if cancellation is None and capture is None and execution is None:
                    continue
                try:
                    preview.rows.append({"line": line, "code": int(code),
                                         "year": preview.year, "month": month,
                                         "cancellation": decimal_value(cancellation or 0),
                                         "capture": decimal_value(capture or 0),
                                         "execution": decimal_value(execution or 0)})
                except ValueError as error:
                    preview.errors.append(f"Linha {line}, mês {month}: {error}")
        if not preview.rows:
            preview.errors.append("Nenhum dado mensal de Associação foi encontrado.")
        return preview

    def _cashflow(self, path: Path, sheet) -> HistoricalPreview:
        preview = HistoricalPreview(path, "FLUXO_CAIXA", None)
        for line, values in enumerate(sheet.iter_rows(min_row=3, values_only=True), start=3):
            if not any(value is not None for value in values[:8]):
                continue
            year, month_name, description, notes, category, kind, value, boe = values[:8]
            if description is None and "SALDO" in normalized(notes):
                preview.warnings.append(f"Linha {line}: saldo técnico não importado como lançamento.")
                continue
            try:
                year = int(year)
                month = MONTHS[normalized(month_name)]
                amount = decimal_value(value)
                if amount <= 0:
                    raise ValueError("O valor deve ser maior que zero.")
                if not str(description or "").strip():
                    raise ValueError("Descrição obrigatória.")
                if normalized(boe) not in {"SIM", "NAO"}:
                    raise ValueError("BOE deve ser Sim ou Não.")
                row = {"line": line, "year": year, "month": month,
                       "description": str(description).strip(),
                       "notes": str(notes).strip() if notes is not None else None,
                       "category_label": str(category or "").strip(),
                       "type_label": str(kind or "").strip(), "value": amount,
                       "boe": normalized(boe) == "SIM"}
                preview.rows.append(row)
                preview.total += amount
                preview.year = year if preview.year is None else preview.year
            except (KeyError, TypeError, ValueError) as error:
                preview.errors.append(f"Linha {line}: {error}")
        return preview

    @staticmethod
    def _operational_preview(result: HistoricalParseResult) -> HistoricalPreview:
        rows = []
        for item in result.data:
            if isinstance(item, TargetImportData):
                rows.append({
                    "line": item.line, "code": item.code, "year": item.year,
                    "month": item.month, "indicator": item.indicator,
                    "target": item.target, "actual": item.actual,
                })
            elif isinstance(item, BudgetImportData):
                rows.append({
                    "line": item.line, "year": item.year, "month": item.month,
                    "type": item.entry_type, "category": item.category,
                    "value": item.value, "source_label": item.source_label,
                })
        return HistoricalPreview(
            result.metadata.file_path, result.metadata.detected_type,
            result.metadata.year, rows, list(result.warnings), list(result.errors),
            total=result.total,
        )

    @staticmethod
    def _year_from_name(path: Path) -> int | None:
        match = re.search(r"\b(20\d{2})\b", path.name)
        return int(match.group(1)) if match else None
