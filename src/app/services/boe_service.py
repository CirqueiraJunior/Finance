from pathlib import Path
import unicodedata
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import BOEDuplicateImportError, BOEValidationError
from app.importers.boe_importer import BOEImporter
from app.importers.boe_types import (
    BOEIssueSeverity,
    BOEValidationIssue,
    BOEValidationResult,
)
from app.models.boe_entity_total import BOEEntityTotal
from app.models.boe_import import BOEImport
from app.models.boe_import_issue import BOEImportIssue
from app.models.entity import Entity
from app.repositories.boe_repository import BOERepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.entity_repository import EntityRepository
from app.services.cashflow_service import CashflowService


@dataclass(frozen=True, slots=True)
class BOEEntityDetail:
    code: int
    entity_name: str
    source_name: str
    queries: int
    value: Decimal


@dataclass(frozen=True, slots=True)
class BOEImportDetails:
    boe_import: BOEImport
    entities: tuple[BOEEntityDetail, ...]
    total_entities: int
    total_queries: int
    total_value: Decimal
    inconsistencies: tuple[BOEImportIssue, ...]

    @property
    def entity_totals(self) -> list[BOEEntityTotal]:
        """Compatibility access for infrastructure introduced before Sprint 08."""
        return self.boe_import.entity_totals

    @property
    def issues(self) -> tuple[BOEImportIssue, ...]:
        """Compatibility access for infrastructure introduced before Sprint 08."""
        return self.inconsistencies


