from datetime import date
from decimal import Decimal

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import DashboardSummary
from app.widgets import MonthComboBox


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("contentPage")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Dashboard Executivo")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Visão consolidada dos módulos homologados, sem novos cálculos de domínio."
        )
        description.setObjectName("pageDescription")
        filters = QHBoxLayout()
        self.year_filter = QSpinBox()
        self.year_filter.setRange(2000, 9999)
        self.year_filter.setValue(date.today().year)
        self.month_filter = MonthComboBox()
        self.month_filter.set_month(date.today().month)
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.setObjectName("primaryButton")
        filters.addWidget(QLabel("Ano"))
        filters.addWidget(self.year_filter)
        filters.addWidget(QLabel("Mês"))
        filters.addWidget(self.month_filter)
        filters.addWidget(self.refresh_button)
        filters.addStretch()

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(filters)

        layout.addWidget(self._section("Financeiro"))
        finance_grid = QGridLayout()
        self.financial_cards = {}
        financial_titles = (
            ("total_revenue", "Receita Total"),
            ("total_expense", "Despesa Total"),
            ("operational_result", "Resultado Operacional"),
            ("cash_movement", "Movimentação de Caixa"),
            ("applied_balance", "Saldo Aplicado"),
            ("applications", "Aplicações"),
            ("redemptions", "Resgates"),
        )
        for index, (key, label) in enumerate(financial_titles):
            card, value = self._card(label)
            self.financial_cards[key] = value
            finance_grid.addWidget(card, index // 4, index % 4)
        layout.addLayout(finance_grid)

        layout.addWidget(self._section("BOE"))
        boe_cards = QHBoxLayout()
        self.boe_entities = self._add_card(boe_cards, "Entidades", "0")
        self.boe_queries = self._add_card(boe_cards, "Consultas", "0")
        self.boe_value = self._add_card(boe_cards, "Valor BOE")
        layout.addLayout(boe_cards)
        self.boe_state = QLabel("Sem dados BOE para o período.")
        self.boe_state.setObjectName("pageDescription")
        layout.addWidget(self.boe_state)

        layout.addWidget(self._section("Orçado x Realizado"))
        self.budget_table = QTableWidget(3, 3)
        self.budget_table.setObjectName("dashboardBudgetTable")
        self.budget_table.setHorizontalHeaderLabels(["Grupo", "Orçado", "Realizado"])
        self.budget_table.setVerticalHeaderLabels(["Receitas", "Despesas", "Resultado"])
        self.budget_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.budget_table.setMaximumHeight(155)
        self.budget_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.budget_table)

        layout.addWidget(self._section("Meta x Realizado"))
        targets = QHBoxLayout()
        query_card, self.query_target, self.query_actual, self.query_achievement = (
            self._target_card("Consultas")
        )
        registration_card, self.registration_target, self.registration_actual, (
            self.registration_achievement
        ) = self._target_card("Registros")
        targets.addWidget(query_card, 1)
        targets.addWidget(registration_card, 1)
        layout.addLayout(targets)
        self.target_state = QLabel("Sem dados de Meta x Realizado para o período.")
        self.target_state.setObjectName("pageDescription")
        layout.addWidget(self.target_state)

        charts = QGridLayout()
        self.finance_chart = self._chart_view("financeChart")
        self.budget_chart = self._chart_view("budgetChart")
        self.target_chart = self._chart_view("targetChart")
        charts.addWidget(self.finance_chart, 0, 0)
        charts.addWidget(self.budget_chart, 0, 1)
        charts.addWidget(self.target_chart, 1, 0, 1, 2)
        layout.addLayout(charts)

        self.status = QLabel("Dashboard pronto.")
        self.status.setObjectName("operationStatus")
        layout.addWidget(self.status)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    @staticmethod
    def _card(title: str, initial: str = "R$ 0,0000") -> tuple[QWidget, QLabel]:
        card = QWidget()
        card.setObjectName("summaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        label = QLabel(title)
        label.setObjectName("summaryLabel")
        value = QLabel(initial)
        value.setObjectName("summaryValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        return card, value

    @classmethod
    def _add_card(cls, layout: QHBoxLayout, title: str, initial="R$ 0,0000") -> QLabel:
        card, value = cls._card(title, initial)
        layout.addWidget(card, 1)
        return value

    @staticmethod
    def _target_card(title: str) -> tuple[QWidget, QLabel, QLabel, QLabel]:
        card = QWidget()
        card.setObjectName("summaryCard")
        grid = QGridLayout(card)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        target = QLabel("0,0000")
        actual = QLabel("0,0000")
        achievement = QLabel("—")
        achievement.setObjectName("summaryValue")
        grid.addWidget(heading, 0, 0, 1, 2)
        grid.addWidget(QLabel("Meta"), 1, 0)
        grid.addWidget(target, 1, 1)
        grid.addWidget(QLabel("Realizado"), 2, 0)
        grid.addWidget(actual, 2, 1)
        grid.addWidget(QLabel("Atingimento"), 3, 0)
        grid.addWidget(achievement, 3, 1)
        return card, target, actual, achievement

    @staticmethod
    def _chart_view(name: str) -> QChartView:
        chart = QChart()
        chart.setTitleFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        chart.legend().setFont(QFont("Segoe UI", 8))
        view = QChartView(chart)
        view.setObjectName(name)
        view.setFont(QFont("Segoe UI", 9))
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setMinimumHeight(220)
        return view

    def selected_period(self) -> tuple[int, int]:
        return self.year_filter.value(), self.month_filter.currentData()

    def set_period(self, year: int, month: int) -> None:
        self.year_filter.setValue(year)
        self.month_filter.set_month(month)

    def show_summary(self, summary: DashboardSummary) -> None:
        financial = summary.financial
        for field, label in self.financial_cards.items():
            label.setText(self.currency(getattr(financial, field)))
        self.boe_entities.setText(self.integer(summary.boe.entities))
        self.boe_queries.setText(self.integer(summary.boe.queries))
        self.boe_value.setText(self.currency(summary.boe.total_value))
        self.boe_state.setVisible(not summary.boe.has_data)

        budget = summary.budget
        budget_rows = (
            (budget.budgeted_revenue, budget.actual_revenue),
            (budget.budgeted_expense, budget.actual_expense),
            (budget.budgeted_result, budget.actual_result),
        )
        for row, values in enumerate(budget_rows):
            self.budget_table.setItem(row, 0, QTableWidgetItem(self.budget_table.verticalHeaderItem(row).text()))
            self.budget_table.setItem(row, 1, QTableWidgetItem(self.currency(values[0])))
            self.budget_table.setItem(row, 2, QTableWidgetItem(self.currency(values[1])))

        self._show_target(
            summary.targets.queries,
            self.query_target,
            self.query_actual,
            self.query_achievement,
        )
        self._show_target(
            summary.targets.registrations,
            self.registration_target,
            self.registration_actual,
            self.registration_achievement,
        )
        self.target_state.setVisible(
            not summary.targets.queries.has_data
            and not summary.targets.registrations.has_data
        )

        self.finance_chart.setChart(
            self._bar_chart(
                "Receitas x Despesas",
                ["Financeiro"],
                [("Receitas", [financial.total_revenue]),
                 ("Despesas", [financial.total_expense])],
            )
        )
        self.budget_chart.setChart(
            self._bar_chart(
                "Orçado x Realizado",
                ["Receitas", "Despesas"],
                [("Orçado", [budget.budgeted_revenue, budget.budgeted_expense]),
                 ("Realizado", [budget.actual_revenue, budget.actual_expense])],
            )
        )
        self.target_chart.setChart(
            self._bar_chart(
                "Atingimento das Metas",
                ["Consultas", "Registros"],
                [("Atingimento %", [
                    summary.targets.queries.achievement_percentage or Decimal("0"),
                    summary.targets.registrations.achievement_percentage or Decimal("0"),
                ])],
            )
        )

    def _show_target(self, result, target: QLabel, actual: QLabel, achievement: QLabel) -> None:
        target.setText(self.number(result.target))
        actual.setText(self.number(result.actual))
        achievement.setText(self.percentage(result.achievement_percentage))

    @staticmethod
    def _bar_chart(title: str, categories: list[str], series_data) -> QChart:
        series = QBarSeries()
        maximum = 0.0
        for name, values in series_data:
            bar_set = QBarSet(name)
            numeric = [float(value) for value in values]
            bar_set.append(numeric)
            maximum = max(maximum, *numeric)
            series.append(bar_set)
        chart = QChart()
        chart.addSeries(series)
        chart.setTitleFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        chart.setTitle(title)
        chart.legend().setVisible(True)
        chart.legend().setFont(QFont("Segoe UI", 8))
        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        axis_y.setRange(0, maximum * 1.15 if maximum > 0 else 1)
        axis_y.setLabelFormat("%.1f")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        return chart

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    @staticmethod
    def currency(value: Decimal) -> str:
        return "R$ " + DashboardPage.number(value)

    @staticmethod
    def number(value: Decimal) -> str:
        formatted = f"{value:,.4f}"
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def integer(value: int) -> str:
        return f"{value:,}".replace(",", ".")

    @staticmethod
    def percentage(value: Decimal | None) -> str:
        return "—" if value is None else f"{value:.4f}%".replace(".", ",")
