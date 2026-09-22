from collections.abc import Mapping

from PySide6.QtWidgets import QStackedWidget


class NavigationController:
    def __init__(
        self,
        stack: QStackedWidget,
        page_indexes: Mapping[str, int],
        allowed_pages: set[str] | None = None,
    ) -> None:
        self._stack = stack
        self._page_indexes = dict(page_indexes)
        self._allowed_pages = set(
            self._page_indexes if allowed_pages is None else allowed_pages
        )

    @property
    def allowed_pages(self) -> set[str]:
        return set(self._allowed_pages)

    def set_allowed_pages(self, allowed_pages: set[str]) -> None:
        self._allowed_pages = set(allowed_pages) & self._page_indexes.keys()

    def first_allowed_page(self) -> str | None:
        return next(
            (key for key in self._page_indexes if key in self._allowed_pages),
            None,
        )

    def navigate_to(self, page_key: str) -> None:
        if page_key not in self._page_indexes:
            raise ValueError(f"Página desconhecida: {page_key}")
        if page_key not in self._allowed_pages:
            raise PermissionError(f"Acesso não autorizado à página: {page_key}")
        self._stack.setCurrentIndex(self._page_indexes[page_key])