class BOEService:
    def __init__(
        self,
        repository: BOERepository,
        entity_repository: EntityRepository,
        importer: BOEImporter,
        cashflow_service: CashflowService | None = None,
    ) -> None:
        if repository.session is not entity_repository.session:
            raise ValueError("Os repositories do BOE devem compartilhar a mesma sessão.")
        self.repository = repository
        self.entity_repository = entity_repository
        self.importer = importer
        self.cashflow_service = cashflow_service or CashflowService(
            CashflowRepository(repository.session)
        )
        if (
            self.cashflow_service.repository.session is not repository.session
        ):
            raise ValueError("BOE e Fluxo de Caixa devem compartilhar a mesma sessão.")

    def validate_file(self, file_path: str | Path) -> BOEValidationResult:
        result = self.importer.parse(file_path)
        if result.hash_arquivo and self.repository.get_import_by_hash(result.hash_arquivo):
            self._add_error(result, "Este arquivo BOE já foi importado.")
        if (
            result.periodo_ano is not None
            and result.periodo_mes is not None
            and self.repository.get_import_by_period(
                result.periodo_ano, result.periodo_mes
            )
        ):
            self._add_error(result, "Já existe um BOE importado para este período.")

        seen_codes: set[int] = set()
        for row in result.linhas:
            if row.codigo_entidade in seen_codes:
                self._add_error(
                    result,
                    "Código de Entidade duplicado no arquivo.",
                    linha=row.linha,
                    codigo=str(row.codigo_entidade),
                )
                continue
            seen_codes.add(row.codigo_entidade)
            entity = self.entity_repository.get_by_code(row.codigo_entidade)
            if entity is None:
                self._add_error(
                    result,
                    "Código de Entidade não encontrado na Base Mestra.",
                    linha=row.linha,
                    codigo=str(row.codigo_entidade),
                )
                continue
            if not self._name_matches(entity, row.nome_entidade):
                result.inconsistencias.append(
                    BOEValidationIssue(
                        mensagem=(
                            "Nome da Entidade no BOE diverge da Base Mestra; "
                            "o vínculo será realizado pelo código."
                        ),
                        severidade=BOEIssueSeverity.WARNING,
                        linha=row.linha,
                        codigo=str(row.codigo_entidade),
                    )
                )
        return result

    def import_file(self, file_path: str | Path) -> BOEImport:
        result = self.validate_file(file_path)
        if not result.aprovado:
            raise BOEValidationError(result)
        if (
            result.hash_arquivo is None
            or result.periodo_ano is None
            or result.periodo_mes is None
        ):
            raise BOEValidationError(result)

        boe_import = BOEImport(
            periodo_ano=result.periodo_ano,
            periodo_mes=result.periodo_mes,
            nome_arquivo=result.nome_arquivo,
            caminho_origem=str(result.caminho_arquivo),
            hash_arquivo=result.hash_arquivo,
            quantidade_entidades=len(result.linhas),
            quantidade_inconsistencias=len(result.inconsistencias),
            valor_total=result.valor_total_calculado,
            status="imported",
        )
        try:
            self.repository.add_import(boe_import)
            for row in result.linhas:
                entity = self.entity_repository.get_by_code(row.codigo_entidade)
                if entity is None:
                    raise BOEValidationError(result)
                self.repository.add_entity_total(
                    BOEEntityTotal(
                        boe_import_id=boe_import.id,
                        entity_id=entity.id,
                        codigo_entidade_origem=row.codigo_entidade,
                        nome_entidade_origem=row.nome_entidade,
                        quantidade_consultas=row.quantidade_consultas,
                        valor_total=row.valor_total,
                    )
                )
            for issue in result.inconsistencias:
                self.repository.add_issue(
                    BOEImportIssue(
                        boe_import_id=boe_import.id,
                        linha=issue.linha,
                        codigo=issue.codigo,
                        mensagem=issue.mensagem,
                        severidade=issue.severidade.value,
                    )
                )
            self.cashflow_service.create_direct_revenue_from_boe(
                boe_import, commit=False
            )
            self.repository.session.commit()
        except IntegrityError as error:
            self.repository.session.rollback()
            raise BOEDuplicateImportError(
                "O arquivo ou período BOE já foi importado."
            ) from error
        except Exception:
            self.repository.session.rollback()
            raise
        self.repository.session.refresh(boe_import)
        return boe_import

    def list_imports(self) -> list[BOEImport]:
        return self.repository.list_imports()

    def get_import_details(self, import_id: int) -> BOEImportDetails | None:
        boe_import = self.repository.get_import(import_id)
        if boe_import is None:
            return None

        rows = []
        for total in sorted(
            boe_import.entity_totals,
            key=lambda item: item.codigo_entidade_origem,
        ):
            if total.codigo_entidade_origem == 7500:
                continue
            official_name = None
            if total.entity is not None:
                official_name = total.entity.nome_oficial or total.entity.nome
            rows.append(
                BOEEntityDetail(
                    code=total.codigo_entidade_origem,
                    entity_name=official_name or total.nome_entidade_origem,
                    source_name=total.nome_entidade_origem,
                    queries=total.quantidade_consultas,
                    value=total.valor_total,
                )
            )

        entities = tuple(rows)
        return BOEImportDetails(
            boe_import=boe_import,
            entities=entities,
            total_entities=len(entities),
            total_queries=sum(row.queries for row in entities),
            total_value=sum((row.value for row in entities), Decimal("0.0000")),
            inconsistencies=tuple(boe_import.issues),
        )

    def get_period_details(self, year: int, month: int) -> BOEImportDetails | None:
        boe_import = self.repository.get_import_by_period(year, month)
        if boe_import is None:
            return None
        return self.get_import_details(boe_import.id)

    @classmethod
    def _name_matches(cls, entity: Entity, source_name: str) -> bool:
        source = cls._normalize_name(source_name)
        candidates = [entity.nome, entity.nome_oficial]
        candidates.extend(alias.alias for alias in entity.aliases)
        return source in {
            cls._normalize_name(candidate)
            for candidate in candidates
            if candidate
        }

    @staticmethod
    def _normalize_name(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        without_accents = "".join(
            char for char in normalized if not unicodedata.combining(char)
        )
        return " ".join(without_accents.upper().strip().split())

    @staticmethod
    def _add_error(
        result: BOEValidationResult,
        message: str,
        *,
        linha: int | None = None,
        codigo: str | None = None,
    ) -> None:
        result.inconsistencias.append(
            BOEValidationIssue(
                mensagem=message,
                severidade=BOEIssueSeverity.ERROR,
                linha=linha,
                codigo=codigo,
            )
        )
