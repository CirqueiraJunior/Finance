from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRectF, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget


class _SpinningGear(QWidget):
    """Small, dependency-free activity indicator used by import dialogs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(54, 54)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._advance)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _advance(self) -> None:
        self._angle = (self._angle + 15) % 360
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self._angle)
        pen = QPen(QColor("#1f6f78"), 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(QRectF(-17, -17, 34, 34), 30 * 16, 285 * 16)
        painter.drawLine(0, -24, 0, -17)
        painter.drawLine(17, 0, 24, 0)
        painter.drawLine(0, 17, 0, 24)
        painter.drawLine(-24, 0, -17, 0)


class ProcessingDialog(QDialog):
    """Reusable non-dismissible modal indicator for background operations."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        window_title: str = "Processamento",
        title: str = "Processando importação...",
        description: str = "Aguarde enquanto os dados são validados e gravados.",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("processingDialog")
        self.setWindowTitle(window_title)
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(410)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(10)
        self.gear = _SpinningGear(self)
        self.title = QLabel(title)
        self.title.setObjectName("sectionTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description = QLabel(description)
        self.description.setObjectName("pageDescription")
        self.description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.gear, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.description)

    def showEvent(self, event) -> None:
        self.gear.start()
        super().showEvent(event)

    def done(self, result: int) -> None:
        self.gear.stop()
        super().done(result)

    def reject(self) -> None:
        return


class OperationWorker(QObject):
    """Runs a callable off the GUI thread and reports only through signals."""

    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self._operation())
        except Exception as error:
            self.failed.emit(error)
        finally:
            self.finished.emit()
