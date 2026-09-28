from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QDialog, QMessageBox

from app.gui.pages.cadastros import CadastrosPage, CatalogDialog, EntityDialog
from app.services.cashflow_catalog_service import CashflowCatalogService
from app.services.entity_service import EntityService
from app.core.exceptions import EntityDomainError
from app.api_client.client import APIClient
from app.gui.processing import OperationWorker, ProcessingDialog


class RegistrationController(QObject):
    def __init__(self, view: CadastrosPage, entities: EntityService,
                 catalog: CashflowCatalogService) -> None:
        super().__init__(view)
        self.view, self.entities, self.catalog = view, entities, catalog
        view.new_entity_button.clicked.connect(self.new_entity)
        view.edit_entity_button.clicked.connect(self.edit_entity)
        view.toggle_entity_button.clicked.connect(self.toggle_entity)
        view.aliases_button.clicked.connect(self.show_aliases)
        view.new_catalog_button.clicked.connect(self.new_catalog)
        view.edit_catalog_button.clicked.connect(self.edit_catalog)
        self.refresh()

    def refresh(self) -> None:
        self.view.show_entities(self.entities.list_entities())
        self.view.show_catalog(self.catalog.list_entries())

    def new_entity(self) -> None:
        dialog = EntityDialog(self.view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.entities.create_entity(**dialog.values())
                self.refresh()
                self.view.set_status("Entidade cadastrada com sucesso.")
            except (ValueError, EntityDomainError) as error:
                self.view.set_status(str(error), error=True)

    def edit_entity(self) -> None:
        entity_id = self.view.selected_entity_id()
        entity = self.entities.repository.get_by_id(entity_id) if entity_id else None
        if entity is None:
            self.view.set_status("Selecione uma Entidade.", error=True)
            return
        dialog = EntityDialog(self.view, entity)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            values = dialog.values()
            values.pop("codigo_entidade")
            self.entities.update_entity(entity.id, **values)
            self.refresh()

    def toggle_entity(self) -> None:
        entity_id = self.view.selected_entity_id()
        entity = self.entities.repository.get_by_id(entity_id) if entity_id else None
        if entity is None:
            self.view.set_status("Selecione uma Entidade.", error=True)
            return
        self.entities.set_active(entity.id, not entity.ativa)
        self.refresh()

    def show_aliases(self) -> None:
        entity_id = self.view.selected_entity_id()
        entity = self.entities.repository.get_by_id(entity_id) if entity_id else None
        if entity is None:
            self.view.set_status("Selecione uma Entidade.", error=True)
            return
        aliases = "\n".join(alias.alias for alias in entity.aliases) or "Nenhum alias cadastrado."
        QMessageBox.information(self.view, "Aliases", aliases)

    def new_catalog(self) -> None:
        dialog = CatalogDialog(self.view)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.catalog.create_entry(**dialog.values())
                self.refresh()
            except ValueError as error:
                self.view.set_status(str(error), error=True)

    def edit_catalog(self) -> None:
        entry_id = self.view.selected_catalog_id()
        entry = self.catalog.repository.get_by_id(entry_id) if entry_id else None
        if entry is None:
            self.view.set_status("Selecione um item do catálogo.", error=True)
            return
        dialog = CatalogDialog(self.view, entry)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                self.catalog.update_entry(entry.id, **dialog.values())
                self.refresh()
            except ValueError as error:
                self.view.set_status(str(error), error=True)

class RemoteRegistrationController(QObject):
    """Cadastros em modo servidor: Desktop -> API -> PostgreSQL."""

    def __init__(
        self, view: CadastrosPage, api_client,
        *, allowed_areas: set[str] | None = None,
    ) -> None:
        super().__init__(view)
        from types import SimpleNamespace

        self._namespace = SimpleNamespace
        self.view = view
        self.api = api_client
        self._entities: dict[int, object] = {}
        self._catalog: dict[int, object] = {}
        self._allowed_areas = set(
            {"entities", "catalog"} if allowed_areas is None else allowed_areas
        )
        self._operation_thread: QThread | None = None
        self._operation_worker: OperationWorker | None = None
        self._operation_dialog: ProcessingDialog | None = None

        view.new_entity_button.clicked.connect(self.new_entity)
        view.edit_entity_button.clicked.connect(self.edit_entity)
        view.toggle_entity_button.clicked.connect(self.toggle_entity)
        view.aliases_button.clicked.connect(self.show_aliases)
        view.new_catalog_button.clicked.connect(self.new_catalog)
        view.edit_catalog_button.clicked.connect(self.edit_catalog)

        self.refresh()

    def _run_remote(self, title, operation, succeeded) -> None:
        """Keep real API I/O off Qt's GUI thread; test doubles stay synchronous."""
        def failed(error: Exception) -> None:
            self.view.set_status(str(error), error=True)

        if not isinstance(self.api, APIClient):
            try:
                succeeded(operation())
            except RuntimeError as error:
                failed(error)
            return
        if self._operation_thread is not None and self._operation_thread.isRunning():
            return

        dialog = ProcessingDialog(self.view, window_title=title)
        thread = QThread(self)
        worker = OperationWorker(operation)
        worker.moveToThread(thread)
        self._operation_dialog = dialog
        self._operation_thread = thread
        self._operation_worker = worker
        state = {"ok": False, "value": None, "error": None}

        worker.succeeded.connect(
            lambda value: state.update(ok=True, value=value)
        )
        worker.failed.connect(lambda error: state.update(error=error))

        def finished() -> None:
            if self._operation_dialog is not None:
                self._operation_dialog.accept()
                self._operation_dialog.deleteLater()
            if self._operation_thread is not None:
                self._operation_thread.deleteLater()
            self._operation_dialog = None
            self._operation_thread = None
            self._operation_worker = None
            if state["ok"]:
                succeeded(state["value"])
            else:
                failed(state["error"])

        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(finished)
        dialog.show()
        thread.start()

    def _load_data(self):
        entities = (
            [self._entity_object(item) for item in self.api.get("/api/v1/entities")]
            if "entities" in self._allowed_areas else []
        )
        catalog = (
            [self._catalog_object(item) for item in self.api.get("/api/v1/catalog")]
            if "catalog" in self._allowed_areas else []
        )
        return entities, catalog

    def _show_data(self, payload) -> None:
        entities, catalog = payload
        self._entities = {item.id: item for item in entities}
        self._catalog = {item.id: item for item in catalog}
        self.view.show_entities(entities)
        self.view.show_catalog(catalog)

    def set_allowed_areas(self, allowed_areas: set[str]) -> None:
        self._allowed_areas = set(allowed_areas)
        self.refresh()

    def _entity_object(self, item: dict):
        aliases = [
            self._namespace(
                id=alias.get("id"),
                alias=alias.get("alias", ""),
                origem=alias.get("origem"),
            )
            for alias in item.get("aliases", [])
        ]
        return self._namespace(
            id=item["id"],
            codigo_entidade=item["codigo_entidade"],
            nome=item["nome"],
            nome_oficial=item.get("nome_oficial"),
            municipio=item.get("municipio"),
            uf=item.get("uf"),
            regiao=item.get("regiao"),
            sigla=item.get("sigla"),
            ativa=item["ativa"],
            aliases=aliases,
        )

    def _catalog_object(self, item: dict):
        return self._namespace(
            id=item["id"],
            descricao=item["descricao"],
            categoria=item["categoria"],
            tipo=item["tipo"],
            ativa=item["ativa"],
        )

    def refresh(self) -> None:
        self._run_remote("Atualizando Cadastros", self._load_data, self._show_data)

    def new_entity(self) -> None:
        dialog = EntityDialog(self.view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        def operation():
            self.api.post("/api/v1/entities", values)
            return self._load_data()
        def succeeded(payload):
            self._show_data(payload)
            self.view.set_status("Entidade cadastrada no servidor.")
        self._run_remote("Cadastrando Entidade", operation, succeeded)

    def edit_entity(self) -> None:
        entity_id = self.view.selected_entity_id()
        entity = self._entities.get(entity_id) if entity_id else None
        if entity is None:
            self.view.set_status("Selecione uma Entidade.", error=True)
            return

        dialog = EntityDialog(self.view, entity)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        values.pop("codigo_entidade", None)

        def operation():
            self.api.patch(f"/api/v1/entities/{entity.id}", values)
            return self._load_data()
        def succeeded(payload):
            self._show_data(payload)
            self.view.set_status("Entidade atualizada no servidor.")
        self._run_remote("Atualizando Entidade", operation, succeeded)

    def toggle_entity(self) -> None:
        entity_id = self.view.selected_entity_id()
        entity = self._entities.get(entity_id) if entity_id else None
        if entity is None:
            self.view.set_status("Selecione uma Entidade.", error=True)
            return

        payload = {
            "nome": entity.nome,
            "nome_oficial": entity.nome_oficial,
            "regiao": entity.regiao,
            "sigla": entity.sigla,
            "ativa": not entity.ativa,
        }

        def operation():
            self.api.patch(f"/api/v1/entities/{entity.id}", payload)
            return self._load_data()
        def succeeded(values):
            self._show_data(values)
            self.view.set_status("Situação da Entidade atualizada no servidor.")
        self._run_remote("Alterando Entidade", operation, succeeded)

    def show_aliases(self) -> None:
        entity_id = self.view.selected_entity_id()
        if entity_id is None:
            self.view.set_status("Selecione uma Entidade.", error=True)
            return

        def succeeded(aliases):
            text = "\n".join(item["alias"] for item in aliases) or "Nenhum alias cadastrado."
            QMessageBox.information(self.view, "Aliases", text)
        self._run_remote(
            "Carregando Aliases",
            lambda: self.api.get(f"/api/v1/entities/{entity_id}/aliases"),
            succeeded,
        )

    def new_catalog(self) -> None:
        dialog = CatalogDialog(self.view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        def operation():
            self.api.post("/api/v1/catalog", values)
            return self._load_data()
        def succeeded(payload):
            self._show_data(payload)
            self.view.set_status("Item cadastrado no servidor.")
        self._run_remote("Cadastrando Item", operation, succeeded)

    def edit_catalog(self) -> None:
        entry_id = self.view.selected_catalog_id()
        entry = self._catalog.get(entry_id) if entry_id else None
        if entry is None:
            self.view.set_status("Selecione um item do catálogo.", error=True)
            return

        dialog = CatalogDialog(self.view, entry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()
        def operation():
            self.api.patch(f"/api/v1/catalog/{entry.id}", values)
            return self._load_data()
        def succeeded(payload):
            self._show_data(payload)
            self.view.set_status("Item atualizado no servidor.")
        self._run_remote("Atualizando Item", operation, succeeded)
