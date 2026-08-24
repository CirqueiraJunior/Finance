from collections.abc import Mapping

from PySide6.QtWidgets import QStackedWidget


class NavigationController:
    def __init__(
        self,
        stack: QStackedWidget,
        page_indexes: Mapping[str, int],
    ) -> None:
        self._stack = stack
        self._page_indexes = dict(page_indexes)

    def navigate_to(self, page_key: str) -> None:
        try:
            self._stack.setCurrentIndex(self._page_indexes[page_key])
        except KeyError as error:
            raise ValueError(f"Página desconhecida: {page_key}") from error

