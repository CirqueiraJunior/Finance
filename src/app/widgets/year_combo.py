from collections.abc import Iterable
from datetime import date

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QComboBox

from app.gui.processing import OperationWorker


def populate_year_combo(
    combo: QComboBox,
    years: Iterable[int],
    *,
    preferred: int | None = None,
) -> int | None:
    """Populate a year combo while preserving a valid current selection."""
    options = sorted({int(year) for year in years})
    current = combo.currentData()
    selected = current if current in options else preferred
    if selected not in options:
        today = date.today().year
        selected = today if today in options else (options[-1] if options else None)

    combo.blockSignals(True)
    combo.clear()
    for year in options:
        combo.addItem(str(year), year)
    if selected is not None:
        combo.setCurrentIndex(combo.findData(selected))
    combo.setEnabled(bool(options))
    combo.blockSignals(False)
    return selected


def select_year(combo: QComboBox, year: int) -> bool:
    index = combo.findData(int(year))
    if index < 0:
        return False
    combo.setCurrentIndex(index)
    return True


class AvailableYearsLoader(QObject):
    """Load year options without blocking remote Desktop requests."""

    _result_ready = Signal(int, object)
    _error_ready = Signal(int, object)

    def __init__(self, parent: QObject, operation, succeeded, failed) -> None:
        super().__init__(parent)
        self.operation = operation
        self.succeeded = succeeded
        self.failed = failed
        self._generation = 0
        self._thread: QThread | None = None
        self._worker: OperationWorker | None = None

        self._result_ready.connect(self._deliver_result)
        self._error_ready.connect(self._deliver_error)

    def load(self, *, remote: bool) -> None:
        if self._thread is not None and self._thread.isRunning():
            return

        self._generation += 1
        generation = self._generation

        if not remote:
            try:
                self.succeeded(self.operation())
            except Exception as error:
                self.failed(error)
            return

        thread = QThread(self)
        worker = OperationWorker(self.operation)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.succeeded.connect(
            lambda result, generation=generation:
            self._result_ready.emit(generation, result)
        )
        worker.failed.connect(
            lambda error, generation=generation:
            self._error_ready.emit(generation, error)
        )

        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear)

        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot(int, object)
    def _deliver_result(self, generation: int, result) -> None:
        if generation == self._generation:
            self.succeeded(result)

    @Slot(int, object)
    def _deliver_error(self, generation: int, error) -> None:
        if generation == self._generation:
            self.failed(error)

    @Slot()
    def _clear(self) -> None:
        self._thread = None
        self._worker = None
