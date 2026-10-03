"""Parsing puro dos arquivos operacionais históricos de Metas e Orçamento."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import unicodedata

from openpyxl import load_workbook


def normalized(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join(
        "".join(char for char in text if not unicodedata.combining(char))
        .upper().strip().split()
    )


def semantic(value: object) -> str:
    """Normaliza rótulos de layout sem tornar valores de negócio permissivos."""
    return re.sub(r"[^A-Z0-9]+", "", normalized(value))


def decimal_value(value: object) -> Decimal:
    if isinstance(value, float):
        value = str(value)
    try:
        result = Decimal(value).quantize(Decimal("0.0001"))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("Valor numérico inválido.") from error
    if not result.is_finite() or result < 0:
        raise ValueError("Valor numérico inválido.")
    return result


@dataclass(frozen=True, slots=True)
class HistoricalParseMetadata:
    file_path: Path
    detected_type: str
    year: int | None
    sheets: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TargetImportData:
    line: int
    code: int
    year: int
    month: int
    indicator: str
    target: Decimal
    actual: Decimal
    entity_name: str | None = None


@dataclass(frozen=True, slots=True)
class AssociationImportData:
    line: int
    code: int
    year: int
    month: int
    cancellation: Decimal
    capture: Decimal
    execution: Decimal
    entity_name: str | None = None


@dataclass(frozen=True, slots=True)
class BudgetImportData:
    line: int
    year: int
    month: int
    entry_type: str
    category: str
    value: Decimal
    source_label: str


@dataclass(frozen=True, slots=True)
class HistoricalParseResult:
    metadata: HistoricalParseMetadata
    data: tuple[
        TargetImportData | AssociationImportData | BudgetImportData, ...
    ] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    total: Decimal = Decimal("0.0000")

    @property
    def can_import(self) -> bool:
        return bool(self.data) and not self.errors


class HistoricalWorkbookParser:
    """Lê e valida workbooks sem conhecer banco, repositório ou persistência."""

    BUDGET_MAPPINGS = {
        "REPASSE CDLS ESTADO GOIAS": ("RECEITA", "RECEITA_DIRETA"),
        "DESPESAS COM PESSOAL": ("DESPESA", "PESSOAL"),
        "DESPESAS COM EVENTOS": ("DESPESA", "EVENTOS"),
        "DESPESAS COM A OPERACAO": ("DESPESA", "OPERACIONAL"),
    }
    TARGET_MONTH_HEADERS = (
        "JAN", "FEV", "MAR", "ABR", "MAI", "JUN",
        "JUL", "AGO", "SET", "OUT", "NOV", "DEZ",
    )
    MONTH_ALIASES = {
        "JAN": 1, "JANEIRO": 1, "FEV": 2, "FEVEREIRO": 2,
        "MAR": 3, "MARCO": 3, "ABR": 4, "ABRIL": 4,
        "MAI": 5, "MAIO": 5, "JUN": 6, "JUNHO": 6,
        "JUL": 7, "JULHO": 7, "AGO": 8, "AGOSTO": 8,
        "SET": 9, "SETEMBRO": 9, "OUT": 10, "OUTUBRO": 10,
        "NOV": 11, "NOVEMBRO": 11, "DEZ": 12, "DEZEMBRO": 12,
    }

    def parse(self, file_path: str | Path) -> HistoricalParseResult:
        path = Path(file_path)
        if path.suffix.lower() not in {".xlsx", ".xlsm"} or not path.is_file():
            return self._unknown(path, (), "Arquivo Excel inválido ou inexistente.")
        workbook = load_workbook(path, read_only=True, data_only=True)
        try:
            names = {normalized(name): name for name in workbook.sheetnames}
            sheets = tuple(workbook.sheetnames)
            structural = self._structural_target_sheet(workbook)
            if structural is not None:
                sheet, header_line, columns = structural
                return self._structural_targets(
                    path, sheets, sheet, header_line, columns
                )
            target_name, target_error = self._section_sheet(
                workbook, {"METADECONSULTAS", "METADEREGISTROS"},
                preferred=("META",),
            )
            actual_name, actual_error = self._section_sheet(
                workbook,
                {"CONSULTASREALIZADAS", "REGISTROSREALIZADOS"},
                preferred=("FATURAMENTO", "DESEMPENHO"),
            )
            structurally_identified = target_name is not None and actual_name is not None
            # Compatibilidade com arquivos 2026 antigos que não trazem os
            # marcadores das duas seções, mas usam nomes oficiais inequívocos.
            target_name = target_name or self._sheet_name(names, "META")
            actual_name = actual_name or self._sheet_name(names, "FATURAMENTO")
            if target_name is not None and actual_name is not None:
                year, year_error = self._workbook_year(path, workbook)
                if year_error:
                    return self._unknown(path, sheets, year_error)
                association_name, association_layout, association_error = (
                    self._association_sheet(workbook)
                )
                if association_error:
                    return self._unknown(path, sheets, association_error)
                if (association_name is None and not structurally_identified
                        and "ASSOCIACOES" in names):
                    association_name = names["ASSOCIACOES"]
                return self._targets(
                    path, sheets, workbook[target_name], workbook[actual_name],
                    year=year,
                    association_sheet=(
                        workbook[association_name] if association_name else None
                    ),
                    association_layout=association_layout,
                )
            if target_error or actual_error:
                return self._unknown(path, sheets, target_error or actual_error)
            if "PLANEJ. ORCAMENTARIO" in names:
                return self._budget(path, sheets, workbook[names["PLANEJ. ORCAMENTARIO"]])
            return self._unknown(path, sheets, "Estrutura operacional não reconhecida.")
        finally:
            workbook.close()

    def _structural_target_sheet(self, workbook):
        required = {
            "COD.", "ENTIDADE", "VERTENTE", "TOTAL ANUAL",
            *self.TARGET_MONTH_HEADERS,
        }
        matches = []
        for sheet in workbook.worksheets:
            for line, values in enumerate(
                sheet.iter_rows(min_row=1, max_row=25, values_only=True), start=1
            ):
                columns = {
                    normalized(value): index
                    for index, value in enumerate(values)
                    if value is not None
                }
                if required.issubset(columns):
                    matches.append((sheet, line, columns))
                    break
        return matches[0] if len(matches) == 1 else None

    def _structural_targets(
        self, path: Path, sheets: tuple[str, ...], sheet,
        header_line: int, columns: dict[str, int],
    ) -> HistoricalParseResult:
        year = self._year_from_name(path) or self._year_from_name(Path(sheet.title))
        if year is None:
            return self._unknown(
                path, sheets, "Ano das Metas não identificado no arquivo ou na aba."
            )
        data: list[TargetImportData] = []
        warnings: list[str] = []
        errors: list[str] = []
        ignored_vertentes: set[str] = set()
        for line, values in enumerate(
            sheet.iter_rows(min_row=header_line + 1, values_only=True),
            start=header_line + 1,
        ):
            code = self._entity_code(values[columns["COD."]] if len(values) > columns["COD."] else None)
            if code is None:
                continue
            entity_name = values[columns["ENTIDADE"]] if len(values) > columns["ENTIDADE"] else None
            source_indicator = normalized(
                values[columns["VERTENTE"]] if len(values) > columns["VERTENTE"] else None
            )
            indicator = {
                "CONSULTAS": "CONSULTAS",
                "REGISTRO": "REGISTROS",
                "REGISTROS": "REGISTROS",
            }.get(source_indicator)

            if indicator is None:
                if source_indicator:
                    ignored_vertentes.add(source_indicator)
                continue
            if not isinstance(entity_name, str) or not entity_name.strip():
                errors.append(f"Linha {line}: nome da Entidade ausente.")
                continue
            for month, header in enumerate(self.TARGET_MONTH_HEADERS, start=1):
                index = columns[header]
                value = values[index] if len(values) > index else None
                if value is None:
                    continue
                try:
                    target = decimal_value(value)
                except ValueError as error:
                    errors.append(f"Linha {line}, mês {month}: {error}")
                    continue
                data.append(TargetImportData(
                    line=line, code=code, year=year, month=month,
                    indicator=indicator, target=target,
                    actual=Decimal("0.0000"),
                    entity_name=entity_name.strip(),
                ))
        if ignored_vertentes:
            warnings.append(
                "Vertentes ainda não suportadas foram ignoradas: "
                + ", ".join(sorted(ignored_vertentes)) + "."
            )
        return HistoricalParseResult(
            HistoricalParseMetadata(path, "META_REALIZADO", year, sheets),
            tuple(data), tuple(warnings), tuple(errors),
        )

    def _targets(self, path: Path, sheets: tuple[str, ...], target_sheet,
                 actual_sheet, *, year: int, association_sheet=None,
                 association_layout=None) -> HistoricalParseResult:
        actual_by_key: dict[tuple[str, int, int], object] = {}
        actual_rows, actual_indicators = self._indicator_rows(actual_sheet, {
            "CONSULTAS REALIZADAS": "CONSULTAS",
            "REGISTROS REALIZADOS": "REGISTROS",
        })
        for indicator, _line, code, _entity_name, monthly in actual_rows:
            for month, value in monthly.items():
                actual_by_key[(indicator, code, month)] = value

        data: list[TargetImportData | AssociationImportData] = []
        errors: list[str] = []
        target_rows, target_indicators = self._indicator_rows(target_sheet, {
            "META DE CONSULTAS": "CONSULTAS",
            "META DE REGISTROS": "REGISTROS",
        })
        for indicator, line, code, entity_name, monthly in target_rows:
            for month, target in monthly.items():
                actual = actual_by_key.get((indicator, code, month))
                if target is None and actual is None:
                    continue
                try:
                    data.append(TargetImportData(
                        line, code, year, month, indicator,
                        decimal_value(target or 0), decimal_value(actual or 0),
                        str(entity_name).strip(),
                    ))
                except ValueError as error:
                    errors.append(f"Linha {line}, mês {month}: {error}")

        warnings = []
        if "REGISTROS" not in target_indicators or "REGISTROS" not in actual_indicators:
            warnings.append(
                "A estrutura analisada contém CONSULTAS. REGISTROS só serão importados quando houver aba oficial inequívoca."
            )
        if association_sheet is not None:
            association_data, association_errors = self._associations(
                association_sheet, year, association_layout
            )
            data.extend(association_data)
            errors.extend(association_errors)
        metadata = HistoricalParseMetadata(path, "META_REALIZADO", year, sheets)
        return HistoricalParseResult(metadata, tuple(data), tuple(warnings), tuple(errors))

    @staticmethod
    def _associations(sheet, year: int, layout=None) -> tuple[
        list[AssociationImportData], list[str]
    ]:
        data: list[AssociationImportData] = []
        errors: list[str] = []
        rows = sheet.iter_rows(
            min_row=(layout[0] if layout else 3), values_only=True
        )
        month_columns = layout[1] if layout else {
            month: (2 + (month - 1) * 4, 3 + (month - 1) * 4,
                    5 + (month - 1) * 4)
            for month in range(1, 13)
        }
        for line, values in enumerate(rows, start=(layout[0] if layout else 3)):
            raw_code = values[0] if values else None
            try:
                numeric_code = Decimal(str(raw_code).strip())
            except (InvalidOperation, AttributeError, ValueError):
                continue
            if (
                not numeric_code.is_finite()
                or numeric_code != numeric_code.to_integral_value()
                or int(numeric_code) < 7501
            ):
                continue
            code = int(numeric_code)
            entity_name = values[1] if len(values) > 1 else None
            for month, (cancel_index, capture_index, execution_index) in month_columns.items():
                cancellation = values[cancel_index] if len(values) > cancel_index else None
                capture = values[capture_index] if len(values) > capture_index else None
                execution = values[execution_index] if len(values) > execution_index else None
                if cancellation is None and capture is None and execution is None:
                    continue
                try:
                    data.append(AssociationImportData(
                        line=line,
                        code=code,
                        year=year,
                        month=month,
                        cancellation=decimal_value(cancellation or 0),
                        capture=decimal_value(capture or 0),
                        execution=decimal_value(execution or 0),
                        entity_name=(
                            entity_name.strip()
                            if isinstance(entity_name, str) else None
                        ),
                    ))
                except ValueError as error:
                    errors.append(f"Linha {line}, mês {month}: {error}")
        return data, errors

    def _indicator_rows(self, sheet, labels: dict[str, str]):
        physical_rows = list(enumerate(
            sheet.iter_rows(min_row=1, values_only=True), start=1
        ))
        semantic_labels = {semantic(label): value for label, value in labels.items()}
        has_sections = any(
            semantic(values[0] if values else None) in semantic_labels
            for _, values in physical_rows
        )
        active_indicator = None if has_sections else "CONSULTAS"
        columns = None
        indicators: set[str] = set()
        rows = []
        for line, values in physical_rows:
            first = values[0] if values else None
            section = semantic_labels.get(semantic(first))
            if section is not None:
                active_indicator = section
                indicators.add(section)
                columns = None
                continue
            header_columns = self._target_header_columns(values)
            if header_columns is not None:
                columns = header_columns
                continue
            effective = columns or {
                "code": 0, "entity": 1,
                "months": {month: month + 1 for month in range(1, 13)},
            }
            code_index = effective["code"]
            code = self._entity_code(
                values[code_index] if len(values) > code_index else None
            )
            entity_index = effective["entity"]
            entity_name = values[entity_index] if len(values) > entity_index else None
            if (active_indicator is None or code is None
                    or not isinstance(entity_name, str) or not entity_name.strip()):
                continue
            indicators.add(active_indicator)
            monthly = {
                month: values[index] if len(values) > index else None
                for month, index in effective["months"].items()
            }
            rows.append((active_indicator, line, code, entity_name, monthly))
        return rows, indicators

    def _target_header_columns(self, values):
        tokens = {semantic(value): index for index, value in enumerate(values) if value is not None}
        code = next((tokens[item] for item in ("COD", "CODIGO") if item in tokens), None)
        entity = next((tokens[item] for item in ("ENTIDADE", "ENTIDADES") if item in tokens), None)
        months = {
            month: index for token, index in tokens.items()
            if (month := self.MONTH_ALIASES.get(token)) is not None
        }
        if code is None or entity is None or not months:
            return None
        return {"code": code, "entity": entity, "months": months}

    @staticmethod
    def _section_sheet(workbook, required: set[str], *, preferred: tuple[str, ...]):
        matches = []
        for sheet in workbook.worksheets:
            found = {
                semantic(values[0] if values else None)
                for values in sheet.iter_rows(min_row=1, max_row=250, values_only=True)
            }
            if required.issubset(found):
                matches.append(sheet.title)
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            preferred_matches = [
                name for wanted in preferred for name in matches
                if semantic(name) == semantic(wanted)
            ]
            if len(preferred_matches) == 1:
                return preferred_matches[0], None
            return None, "Estrutura ambígua entre as abas: " + ", ".join(matches) + "."
        return None, None

    def _association_sheet(self, workbook):
        matches = []
        for sheet in workbook.worksheets:
            rows = list(sheet.iter_rows(min_row=1, max_row=10, values_only=True))
            for month_row_index in range(len(rows) - 1):
                month_row = rows[month_row_index]
                subheaders = rows[month_row_index + 1]
                month_columns = {}
                for index, value in enumerate(month_row):
                    month = self.MONTH_ALIASES.get(semantic(value))
                    if month is None:
                        continue
                    group = {
                        semantic(subheaders[column]): column
                        for column in range(index, min(index + 4, len(subheaders)))
                        if subheaders[column] is not None
                    }
                    required = {"CANC", "CAPTACAO", "SUSPENSO", "TOTALASSC"}
                    if required.issubset(group):
                        month_columns[month] = (
                            group["CANC"], group["CAPTACAO"], group["TOTALASSC"]
                        )
                if set(month_columns) == set(range(1, 13)):
                    matches.append((sheet.title, (month_row_index + 3, month_columns)))
                    break
        if len(matches) == 1:
            name, layout = matches[0]
            return name, layout, None
        if len(matches) > 1:
            return None, None, (
                "Mais de uma aba corresponde ao layout de associações: "
                + ", ".join(name for name, _ in matches) + "."
            )
        return None, None, None

    def _workbook_year(self, path: Path, workbook):
        evidence: list[tuple[str, int]] = []
        file_year = self._year_from_name(path)
        if file_year is not None:
            evidence.append(("nome do arquivo", file_year))
        for sheet in workbook.worksheets:
            for values in sheet.iter_rows(min_row=1, max_row=25, max_col=20, values_only=True):
                for value in values:
                    match = re.search(r"META\s*X\s*REALIZADO\s*(20\d{2})", normalized(value))
                    if match:
                        evidence.append((f"conteúdo da aba {sheet.title}", int(match.group(1))))
        parent_years = {
            int(match.group(1))
            for parent in list(path.parents)[:5]
            if (match := re.search(r"\b(20\d{2})\b", parent.name))
        }
        evidence.extend(("diretório pai", year) for year in sorted(parent_years))
        years = {year for _, year in evidence}
        if len(years) > 1:
            details = ", ".join(f"{source}={year}" for source, year in evidence)
            return None, f"Anos conflitantes identificados: {details}."
        if not years:
            return None, "Ano das Metas não identificado no nome, conteúdo ou diretório do arquivo."
        return years.pop(), None

    def _budget(self, path: Path, sheets: tuple[str, ...], sheet) -> HistoricalParseResult:
        year = self._year_from_name(path)
        if year is None:
            return self._unknown(
                path, sheets,
                "Ano do Orçamento não identificado no nome do arquivo."
            )
        data: list[BudgetImportData] = []
        warnings: list[str] = []
        errors: list[str] = []
        total = Decimal("0.0000")
        ignored = 0
        for line, values in enumerate(sheet.iter_rows(min_row=9, values_only=True), start=9):
            label = normalized(values[1] if len(values) > 1 else None)
            mapping = self.BUDGET_MAPPINGS.get(label)
            if mapping is None:
                if label and any(
                    values[index] for index in range(2, min(len(values), 26), 2)
                ):
                    ignored += 1
                continue
            for month in range(1, 13):
                index = 2 + (month - 1) * 2
                value = values[index] if len(values) > index else None
                if value is None:
                    continue
                try:
                    amount = decimal_value(value)
                except ValueError as error:
                    errors.append(f"Linha {line}, mês {month}: {error}")
                    continue
                data.append(BudgetImportData(
                    line, year, month, mapping[0], mapping[1], amount,
                    str(values[1] or "").strip(),
                ))
                total += amount
        if ignored:
            warnings.append(
                f"{ignored} linhas detalhadas sem correspondência inequívoca foram excluídas do preview."
            )
        metadata = HistoricalParseMetadata(path, "ORCAMENTO", year, sheets)
        return HistoricalParseResult(
            metadata, tuple(data), tuple(warnings), tuple(errors), total
        )

    @staticmethod
    def _entity_code(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        try:
            numeric = Decimal(str(value).strip())
        except (InvalidOperation, AttributeError, ValueError):
            return None
        if not numeric.is_finite() or numeric != numeric.to_integral_value():
            return None
        code = int(numeric)
        return code if code > 0 and code not in {7500, 7600} else None

    @staticmethod
    def _sheet_name(names: dict[str, str], expected: str) -> str | None:
        """Accept official regional/year suffixes without guessing by content."""
        exact = names.get(expected)
        if exact is not None:
            return exact
        matches = [
            original for normalized_name, original in names.items()
            if re.fullmatch(rf"{re.escape(expected)}(?:\s*[-_]\s*|\s+).+", normalized_name)
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _year_from_name(path: Path) -> int | None:
        match = re.search(r"\b(20\d{2})\b", path.name)
        return int(match.group(1)) if match else None

    @staticmethod
    def _unknown(path: Path, sheets: tuple[str, ...], error: str) -> HistoricalParseResult:
        return HistoricalParseResult(
            HistoricalParseMetadata(path, "DESCONHECIDO", None, sheets), errors=(error,)
        )
