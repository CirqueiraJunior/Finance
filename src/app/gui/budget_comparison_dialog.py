from PySide6.QtWidgets import QLabel

from app.gui.import_comparison_dialog import ImportComparisonDialog
from app.gui.comparison_currency import format_brl


class BudgetComparisonDialog(ImportComparisonDialog):
    """Adapt the budget validation contract to the shared comparison UI."""

    COLUMNS = (
        "Situa\u00e7\u00e3o",
        "Per\u00edodo",
        "Tipo",
        "Categoria",
        "Descri\u00e7\u00e3o",
        "Atual no Finance",
        "Nova planilha",
        "Diferen\u00e7a",
    )

    def __init__(self, validation: dict, *, can_authorize=False, parent=None):
        totals = validation.get("comparison_totals") or {}
        comparison = validation.get("comparison_preview") or []
        preview = validation.get("preview") or []

        actionable = [
            row for row in comparison
            if isinstance(row, dict)
            and row.get("status") in ("NEW", "CHANGED")
        ]

        rows = []
        for entry in actionable:
            description = str(entry.get("source_label") or "")

            if not description:
                for candidate in preview:
                    if not isinstance(candidate, dict):
                        continue
                    if all(
                        candidate.get(field) == entry.get(field)
                        for field in (
                            "line", "year", "month",
                            "entry_type", "category",
                        )
                    ):
                        description = str(
                            candidate.get("source_label") or ""
                        )
                        break

            month = entry.get("month")
            year = entry.get("year")

            try:
                period = f"{int(month):02d}/{year}"
            except (TypeError, ValueError):
                period = f"{month}/{year}"

            def display(value):
                return format_brl(value)

            rows.append((
                {
                    "NEW": "Novo",
                    "CHANGED": "Alterado",
                }.get(entry.get("status"), str(entry.get("status") or "")),
                period,
                str(entry.get("entry_type") or ""),
                str(entry.get("category") or ""),
                description,
                display(entry.get("previous_value")),
                display(entry.get("value")),
                display(entry.get("difference")),
            ))

        super().__init__(
            title="Compara\u00e7\u00e3o antes da importa\u00e7\u00e3o",
            indicators=[
                ("Novos", totals.get("new", 0)),
                ("Alterados", totals.get("changed", 0)),
                ("Sem altera\u00e7\u00e3o", totals.get("unchanged", 0)),
            ],
            columns=self.COLUMNS,
            rows=rows,
            can_authorize=can_authorize,
            empty_message=(
                "Nenhuma altera\u00e7\u00e3o identificada. "
                "Os registros da planilha j\u00e1 correspondem "
                "aos dados existentes no Finance. "
                "Nenhuma atualiza\u00e7\u00e3o \u00e9 necess\u00e1ria."
            ),
            explanation=(
                "Somente registros novos ou alterados aparecem abaixo. "
                "Confira os valores antes de autorizar."
            ),
            parent=parent,
        )

        self.actionable_count = len(actionable)
        self.setObjectName("budgetComparisonDetailDialog")
        self.setWindowTitle(
            "Comparar Or\u00e7amento - Finance x Nova Planilha"
        )

        # Preserve the names exposed by the original budget dialog.
        self.count_labels = dict(zip(
            ("new", "changed", "unchanged"),
            self.count_labels,
        ))

        if self.table is not None:
            self.table.setObjectName("budgetComparisonDetailTable")
        else:
            notice = self.findChild(
                QLabel, "importComparisonEmptyNotice"
            )
            if notice is not None:
                notice.setObjectName("budgetNoChangesNotice")
