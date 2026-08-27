from PySide6.QtWidgets import QComboBox


MONTH_NAMES = (
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
)


class MonthComboBox(QComboBox):
    """Seletor mensal padronizado com nome visível e número interno."""

    def __init__(self, parent=None, *, include_all: bool = False) -> None:
        super().__init__(parent)
        if include_all:
            self.addItem("Ano completo", 0)
        for month, name in enumerate(MONTH_NAMES, start=1):
            self.addItem(name, month)

    def set_month(self, month: int | None) -> None:
        value = 0 if month is None else month
        index = self.findData(value)
        if index < 0:
            raise ValueError("Mês inválido para o seletor.")
        self.setCurrentIndex(index)

    def month(self) -> int:
        return int(self.currentData())
