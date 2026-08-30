from dataclasses import dataclass
from datetime import date
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.historical_importer import (
    HistoricalPreview, HistoricalWorkbookImporter, normalized,
)
from app.models.association_entry import AssociationEntry
from app.models.budget_entry import BudgetEntry
from app.models.cashflow_entry import CashflowEntry
from app.models.investment_movement import InvestmentMovement
from app.models.target_entry import TargetEntry
from app.services.backup_service import BackupService
from app.services.boe_service import BOEService
from app.services.cashflow_catalog_service import CashflowCatalogService
from app.services.entity_service import EntityService


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ImportReport:
    processed: int
    imported: int
    ignored: int
    duplicates: int
    warnings: int
    errors: int
    total: str
    backup_path: Path


CATEGORY_MAP = {
    "RECEITA DIRETA": "RECEITA_DIRETA", "RECEITA INDIRETA": "RECEITA_INDIRETA",
    "ADMINISTRATIVO": "ADMINISTRATIVO", "DIRETORIA": "DIRETORIA",
    "EVENTOS": "EVENTOS", "OPERACIONAL": "OPERACIONAL", "PESSOAL": "PESSOAL",
    "INVESTIMENTO": "INVESTIMENTO", "RESGATE": "RESGATE",
    "OUTROS": "OUTROS",
    "SALDO APLICADO": "SALDO_APLICADO",
}
TYPE_MAP = {"RECEITA": "RECEITA", "DESPESA": "DESPESA",
            "APLICACAO": "APLICACAO", "RESGATE": "RESGATE", "SALDO": "SALDO"}


