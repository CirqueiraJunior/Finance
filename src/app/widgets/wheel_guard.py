from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QSpinBox,
    QTabBar,
    QTabWidget,
)


class WheelBlockedComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class WheelBlockedSpinBox(QSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class WheelBlockedDoubleSpinBox(QDoubleSpinBox):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class WheelBlockedDateEdit(QDateEdit):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class WheelBlockedTabBar(QTabBar):
    def wheelEvent(self, event) -> None:  # noqa: N802
        event.ignore()


class WheelBlockedTabWidget(QTabWidget):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.setTabBar(WheelBlockedTabBar(self))
