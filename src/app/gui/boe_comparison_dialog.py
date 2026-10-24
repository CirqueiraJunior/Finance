"""Adaptador visual BOE para a comparacao compartilhada.

Somente leitura. Regras de persistencia permanecem no BOEService.
"""

from app.gui.import_comparison_dialog import ImportComparisonDialog


class BOEComparisonDialog(ImportComparisonDialog):
    """Mostra competencia, entidades e inconsistencias da BOE."""

    def __init__(
        self,
        result,
        *,
        can_authorize=True,
        parent=None,
    ):
        approved = bool(getattr(result, "aprovado", False))
        year = getattr(result, "periodo_ano", None)
        month = getattr(result, "periodo_mes", None)

        if year is not None and month is not None:
            period = f"{int(month):02d}/{int(year)}"
        else:
            period = "Não identificada"

        entities = tuple(getattr(result, "linhas", ()) or ())
        issues = tuple(
            getattr(result, "inconsistencias", ()) or ()
        )

        error_count = int(
            getattr(result, "quantidade_erros", 0) or 0
        )
        warning_count = int(
            getattr(result, "quantidade_avisos", 0) or 0
        )

        rows = [
            (
                "Resumo",
                "—",
                "—",
                f"Competência: {period} | "
                f"Entidades: {len(entities)} | "
                f"Validação: {'APROVADA' if approved else 'REPROVADA'}",
            ),
        ]

        def issue_key(issue):
            severity = getattr(issue, "severidade", None)
            value = str(getattr(severity, "value", severity))
            return 0 if value == "ERROR" else 1

        for issue in sorted(issues, key=issue_key):
            severity = getattr(issue, "severidade", None)
            severity_value = str(
                getattr(severity, "value", severity)
            )
            rows.append((
                "Erro" if severity_value == "ERROR" else "Aviso",
                str(getattr(issue, "linha", None) or "Arquivo"),
                str(getattr(issue, "codigo", None) or "—"),
                str(getattr(issue, "mensagem", "")),
            ))

        name = str(
            getattr(result, "nome_arquivo", "") or "BOE"
        )

        super().__init__(
            title="Comparar BOE — " + name,
            indicators=[
                ("Entidades", len(entities)),
                ("Erros", error_count),
                ("Avisos", warning_count),
            ],
            columns=[
                "Tipo",
                "Linha",
                "Código",
                "Descrição",
            ],
            rows=rows,
            can_authorize=bool(
                can_authorize and approved and not error_count
            ),
            empty_message="Nenhum dado de comparação disponível.",
            explanation=(
                "Prévia somente leitura. A autorização permite "
                "prosseguir para a confirmação final; nenhum dado "
                "é gravado nesta etapa. Competência: " + period
            ),
            parent=parent,
        )