class HistoricalImportService:
    def __init__(self, session: Session, importer: HistoricalWorkbookImporter,
                 entities: EntityService, catalog: CashflowCatalogService,
                 backup: BackupService, boe: BOEService) -> None:
        self.session, self.importer = session, importer
        self.entities, self.catalog = entities, catalog
        self.backup, self.boe = backup, boe

    def analyze(self, file_path: str | Path,
                forced_type: str | None = None) -> HistoricalPreview:
        if forced_type == "ASSOCIACAO":
            preview = self.importer.parse_association(file_path)
        else:
            preview = self.importer.parse(file_path)
        if preview.detected_type == "BOE":
            return self._analyze_boe(file_path)
        if preview.detected_type in {"META_REALIZADO", "ASSOCIACAO"}:
            self._validate_entities(preview)
        elif preview.detected_type == "FLUXO_CAIXA":
            self._validate_cashflow(preview)
        self._mark_duplicates(preview)
        return preview

    def import_preview(self, preview: HistoricalPreview) -> ImportReport:
        if not preview.can_import:
            raise ValueError("O preview contém erros bloqueantes.")
        backup_path = self.backup.create_import_backup()
        if preview.detected_type == "BOE":
            imported = self.boe.import_file(preview.file_path)
            logger.info("Importação histórica BOE concluída: %s", imported.id)
            return ImportReport(len(preview.rows), len(preview.rows), 0,
                                preview.duplicates, len(preview.warnings), 0,
                                str(preview.total), backup_path)
        imported = 0
        try:
            self.session.rollback()
            for row in preview.rows:
                if row.get("duplicate") or row.get("skip"):
                    continue
                self._persist(preview.detected_type, row)
                imported += 1
            self.session.commit()
        except Exception:
            self.session.rollback()
            logger.exception("Importação histórica revertida integralmente.")
            raise
        report = ImportReport(
            len(preview.rows), imported, len(preview.rows) - imported,
            preview.duplicates, len(preview.warnings), len(preview.errors),
            str(preview.total), backup_path,
        )
        logger.info("Importação histórica concluída: %s", report)
        return report

    def _validate_entities(self, preview: HistoricalPreview) -> None:
        for row in preview.rows:
            entity = self.entities.get_entity_by_code(row["code"])
            if entity is None or not entity.ativa or entity.codigo_entidade == 7500:
                preview.errors.append(
                    f"Linha {row['line']}: Entidade {row['code']} inválida ou inativa."
                )
            else:
                row["entity_id"] = entity.id

    def _validate_cashflow(self, preview: HistoricalPreview) -> None:
        official = {
            (normalized(item.descricao), item.categoria, item.tipo)
            for item in self.catalog.list_entries() if item.ativa
        }
        for row in preview.rows:
            category = CATEGORY_MAP.get(normalized(row["category_label"]))
            kind = TYPE_MAP.get(normalized(row["type_label"]))
            row["category"], row["type"] = category, kind
            if category is None or kind is None:
                preview.errors.append(f"Linha {row['line']}: Categoria ou Tipo inválido.")
            elif (normalized(row["description"]), category, kind) not in official:
                preview.errors.append(
                    f"Linha {row['line']}: combinação não encontrada no catálogo oficial."
                )
            elif kind == "SALDO" or category == "SALDO_APLICADO":
                row["skip"] = True
                preview.warnings.append(
                    f"Linha {row['line']}: saldo aplicado excluído por ser registro técnico."
                )
            elif category == "RECEITA_DIRETA":
                row["skip"] = True
                preview.warnings.append(
                    f"Linha {row['line']}: Receita Direta excluída; deve vir do importador BOE."
                )

    def _mark_duplicates(self, preview: HistoricalPreview) -> None:
        for row in preview.rows:
            duplicate = False
            if row.get("skip"):
                continue
            kind = preview.detected_type
            if kind == "FLUXO_CAIXA" and row.get("category"):
                model = InvestmentMovement if row.get("type") in {"APLICACAO", "RESGATE"} else CashflowEntry
                if model is CashflowEntry:
                    statement = select(model.id).where(
                        model.periodo_ano == row["year"], model.periodo_mes == row["month"],
                        model.descricao == row["description"], model.categoria == row["category"],
                        model.tipo == row["type"], model.valor == row["value"],
                        model.boe == row["boe"], model.observacao == row["notes"],
                    )
                else:
                    statement = select(model.id).where(
                        model.periodo_ano == row["year"], model.periodo_mes == row["month"],
                        model.descricao == row["description"], model.tipo == row["type"],
                        model.valor == row["value"], model.observacao == row["notes"],
                    )
                duplicate = self.session.scalar(statement) is not None
            elif kind == "META_REALIZADO" and row.get("entity_id"):
                duplicate = self.session.scalar(select(TargetEntry.id).where(
                    TargetEntry.entity_id == row["entity_id"],
                    TargetEntry.periodo_ano == row["year"],
                    TargetEntry.periodo_mes == row["month"],
                    TargetEntry.indicador == row["indicator"],
                )) is not None
            elif kind == "ASSOCIACAO" and row.get("entity_id"):
                existing = self.session.scalar(select(AssociationEntry).where(
                    AssociationEntry.entity_id == row["entity_id"],
                    AssociationEntry.periodo_ano == row["year"],
                    AssociationEntry.periodo_mes == row["month"],
                ))
                if existing is not None:
                    incoming = (
                        row["capture"], row["execution"],
                        row.get("cancellation", 0),
                    )
                    persisted = (
                        existing.valor_captacao, existing.valor_execucao,
                        existing.valor_cancelamento,
                    )
                    duplicate = incoming == persisted
                    if not duplicate:
                        row["update"] = True
                        row["existing_id"] = existing.id
            elif kind == "ORCAMENTO":
                duplicate = self.session.scalar(select(BudgetEntry.id).where(
                    BudgetEntry.periodo_ano == row["year"],
                    BudgetEntry.periodo_mes == row["month"], BudgetEntry.tipo == row["type"],
                    BudgetEntry.categoria == row["category"],
                )) is not None
            row["duplicate"] = duplicate
            if duplicate:
                preview.duplicates += 1

    def _persist(self, kind: str, row: dict) -> None:
        if kind == "FLUXO_CAIXA":
            if row["type"] in {"APLICACAO", "RESGATE"}:
                self.session.add(InvestmentMovement(
                    data_movimento=date(row["year"], row["month"], 1),
                    periodo_ano=row["year"], periodo_mes=row["month"], tipo=row["type"],
                    descricao=row["description"], valor=row["value"], observacao=row["notes"],
                ))
            else:
                self.session.add(CashflowEntry(
                    periodo_ano=row["year"], periodo_mes=row["month"],
                    data_lancamento=date(row["year"], row["month"], 1),
                    descricao=row["description"], tipo=row["type"], origem="MANUAL",
                    categoria=row["category"], valor=row["value"], boe=row["boe"],
                    observacao=row["notes"],
                ))
        elif kind == "META_REALIZADO":
            self.session.add(TargetEntry(
                entity_id=row["entity_id"], periodo_ano=row["year"],
                periodo_mes=row["month"], indicador=row["indicator"],
                valor_meta=row["target"], valor_realizado=row["actual"],
                observacao="Importação histórica controlada",
            ))
        elif kind == "ASSOCIACAO":
            entry = (self.session.get(AssociationEntry, row["existing_id"])
                     if row.get("update") else AssociationEntry(
                         entity_id=row["entity_id"], periodo_ano=row["year"],
                         periodo_mes=row["month"],
                     ))
            entry.valor_captacao = row["capture"]
            entry.valor_execucao = row["execution"]
            entry.valor_cancelamento = row.get("cancellation", 0)
            if not row.get("update"):
                self.session.add(entry)
        elif kind == "ORCAMENTO":
            self.session.add(BudgetEntry(
                periodo_ano=row["year"], periodo_mes=row["month"],
                tipo=row["type"], categoria=row["category"],
                valor_orcado=row["value"],
                observacao=f"Importado de: {row['source_label']}",
            ))
        else:
            raise ValueError("Tipo de importação não suportado.")

    def _analyze_boe(self, file_path) -> HistoricalPreview:
        result = self.boe.validate_file(file_path)
        preview = HistoricalPreview(Path(file_path), "BOE", result.periodo_ano)
        preview.rows = [{"line": row.linha, "code": row.codigo_entidade}
                        for row in result.linhas]
        preview.total = result.valor_total_calculado
        for issue in result.inconsistencias:
            target = preview.errors if issue.severidade.value == "error" else preview.warnings
            target.append(issue.mensagem)
        return preview
