from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from app.gui.pages.cadastros import CadastrosPage, CatalogDialog, EntityDialog
from app.services.cashflow_catalog_service import CashflowCatalogService
from app.services.entity_service import EntityService
from app.core.exceptions import EntityDomainError


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

    def __init__(self, view: CadastrosPage, api_client) -> None:
        super().__init__(view)
        from types import SimpleNamespace

        self._namespace = SimpleNamespace
        self.view = view
        self.api = api_client
        self._entities: dict[int, object] = {}
        self._catalog: dict[int, object] = {}

        view.new_entity_button.clicked.connect(self.new_entity)
        view.edit_entity_button.clicked.connect(self.edit_entity)
        view.toggle_entity_button.clicked.connect(self.toggle_entity)
        view.aliases_button.clicked.connect(self.show_aliases)
        view.new_catalog_button.clicked.connect(self.new_catalog)
        view.edit_catalog_button.clicked.connect(self.edit_catalog)

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
        try:
            entities = [
                self._entity_object(item)
                for item in self.api.get("/api/v1/entities")
            ]
            catalog = [
                self._catalog_object(item)
                for item in self.api.get("/api/v1/catalog")
            ]
        except RuntimeError as error:
            self.view.set_status(str(error), error=True)
            return

        self._entities = {item.id: item for item in entities}
        self._catalog = {item.id: item for item in catalog}
        self.view.show_entities(entities)
        self.view.show_catalog(catalog)

    def new_entity(self) -> None:
        dialog = EntityDialog(self.view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.api.post("/api/v1/entities", dialog.values())
            self.refresh()
            self.view.set_status("Entidade cadastrada no servidor.")
        except RuntimeError as error:
            self.view.set_status(str(error), error=True)

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

        try:
            self.api.patch(f"/api/v1/entities/{entity.id}", values)
            self.refresh()
            self.view.set_status("Entidade atualizada no servidor.")
        except RuntimeError as error:
            self.view.set_status(str(error), error=True)

    def toggle_entity(self) -> None:
        entity_id = self.view.selected_entity_id()
        entity = self._entities.get(entity_id) if entity_id else None
        if entity is None:
            self.view.set_status("Selecione uma Entidade.", error=True)
            return

        payload = {
            "nome": entity.nome,
            "nome_oficial": entity.nome_oficial,
            "municipio": entity.municipio,
            "uf": entity.uf,
            "sigla": entity.sigla,
            "ativa": not entity.ativa,
        }

        try:
            self.api.patch(f"/api/v1/entities/{entity.id}", payload)
            self.refresh()
            self.view.set_status("Situação da Entidade atualizada no servidor.")
        except RuntimeError as error:
            self.view.set_status(str(error), error=True)

    def show_aliases(self) -> None:
        entity_id = self.view.selected_entity_id()
        if entity_id is None:
            self.view.set_status("Selecione uma Entidade.", error=True)
            return

        try:
            aliases = self.api.get(f"/api/v1/entities/{entity_id}/aliases")
        except RuntimeError as error:
            self.view.set_status(str(error), error=True)
            return

        text = "\n".join(item["alias"] for item in aliases) or "Nenhum alias cadastrado."
        QMessageBox.information(self.view, "Aliases", text)

    def new_catalog(self) -> None:
        dialog = CatalogDialog(self.view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.api.post("/api/v1/catalog", dialog.values())
            self.refresh()
            self.view.set_status("Item cadastrado no servidor.")
        except RuntimeError as error:
            self.view.set_status(str(error), error=True)

    def edit_catalog(self) -> None:
        entry_id = self.view.selected_catalog_id()
        entry = self._catalog.get(entry_id) if entry_id else None
        if entry is None:
            self.view.set_status("Selecione um item do catálogo.", error=True)
            return

        dialog = CatalogDialog(self.view, entry)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.api.patch(f"/api/v1/catalog/{entry.id}", dialog.values())
            self.refresh()
            self.view.set_status("Item atualizado no servidor.")
        except RuntimeError as error:
            self.view.set_status(str(error), error=True)
