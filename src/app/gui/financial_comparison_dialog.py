from app.gui.import_comparison_dialog import ImportComparisonDialog
from app.gui.comparison_currency import format_brl


class FinancialComparisonDialog(ImportComparisonDialog):
    """Read-only adapter for Financeiro import validation."""

    COLUMNS = (
        "Linha",
        "Período",
        "Tipo",
        "Descrição",
        "Categoria",
        "Valor",
        "Situação",
    )

    def __init__(self, validation, *, can_authorize=False, parent=None):
        validation = validation or {}
        preview = validation.get("preview") or []
        errors = validation.get("errors") or []
        warnings = validation.get("warnings") or []

        def show(value):
            return "-" if value is None or value == "" else str(value)

        def period(row):
            year = row.get("year")
            month = row.get("month")
            if year is None or month is None:
                return "-"
            try:
                return f"{int(month):02d}/{int(year)}"
            except (TypeError, ValueError):
                return f"{month}/{year}"

        eligible = []
        duplicates = 0
        skipped = 0

        for entry in preview:
            if not isinstance(entry, dict):
                continue
            if entry.get("duplicate"):
                duplicates += 1
                continue
            if entry.get("skip"):
                skipped += 1
                continue

            eligible.append((
                show(entry.get("line")),
                period(entry),
                show(entry.get("type_label") or entry.get("type")),
                show(
                    entry.get("description")
                    or entry.get("descricao")
                    or entry.get("source_label")
                ),
                show(
                    entry.get("category_label")
                    or entry.get("category")
                ),
                format_brl(entry.get("value") if entry.get("value") is not None else entry.get("amount")),
                "Elegível",
            ))

        allowed = bool(
            can_authorize
            and validation.get("can_import")
            and not errors
            and eligible
        )

        super().__init__(
            title="Comparar Financeiro - Prévia da importação",
            indicators=[
                ("Elegíveis", len(eligible)),
                ("Duplicados", duplicates),
                ("Ignorados", skipped),
            ],
            columns=self.COLUMNS,
            rows=eligible,
            can_authorize=allowed,
            explanation=(
                "Exibidos somente lançamentos elegíveis para importação. "
                "Duplicados e ignorados não serão autorizados por "
                "esta prévia. Os registros não foram classificados "
                "como alterações de valores existentes."
            ),
            empty_message=(
                "Nenhum lançamento elegível para importação. "
                "A autorização está bloqueada."
            ),
            parent=parent,
        )

        self.eligible_count = len(eligible)
        self.duplicate_count = duplicates
        self.skipped_count = skipped
        self.setObjectName("financialComparisonDialog")
