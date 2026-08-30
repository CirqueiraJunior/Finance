from PySide6.QtCore import QObject
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import CSVExportValidationError
from app.gui.pages.relatorios import RelatoriosPage
from app.services.report_service import ReportService
from app.services.site_csv_service import SiteCSVService


class ReportController(QObject):
    def __init__(
        self,
        view: RelatoriosPage,
        report_service: ReportService,
        csv_service: SiteCSVService,
    ) -> None:
        super().__init__(view)
        self.view = view
        self.report_service = report_service
        self.csv_service = csv_service
        self.view.refresh_button.clicked.connect(self.refresh)
        self.view.choose_folder_button.clicked.connect(self.view.choose_destination)
        self.view.validate_button.clicked.connect(self.validate_csv)
        self.view.export_button.clicked.connect(self.export_csv)
        self.refresh()

    def refresh(self) -> None:
        try:
            self.view.show_report(
                self.report_service.get_annual_report(self.view.selected_year())
            )
            self.view.set_status("Relatório anual atualizado.")
        except (ValueError, SQLAlchemyError, RuntimeError) as error:
            self._rollback()
            self.view.set_status(f"Falha ao carregar relatório: {error}", error=True)

    def validate_csv(self) -> None:
        try:
            result = self.csv_service.validate_year(self.view.selected_year())
        except (CSVExportValidationError, SQLAlchemyError, RuntimeError) as error:
            self._rollback()
            self.view.set_status(f"Falha na validação: {error}", error=True)
            return
        lines = [
            f"Status: {'APROVADO' if result.valid else 'BLOQUEADO'}",
            f"Entidades: {result.entity_count}",
            f"Meta/Realizado: {result.target_rows} registros",
            f"Associação: {result.association_rows} registros",
        ]
        if result.errors:
            lines.extend(["", "Primeiras inconsistências:", *result.errors[:12]])
            if len(result.errors) > 12:
                lines.append(f"... e mais {len(result.errors) - 12} inconsistências.")
        self.view.show_export_message("\n".join(lines))
        self.view.set_status(
            "Validação concluída." if result.valid else "Exportação bloqueada por inconsistências.",
            error=not result.valid,
        )

    def export_csv(self) -> None:
        destination = self.view.destination()
        if destination is None:
            self.view.set_status("Selecione a pasta de exportação.", error=True)
            return
        try:
            result = self.csv_service.export_all(self.view.selected_year(), destination)
        except CSVExportValidationError as error:
            self.view.show_export_message(
                "Exportação bloqueada.\n\n" + "\n".join(error.errors[:15])
            )
            self.view.set_status("Corrija as inconsistências antes de exportar.", error=True)
            return
        except (OSError, SQLAlchemyError, RuntimeError) as error:
            self._rollback()
            self.view.set_status(f"Falha ao exportar: {error}", error=True)
            return
        self.view.show_export_message(
            "Exportação concluída:\n"
            + "\n".join(path.name for path in result.files)
            + f"\n\nRelatório: {result.report_file.name}"
        )
        self.view.set_status("Cinco CSVs gerados com sucesso.")

    def _rollback(self) -> None:
        self.csv_service.export_repository.session.rollback()
