from __future__ import annotations

from collections.abc import Hashable, Iterable

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QListView

from app.widgets.wheel_guard import WheelBlockedComboBox


_PRESERVE_SELECTION = object()


class EntityMultiSelectCombo(WheelBlockedComboBox):
    """Combo de entidades com checkboxes e resumo legível da seleção."""

    selectionChanged = Signal()

    def __init__(self, parent=None, *, all_label: str = "Todas as Entidades"):
        super().__init__(parent)
        self._all_label = all_label
        self.setView(QListView())
        self.view().viewport().installEventFilter(self)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setCursorPosition(0)
        self.lineEdit().installEventFilter(self)
        self._field_click_in_progress = False
        self._options_loaded = False
        self.addItem(self._all_label, None)
        self._check(0, True)
        self._update_summary()

    def _check(self, row: int, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.setItemData(row, state, Qt.ItemDataRole.CheckStateRole)

    def eventFilter(self, watched, event):
        if watched is self.lineEdit():
            if (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.LeftButton
            ):
                self._field_click_in_progress = True
                self._toggle_popup()
                return True
            if (
                event.type() == QEvent.Type.MouseButtonRelease
                and self._field_click_in_progress
            ):
                self._field_click_in_progress = False
                return True
        if (
            watched is self.view().viewport()
            and event.type() == QEvent.Type.MouseButtonRelease
        ):
            index = self.view().indexAt(event.position().toPoint())
            if index.isValid():
                self.toggle_index(index.row())
                return True
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._toggle_popup()
            event.accept()
            return
        super().mousePressEvent(event)

    def _toggle_popup(self) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        if self.view().isVisible():
            self.hidePopup()
        else:
            self.showPopup()

    def toggle_index(self, row: int) -> None:
        if not 0 <= row < self.count():
            return
        if row == 0:
            checked = (
                self.itemData(0, Qt.ItemDataRole.CheckStateRole)
                != Qt.CheckState.Checked
            )
            for index in range(self.count()):
                self._check(index, checked)
        else:
            checked = (
                self.itemData(row, Qt.ItemDataRole.CheckStateRole)
                != Qt.CheckState.Checked
            )
            self._check(row, checked)
            all_selected = self.count() > 1 and all(
                self.itemData(index, Qt.ItemDataRole.CheckStateRole)
                == Qt.CheckState.Checked
                for index in range(1, self.count())
            )
            self._check(0, all_selected)
        self._update_summary()
        self.selectionChanged.emit()

    def set_options(
        self,
        options: Iterable[tuple[str, Hashable]],
        selected_values=_PRESERVE_SELECTION,
    ) -> None:
        if selected_values is _PRESERVE_SELECTION:
            selected_values = self.selected_values()
        selected = set(selected_values or ())
        all_selected = selected_values is None

        unique_options: list[tuple[str, Hashable]] = []
        seen: set[Hashable] = set()
        for label, value in options:
            if value in seen:
                continue
            seen.add(value)
            unique_options.append((label, value))

        self._options_loaded = True
        if not unique_options:
            all_selected = False

        self.clear()
        self.addItem(self._all_label, None)
        for label, value in unique_options:
            self.addItem(label, value)

        self._check(0, all_selected)
        for index in range(1, self.count()):
            self._check(
                index,
                all_selected or self.itemData(index) in selected,
            )
        self._update_summary()

    def set_entities(self, entities, selected_ids=_PRESERVE_SELECTION) -> None:
        options = (
            (
                f"{entity.codigo_entidade} — "
                f"{entity.nome_oficial or entity.nome}",
                int(entity.id),
            )
            for entity in entities
        )
        self.set_options(options, selected_ids)

    def set_selected_values(
        self, selected_values: Iterable[Hashable] | None
    ) -> None:
        self.set_options(
            (
                (self.itemText(index), self.itemData(index))
                for index in range(1, self.count())
            ),
            selected_values,
        )

    def selected_values(self) -> tuple[Hashable, ...] | None:
        if not self._options_loaded:
            return None
        values = tuple(
            self.itemData(index)
            for index in range(1, self.count())
            if self.itemData(index, Qt.ItemDataRole.CheckStateRole)
            == Qt.CheckState.Checked
        )
        if self.count() > 1 and len(values) == self.count() - 1:
            return None
        return values

    def selected_ids(self) -> tuple[int, ...] | None:
        values = self.selected_values()
        if values is None:
            return None
        return tuple(int(value) for value in values)

    def selection_text(self) -> str:
        if not self._options_loaded:
            return "Carregando Entidades..."
        values = self.selected_values()
        if self.count() == 1:
            return "Nenhuma Entidade disponível"
        if values is None:
            return self._all_label
        if not values:
            return "Nenhuma Entidade"
        if len(values) == 1:
            selected = values[0]
            for index in range(1, self.count()):
                if self.itemData(index) == selected:
                    return self.itemText(index)
        return f"{len(values)} Entidades selecionadas"

    def _update_summary(self) -> None:
        summary = self.selection_text()
        self.setToolTip(summary)
        if self.lineEdit() is not None:
            self.lineEdit().setText(summary)
            self.lineEdit().setCursorPosition(0)
