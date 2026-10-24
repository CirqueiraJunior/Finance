from app.gui.import_comparison_dialog import ImportComparisonDialog
from app.gui.comparison_currency import format_brl


class TargetComparisonDialog(ImportComparisonDialog):
    """Adapter for the existing target validation preview.

    This adapter never infers record changes or previous values.
    """

    COLUMNS = (
        "Linha",
        "Entidade",
        "Indicador",
        "Meta",
        "Realizado",
        "Origem",
    )

    def __init__(self, validation, *, can_authorize=False, parent=None):
        metadata = validation.get("metadata") or {}
        preview = validation.get("preview") or []
        association = validation.get("association_preview") or []
        errors = validation.get("errors") or []
        warnings = validation.get("warnings") or []

        detected = str(metadata.get("detected_type") or "")
        is_association = "ASSOC" in detected.upper()

        data = association if is_association else preview
        data = [row for row in data if isinstance(row, dict)]

        def field(row, *keys):
            for key in keys:
                value = row.get(key)
                if value is not None and value != "":
                    return str(value)
            return "-"

        columns = (
            (
                "Linha", "Entidade", "Associa\u00e7\u00e3o",
                "Valor", "Quantidade", "Origem",
            )
            if is_association else self.COLUMNS
        )

        rows = []
        for row in data:
            if is_association:
                cells = (
                    field(row, "line"),
                    field(row, "entity_name", "entity_code"),
                    field(row, "association_name", "association_code"),
                    format_brl(field(row, "value", "amount")),
                    field(row, "quantity", "consultations"),
                    field(row, "source_label", "sheet"),
                )
            else:
                cells = (
                    field(row, "line"),
                    field(row, "entity_name", "entity_code"),
                    field(row, "indicator"),
                    field(row, "target", "target_value"),
                    field(row, "actual", "actual_value"),
                    field(row, "source_label", "sheet"),
                )
            rows.append(cells)

        totals = validation.get("totals") or {}
        count = totals.get("rows")
        if count is None:
            count = len(data)

        allowed = bool(
            can_authorize
            and validation.get("can_import")
            and rows
            and not errors
        )

        super().__init__(
            title="Comparar Metas - Pr\u00e9via da importa\u00e7\u00e3o",
            indicators=[
                ("Registros", count),
                ("Avisos", len(warnings)),
                ("Erros", len(errors)),
            ],
            columns=columns,
            rows=rows,
            can_authorize=allowed,
            explanation=(
                "Pr\u00e9via de registros da planilha. "
                "A valida\u00e7\u00e3o atual n\u00e3o fornece "
                "valores anteriores por registro; "
                "nenhuma diferen\u00e7a foi presumida."
            ),
            empty_message=(
                "Nenhum registro dispon\u00edvel na pr\u00e9via. "
                "A importa\u00e7\u00e3o n\u00e3o pode ser autorizada."
            ),
            parent=parent,
        )

        self.preview_count = len(rows)
        self.setObjectName("targetComparisonDialog")
        self.setWindowTitle(
            "Comparar Metas - Finance x Nova Planilha"
        )
