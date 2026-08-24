from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path


class BOEIssueSeverity(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"


@dataclass(frozen=True, slots=True)
class BOEParsedRow:
    linha: int
    codigo_entidade: int
    nome_entidade: str
    quantidade_consultas: int
    valor_total: Decimal


@dataclass(frozen=True, slots=True)
class BOEValidationIssue:
    mensagem: str
    severidade: BOEIssueSeverity
    linha: int | None = None
    codigo: str | None = None


@dataclass(slots=True)
class BOEValidationResult:
    caminho_arquivo: Path
    nome_arquivo: str
    hash_arquivo: str | None = None
    periodo_ano: int | None = None
    periodo_mes: int | None = None
    linhas: list[BOEParsedRow] = field(default_factory=list)
    inconsistencias: list[BOEValidationIssue] = field(default_factory=list)
    quantidade_consolidada: int | None = None
    valor_consolidado: Decimal | None = None

    @property
    def aprovado(self) -> bool:
        return not any(
            issue.severidade is BOEIssueSeverity.ERROR
            for issue in self.inconsistencias
        )

    @property
    def quantidade_erros(self) -> int:
        return sum(
            issue.severidade is BOEIssueSeverity.ERROR
            for issue in self.inconsistencias
        )

    @property
    def quantidade_avisos(self) -> int:
        return sum(
            issue.severidade is BOEIssueSeverity.WARNING
            for issue in self.inconsistencias
        )

    @property
    def valor_total_calculado(self) -> Decimal:
        return sum((row.valor_total for row in self.linhas), start=Decimal("0"))

