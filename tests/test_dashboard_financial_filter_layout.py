from PySide6.QtWidgets import (
    QComboBox,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QStyleOptionComboBox,
)

from app.gui.pages.dashboard import DashboardPage
from app.resources import load_stylesheet
from app.widgets.month_combo import MONTH_NAMES


def _combo_text_rect(combo: QComboBox):
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    return combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxEditField,
        combo,
    )


def _button_text_rect(button: QPushButton):
    option = QStyleOptionButton()
    button.initStyleOption(option)
    return button.style().subElementRect(
        QStyle.SubElement.SE_PushButtonContents,
        option,
        button,
    )


def test_financial_dashboard_filters_fit_the_normal_maximized_width(qtbot, qapp):
    previous_stylesheet = qapp.styleSheet()
    qapp.setStyleSheet(load_stylesheet())
    try:
        page = DashboardPage()
        qtbot.addWidget(page)
        page.set_available_years([2025, 2026], [], [])

        # 1920 px de janela menos a sidebar homologada de 220 px.
        page.resize(1700, 900)
        page.show()
        qapp.processEvents()

        month_filters = (
            page.financial_start_month,
            page.financial_end_month,
        )
        assert [
            page.financial_start_month.itemText(index)
            for index in range(page.financial_start_month.count())
        ] == list(MONTH_NAMES)
        for combo in month_filters:
            text_width = max(
                combo.fontMetrics().horizontalAdvance(month)
                for month in MONTH_NAMES
            )
            assert _combo_text_rect(combo).width() >= text_width
            for month in (9, 11, 12):
                combo.set_month(month)
                assert combo.currentText() == MONTH_NAMES[month - 1]

        for combo in (page.financial_start_year, page.financial_end_year):
            text_width = max(
                combo.fontMetrics().horizontalAdvance(combo.itemText(index))
                for index in range(combo.count())
            )
            assert _combo_text_rect(combo).width() >= text_width
            assert all(len(combo.itemText(index)) == 4 for index in range(combo.count()))

        button_text_width = page.refresh_button.fontMetrics().horizontalAdvance(
            page.refresh_button.text()
        )
        assert page.refresh_button.text() == "Atualizar Dashboard"
        assert _button_text_rect(page.refresh_button).width() >= button_text_width

        panel = page.financial_filter_panel
        assert panel.geometry().right() <= panel.parentWidget().contentsRect().right()
        widgets = [
            panel.layout().itemAt(index).widget()
            for index in range(panel.layout().count())
            if panel.layout().itemAt(index).widget() is not None
        ]
        assert all(widget.isVisible() for widget in widgets)
        assert all(
            left.geometry().right() < right.geometry().left()
            for left, right in zip(widgets, widgets[1:])
        )
    finally:
        qapp.setStyleSheet(previous_stylesheet)
