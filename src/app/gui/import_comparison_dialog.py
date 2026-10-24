from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ImportComparisonDialog(QDialog):
    """Reusable read-only comparison; returns only a user decision."""

    def __init__(
        self,
        *,
        title,
        indicators,
        columns,
        rows,
        can_authorize=False,
        empty_message=None,
        explanation=None,
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName("importComparisonDialog")
        self.setWindowTitle(title)
        self.setMinimumWidth(780)
        self.resize(1100 if rows else 840, 650 if rows else 350)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("importComparisonTitle")
        heading.setStyleSheet("font-weight: 700; font-size: 15px;")
        layout.addWidget(heading)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.count_labels = []

        for label, value in indicators:
            card = QWidget()
            card.setObjectName("importComparisonCard")
            card.setMinimumHeight(112)
            card.setStyleSheet(
                "QWidget#importComparisonCard {"
                "background: #FFFFFF;"
                "border: 1px solid #CBD8E6;"
                "border-radius: 10px;"
                "}"
            )

            inner = QVBoxLayout(card)
            inner.setContentsMargins(18, 12, 18, 12)
            inner.setSpacing(4)

            caption = QLabel(str(label))
            caption.setStyleSheet(
                "color: #405A77; border: none;"
                "background: transparent;"
            )
            value_label = QLabel(str(value))
            value_label.setObjectName("importComparisonCardValue")
            value_label.setStyleSheet(
                "color: #123F6D; font-size: 30px;"
                "font-weight: 700; border: none;"
                "background: transparent;"
            )

            inner.addWidget(caption)
            inner.addWidget(value_label)
            cards.addWidget(card, 1)
            self.count_labels.append(value_label)

        layout.addLayout(cards)

        self.table = None

        if rows:
            if len(columns) == 0:
                raise ValueError("Comparison columns cannot be empty.")

            if explanation:
                details = QLabel(explanation)
                details.setWordWrap(True)
                layout.addWidget(details)

            table = QTableWidget(len(rows), len(columns))
            table.setObjectName("importComparisonTable")
            table.setHorizontalHeaderLabels(
                [str(column) for column in columns]
            )
            table.setEditTriggers(
                QTableWidget.EditTrigger.NoEditTriggers
            )
            table.setSelectionBehavior(
                QTableWidget.SelectionBehavior.SelectRows
            )
            table.setAlternatingRowColors(True)

            for index, values in enumerate(rows):
                if len(values) != len(columns):
                    raise ValueError(
                        "Each comparison row must match the column count."
                    )
                for column, value in enumerate(values):
                    table.setItem(
                        index,
                        column,
                        QTableWidgetItem(
                            "-" if value is None else str(value)
                        ),
                    )

            header = table.horizontalHeader()
            header.setSectionResizeMode(
                QHeaderView.ResizeMode.ResizeToContents
            )
            header.setStretchLastSection(True)

            layout.addWidget(table, 1)
            self.table = table

        else:
            notice = QLabel(
                empty_message
                or "Nenhuma altera\u00e7\u00e3o identificada."
            )
            notice.setObjectName("importComparisonEmptyNotice")
            notice.setWordWrap(True)
            notice.setMinimumHeight(78)
            notice.setStyleSheet(
                "QLabel#importComparisonEmptyNotice {"
                "background: #EAF8F2;"
                "border: 1px solid #A8DFC4;"
                "border-radius: 9px;"
                "padding: 16px;"
                "color: #116747;"
                "font-weight: 600;"
                "}"
            )
            layout.addWidget(notice)

        allowed = bool(can_authorize and rows)

        guidance = QLabel(
            "Confirmar altera\u00e7\u00f5es libera a etapa Importar, "
            "mas n\u00e3o grava dados nesta etapa."
            if allowed else
            "Nenhuma autoriza\u00e7\u00e3o de importa\u00e7\u00e3o "
            "est\u00e1 dispon\u00edvel nesta compara\u00e7\u00e3o."
        )
        guidance.setObjectName("importComparisonGuidance")
        guidance.setWordWrap(True)
        layout.addWidget(guidance)

        footer = QDialogButtonBox()
        cancel = footer.addButton(
            "Cancelar",
            QDialogButtonBox.ButtonRole.RejectRole,
        )
        cancel.clicked.connect(self.reject)

        self.authorize_button = None

        if allowed:
            authorize = footer.addButton(
                "Confirmar altera\u00e7\u00f5es",
                QDialogButtonBox.ButtonRole.AcceptRole,
            )
            authorize.clicked.connect(self.accept)
            authorize.setDefault(True)
            self.authorize_button = authorize

        layout.addWidget(footer)
