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
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.dashboard_service import DashboardSummary
from app.widgets import MonthComboBox
from app.widgets.buttons import PrimaryButton


class DashboardChartView(QChartView):
    """QChartView com rótulos legíveis, sem notação científica."""

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        chart = self.chart()
        payload = getattr(chart, "_dashboard_labels", None)
        if not payload:
            return
        categories = payload["categories"]
        series_values = payload["series_values"]
        label_kind = payload["label_kind"]
        if not categories or not series_values:
            return

        plot = chart.plotArea()
        if plot.width() <= 0 or plot.height() <= 0:
            return
        series = chart.series()[0] if chart.series() else None
        if series is None:
            return
        axes = chart.axes()
        y_axis = next((axis for axis in axes if isinstance(axis, QValueAxis)), None)
        if y_axis is None:
            return
        y_min, y_max = y_axis.min(), y_axis.max()
        span = y_max - y_min
        if span <= 0:
            return

        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setFont(QFont("Segoe UI", 7))
        painter.setPen(QColor("#334155"))

        count = len(categories)
        sets_count = max(1, len(series_values))
        slot = plot.width() / count
        group_width = slot * float(series.barWidth())
        if group_width <= 0:
            group_width = slot * 0.5
        bar_width = group_width / sets_count

        for set_index, values in enumerate(series_values):
            for index, value in enumerate(values):
                value = float(value)
                if value == 0:
                    continue
                center_x = (plot.left() + slot * index + slot / 2
                            - group_width / 2 + bar_width * (set_index + 0.5))
                y_value = plot.bottom() - ((value - y_min) / span) * plot.height()
                text = self._format_chart_value(value, label_kind)
                metrics = painter.fontMetrics()
                text_width = metrics.horizontalAdvance(text)
                text_height = metrics.height()
                x = center_x - text_width / 2
                if value >= 0:
                    y = max(plot.top() + text_height, y_value - 4)
                else:
                    y = min(plot.bottom() - 2, y_value + text_height + 4)
                painter.drawText(int(x), int(y), text)
        painter.end()

    @staticmethod
    def _format_chart_value(value: float, kind: str) -> str:
        if kind == "percentage":
            return f"{value:.1f}%".replace(".", ",")
        absolute = abs(value)
        if absolute >= 1_000_000:
            text = f"{value / 1_000_000:.1f} mi"
        elif absolute >= 1_000:
            text = f"{value / 1_000:.1f} mil"
        elif absolute >= 100:
            text = f"{value:.0f}"
        else:
            text = f"{value:.1f}"
        return text.replace(".", ",")


class DashboardPage(QWidget):
    CHART_COLORS = {
        "Receita": "#1D4ED8",
        "Receitas": "#1D4ED8",
        "Despesa": "#DC2626",
        "Despesas": "#DC2626",
        "Saldo": "#0F4F86",
        "Orçado": "#D2A52E",
        "Realizado": "#16A34A",
        "Meta": "#2563EB",
        "Valor": "#0F4F86",
        "Consultas": "#2563EB",
        "Atingimento %": "#7C3AED",
        "Aplicação": "#D2A52E",
        "Resgate": "#16A34A",
        "Score": "#7C3AED",
    }
    CHART_FALLBACK = ("#2563EB", "#D2A52E", "#16A34A", "#7C3AED", "#DC2626", "#0891B2")

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
        layout.setContentsMargins(32, 2, 32, 12)
        layout.setSpacing(6)

        title = QLabel("Dashboard Executivo")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Visão consolidada dos módulos homologados, sem novos cálculos de domínio."
        )
        description.setObjectName("pageDescription")
        filters = QHBoxLayout()
        self.year_filter = QSpinBox()
        self.year_filter.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.year_filter.setRange(2000, 9999)
        self.year_filter.setValue(date.today().year)
        self.month_filter = MonthComboBox()
        self.month_filter.setObjectName("dashboardMonthFilter")
        self.month_filter.setMinimumWidth(120)
        self.month_filter.set_month(date.today().month)
        self.refresh_button = PrimaryButton("Atualizar")
        filters.addWidget(QLabel("Ano"))
        filters.addWidget(self.year_filter)
        filters.addWidget(QLabel("Mês"))
        filters.addWidget(self.month_filter)
        filters.addWidget(self.refresh_button)
        filters.addStretch()
        global_filter_panel = QWidget()
        global_filter_panel.setObjectName("dashboardFilterBar")
        global_filter_panel.setLayout(filters)

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(global_filter_panel)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("dashboardTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(False)
        self.tabs.setUsesScrollButtons(False)
        self._tab_pages = {}
        tab_layouts = {}
        for key, label in (("financial", "Financeiro"), ("boe", "BOE"),
                           ("targets", "Meta x Realizado")):
            page = QWidget()
            page.setObjectName(f"dashboard{key.title()}Tab")
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 12, 0, 0)
            page_layout.setSpacing(12)
            self._tab_pages[key] = page
            tab_layouts[key] = page_layout
            self.tabs.addTab(page, label)
        layout.addWidget(self.tabs)

        finance_filters = QHBoxLayout()
        self.finance_category_filter = QComboBox()
        self.finance_category_filter.addItem("Todas as categorias", None)
        for value in ("RECEITA_DIRETA", "RECEITA_INDIRETA", "ADMINISTRATIVO",
                      "DIRETORIA", "EVENTOS", "OPERACIONAL", "PESSOAL",
                      "INVESTIMENTO", "OUTROS"):
            self.finance_category_filter.addItem(value.replace("_", " ").title(), value)
        self.finance_type_filter = QComboBox()
        self.finance_type_filter.addItem("Todos os tipos", None)
        self.finance_type_filter.addItem("Receita", "RECEITA")
        self.finance_type_filter.addItem("Despesa", "DESPESA")
        finance_filters.addWidget(QLabel("Categoria"))
        finance_filters.addWidget(self.finance_category_filter)
        finance_filters.addWidget(QLabel("Tipo"))
        finance_filters.addWidget(self.finance_type_filter)
        finance_filters.addStretch()
        finance_filter_panel = QWidget()
        finance_filter_panel.setObjectName("dashboardFilterBar")
        finance_filter_panel.setLayout(finance_filters)
        tab_layouts["financial"].addWidget(finance_filter_panel)
        tab_layouts["financial"].addWidget(self._section("Financeiro"))
        finance_grid = QGridLayout()
        self.financial_cards = {}
        financial_titles = (
            ("opening_balance", "Saldo Inicial"),
            ("direct_revenue", "Receita Direta"),
            ("indirect_revenue", "Receita Indireta"),
            ("total_revenue", "Receita Total"),
            ("net_revenue", "Receita Líquida"),
            ("total_expense", "Despesa Total"),
            ("applications", "Aplicações"),
            ("redemptions", "Resgates"),
            ("bank_balance", "Saldo Bancário"),
            ("applied_balance", "Saldo Aplicado"),
        )
        financial_roles = {
            "opening_balance": "balance",
            "direct_revenue": "revenue",
            "indirect_revenue": "revenue",
            "total_revenue": "revenue",
            "net_revenue": "revenue",
            "total_expense": "expense",
            "applications": "movement",
            "redemptions": "movement",
            "bank_balance": "balance",
            "applied_balance": "balance",
        }
        for index, (key, label) in enumerate(financial_titles):
            card, value = self._card(label, role=financial_roles[key])
            self.financial_cards[key] = value
            finance_grid.addWidget(card, index // 4, index % 4)
        tab_layouts["financial"].addLayout(finance_grid)

        boe_filters = QHBoxLayout()
        self.boe_start_month = MonthComboBox()
        self.boe_start_month.set_month(1)
        self.boe_end_month = MonthComboBox()
        self.boe_end_month.set_month(date.today().month)
        self.boe_entity_filter = QComboBox()
        self.boe_entity_filter.addItem("Todas as entidades", None)
        boe_filters.addWidget(QLabel("Período"))
        boe_filters.addWidget(self.boe_start_month)
        boe_filters.addWidget(QLabel("até"))
        boe_filters.addWidget(self.boe_end_month)
        boe_filters.addWidget(QLabel("Entidade"))
        boe_filters.addWidget(self.boe_entity_filter)
        boe_filters.addStretch()
        boe_filter_panel = QWidget()
        boe_filter_panel.setObjectName("dashboardFilterBar")
        boe_filter_panel.setLayout(boe_filters)
        tab_layouts["boe"].addWidget(boe_filter_panel)
        tab_layouts["boe"].addWidget(self._section("BOE"))
        boe_cards = QHBoxLayout()
        self.boe_unit_value = self._add_card(boe_cards, "Valor Unitário", role="boe")
        self.boe_entities = self._add_card(boe_cards, "Entidades", "0", role="boe")
        self.boe_queries = self._add_card(boe_cards, "Consultas", "0", role="boe")
        self.boe_value = self._add_card(boe_cards, "Valor BOE", role="boe")
        tab_layouts["boe"].addLayout(boe_cards)
        self.boe_state = QLabel("Sem dados BOE para o período.")
        self.boe_state.setObjectName("pageDescription")
        tab_layouts["boe"].addWidget(self.boe_state)
        self.boe_table = QTableWidget(0, 4)
        self.boe_table.setHorizontalHeaderLabels(
            ["Entidade", "Consultas", "Valor Unitário", "Valor Total"]
        )
        self.boe_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.boe_table.horizontalHeader().setStretchLastSection(True)
        tab_layouts["boe"].addWidget(self.boe_table)

        tab_layouts["financial"].addWidget(self._section("Orçado x Realizado"))
        self.budget_table = QTableWidget(3, 3)
        self.budget_table.setObjectName("dashboardBudgetTable")
        self.budget_table.setHorizontalHeaderLabels(["Grupo", "Orçado", "Realizado"])
        self.budget_table.verticalHeader().setVisible(False)
        self.budget_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.budget_table.setMinimumHeight(155)
        self.budget_table.setMaximumHeight(190)
        self.budget_table.verticalHeader().setDefaultSectionSize(34)
        self.budget_table.horizontalHeader().setStretchLastSection(True)
        tab_layouts["financial"].addWidget(self.budget_table)

        target_filters = QHBoxLayout()
        self.target_start_month = MonthComboBox()
        self.target_start_month.set_month(1)
        self.target_end_month = MonthComboBox()
        self.target_end_month.set_month(date.today().month)
        self.target_entity_filter = QComboBox()
        self.target_entity_filter.addItem("Todas as entidades", None)
        self.target_indicator_filter = QComboBox()
        for label, value in (("Todas", "TODAS"), ("Consultas", "CONSULTAS"),
                             ("Registros", "REGISTROS")):
            self.target_indicator_filter.addItem(label, value)
        target_filters.addWidget(QLabel("Período"))
        target_filters.addWidget(self.target_start_month)
        target_filters.addWidget(QLabel("até"))
        target_filters.addWidget(self.target_end_month)
        target_filters.addWidget(QLabel("Entidade"))
        target_filters.addWidget(self.target_entity_filter)
        target_filters.addWidget(QLabel("Indicador"))
        target_filters.addWidget(self.target_indicator_filter)
        target_filters.addStretch()
        target_filter_panel = QWidget()
        target_filter_panel.setObjectName("dashboardFilterBar")
        target_filter_panel.setLayout(target_filters)
        tab_layouts["targets"].addWidget(target_filter_panel)
        tab_layouts["targets"].addWidget(self._section("Meta x Realizado"))
        targets = QHBoxLayout()
        query_card, self.query_target, self.query_actual, self.query_achievement = (
            self._target_card("Consultas")
        )
        registration_card, self.registration_target, self.registration_actual, (
            self.registration_achievement
        ) = self._target_card("Registros")
        targets.addWidget(query_card, 1)
        targets.addWidget(registration_card, 1)
        tab_layouts["targets"].addLayout(targets)
        target_kpis = QGridLayout()
        self.target_cards = {}
        for index, (key, label, initial) in enumerate((
            ("total_target", "Meta Total", "0,0000"),
            ("total_actual", "Total Realizado", "0,0000"),
            ("total_achievement", "% Atingido", "—"),
            ("associations", "Associados Totais", "0,0000"),
            ("association_variation", "% Variação Associações", "—"),
            ("average_ticket", "Ticket Médio", "—"),
            ("score", "Score", "—"), ("classification", "Classificação", "—"),
            ("award", "Premiação", "—"),
        )):
            role = "performance" if key in {"score", "classification", "award"} else "target"
            card, value = self._card(label, initial, role=role)
            self.target_cards[key] = value
            target_kpis.addWidget(card, index // 3, index % 3)
        tab_layouts["targets"].addLayout(target_kpis)
        self.target_state = QLabel("Sem dados de Meta x Realizado para o período.")
        self.target_state.setObjectName("pageDescription")
        tab_layouts["targets"].addWidget(self.target_state)

        self.finance_chart = self._chart_view("financeChart")
        self.budget_chart = self._chart_view("budgetChart")
        self.target_chart = self._chart_view("targetChart")
        self.balance_chart = self._chart_view("balanceChart")
        self.revenue_distribution_chart = self._chart_view("revenueDistributionChart")
        self.expense_distribution_chart = self._chart_view("expenseDistributionChart")
        self.investment_chart = self._chart_view("investmentChart")
        for chart in (self.finance_chart, self.balance_chart, self.budget_chart,
                      self.revenue_distribution_chart, self.expense_distribution_chart,
                      self.investment_chart):
            tab_layouts["financial"].addWidget(chart)
        self.boe_value_period_chart = self._chart_view("boeValuePeriodChart")
        self.boe_queries_period_chart = self._chart_view("boeQueriesPeriodChart")
        self.boe_value_entity_chart = self._chart_view("boeValueEntityChart")
        self.boe_queries_entity_chart = self._chart_view("boeQueriesEntityChart")
        for chart in (self.boe_value_period_chart, self.boe_queries_period_chart,
                      self.boe_value_entity_chart, self.boe_queries_entity_chart):
            tab_layouts["boe"].addWidget(chart)
        self.target_achievement_chart = self._chart_view("targetAchievementChart")
        self.target_evolution_chart = self._chart_view("targetEvolutionChart")
        self.target_ranking_chart = self._chart_view("targetRankingChart")
        for chart in (self.target_chart, self.target_achievement_chart,
                      self.target_evolution_chart, self.target_ranking_chart):
            tab_layouts["targets"].addWidget(chart)

        self.status = QLabel("Dashboard pronto.")
        self.status.setObjectName("operationStatus")
        layout.addWidget(self.status)
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def set_allowed_areas(self, areas: set[str]) -> None:
        for key, page in self._tab_pages.items():
            index = self.tabs.indexOf(page)
            if index >= 0:
                self.tabs.setTabVisible(index, key in areas)

    def dashboard_filters(self) -> tuple[QComboBox, ...]:
        return (self.finance_category_filter, self.finance_type_filter,
                self.boe_start_month, self.boe_end_month, self.boe_entity_filter,
                self.target_start_month, self.target_end_month, self.target_entity_filter,
                self.target_indicator_filter)

    def selected_dashboard_filters(self) -> dict:
        return {
            "category": self.finance_category_filter.currentData(),
            "entry_type": self.finance_type_filter.currentData(),
            "boe_entity_id": self.boe_entity_filter.currentData(),
            "boe_start_month": self.boe_start_month.month(),
            "boe_end_month": self.boe_end_month.month(),
            "target_entity_id": self.target_entity_filter.currentData(),
            "target_start_month": self.target_start_month.month(),
            "target_end_month": self.target_end_month.month(),
            "indicator": self.target_indicator_filter.currentData() or "TODAS",
        }

    def show_dashboard_data(self, data: dict) -> None:
        if "financial" in data:
            self._show_financial_data(data["financial"])
        if "boe" in data:
            self._show_boe_data(data["boe"])
        if "targets" in data:
            self._show_target_data(data["targets"])

    def _show_financial_data(self, data: dict) -> None:
        for key, label in self.financial_cards.items():
            label.setText(self.currency(data["kpis"].get(key)))
        budget = data["budget"]
        rows = (("Receitas", budget["budgeted_revenue"], budget["actual_revenue"]),
                ("Despesas", budget["budgeted_expense"], budget["actual_expense"]),
                ("Resultado", self.decimal(budget["result"]) -
                 self.decimal(budget["variance"]), budget["result"]))
        for index, row in enumerate(rows):
            for column, value in enumerate((row[0], self.currency(row[1]),
                                            self.currency(row[2]))):
                self.budget_table.setItem(index, column, QTableWidgetItem(value))
        monthly = data.get("monthly", [])
        categories = [self.month_label(row["month"]) for row in monthly]
        self.finance_chart.setChart(self._bar_chart(
            "Receita x Despesa por mês", categories,
            [("Receita", [row["revenue"] for row in monthly]),
             ("Despesa", [row["expense"] for row in monthly])]))
        self.balance_chart.setChart(self._bar_chart(
            "Evolução do Saldo Bancário", categories,
            [("Saldo", [row["bank_balance"] or 0 for row in monthly])]))
        self.budget_chart.setChart(self._bar_chart(
            "Orçado x Realizado mensal", categories,
            [("Orçado", [abs(self.decimal(row["budgeted_revenue"]) -
                              self.decimal(row["budgeted_expense"]))
                          for row in monthly]),
             ("Realizado", [abs(self.decimal(row["actual_revenue"]) -
                                 self.decimal(row["actual_expense"]))
                             for row in monthly])]))
        revenue = data.get("revenue_distribution", {})
        expense = data.get("expense_distribution", {})
        self.revenue_distribution_chart.setChart(self._distribution_chart(
            "Distribuição das Receitas", revenue, "Receita"))
        self.expense_distribution_chart.setChart(self._distribution_chart(
            "Distribuição das Despesas", expense, "Despesa"))
        self.investment_chart.setChart(self._bar_chart(
            "Aplicação x Resgate", categories,
            [("Aplicação", [row["applications"] for row in monthly]),
             ("Resgate", [row["redemptions"] for row in monthly])]))

    def _show_boe_data(self, data: dict) -> None:
        self._sync_entities(self.boe_entity_filter, data.get("filters", {}).get("entities", []))
        self.boe_unit_value.setText(self.currency(data.get("unit_value")))
        self.boe_entities.setText(self.integer(data["entity_count"]))
        self.boe_queries.setText(self.integer(data["queries"]))
        self.boe_value.setText(self.currency(data["total_value"]))
        rows = data.get("entities", [])
        self.boe_state.setVisible(not rows)
        self.boe_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = (f"{row['code']} — {row['name']}", self.integer(row["queries"]),
                      self.currency(row["unit_value"]), self.currency(row["total_value"]))
            for column, value in enumerate(values):
                self.boe_table.setItem(row_index, column, QTableWidgetItem(value))
        monthly = data.get("monthly", [])
        months = [self.month_label(row["month"]) for row in monthly]
        self.boe_value_period_chart.setChart(self._bar_chart(
            "Valor Total por período", months,
            [("Valor", [row["total_value"] for row in monthly])]))
        self.boe_queries_period_chart.setChart(self._bar_chart(
            "Consultas por período", months,
            [("Consultas", [row["queries"] for row in monthly])]))
        entity_labels = [str(row["code"]) for row in rows] or ["Sem dados"]
        self.boe_value_entity_chart.setChart(self._bar_chart(
            "Valor Total por entidade", entity_labels,
            [("Valor", [row["total_value"] for row in rows] or [0])]))
        self.boe_queries_entity_chart.setChart(self._bar_chart(
            "Consultas por entidade", entity_labels,
            [("Consultas", [row["queries"] for row in rows] or [0])]))

    def _show_target_data(self, data: dict) -> None:
        self._sync_entities(self.target_entity_filter,
                            data.get("filters", {}).get("entities", []))
        queries, registrations = data["queries"], data["registrations"]
        total = data.get("total", {
            "target": self.decimal(queries["target"]) + self.decimal(registrations["target"]),
            "actual": self.decimal(queries["actual"]) + self.decimal(registrations["actual"]),
            "achievement_percentage": None,
        })
        self._show_target_values(queries, self.query_target, self.query_actual,
                                 self.query_achievement)
        self._show_target_values(registrations, self.registration_target,
                                 self.registration_actual, self.registration_achievement)
        self.target_cards["total_target"].setText(self.number(total["target"]))
        self.target_cards["total_actual"].setText(self.number(total["actual"]))
        self.target_cards["total_achievement"].setText(
            self.percentage(total["achievement_percentage"]))
        self.target_cards["associations"].setText(self.number(data.get("associations", 0)))
        self.target_cards["association_variation"].setText(
            self.percentage(data.get("association_variation_percentage")))
        self.target_cards["average_ticket"].setText(self.currency(data.get("average_ticket")))
        ranking = data.get("ranking", [])
        top = ranking[0] if ranking else None
        getter = (lambda key, default=None: top.get(key, default)) if isinstance(top, dict) else (
            lambda key, default=None: getattr(top, key, default))
        self.target_cards["score"].setText("—" if top is None else str(getter("score", "—")))
        self.target_cards["classification"].setText(
            "—" if top is None else ("Classificado" if getter("classified", False) else "Não classificado"))
        self.target_cards["award"].setText(
            "—" if top is None else self.currency(getter("award")))
        self.target_state.setVisible(not (queries["target"] or queries["actual"] or
                                          registrations["target"] or registrations["actual"]))
        monthly = data.get("monthly", [])
        months = [self.month_label(row["month"]) for row in monthly]
        indicator = data.get("indicator", "TODAS")
        if indicator == "CONSULTAS":
            target_values = [row["queries_target"] for row in monthly]
            actual_values = [row["queries_actual"] for row in monthly]
        elif indicator == "REGISTROS":
            target_values = [row["registrations_target"] for row in monthly]
            actual_values = [row["registrations_actual"] for row in monthly]
        else:
            target_values = [row["queries_target"] + row["registrations_target"]
                             for row in monthly]
            actual_values = [row["queries_actual"] + row["registrations_actual"]
                             for row in monthly]
        self.target_chart.setChart(self._bar_chart(
            "Meta x Realizado por período", months,
            [("Meta", target_values), ("Realizado", actual_values)]))
        percentages = [0 if target == 0 else actual / target * 100
                       for target, actual in zip(target_values, actual_values)]
        self.target_achievement_chart.setChart(self._bar_chart(
            "% Atingimento", months, [("Atingimento %", percentages)]))
        self.target_evolution_chart.setChart(self._bar_chart(
            "Evolução mensal", months, [("Realizado", actual_values)]))
        ranking_labels = [str(getter("entity_code", ""))] if top is not None else ["Sem dados"]
        ranking_values = [getter("score", 0)] if top is not None else [0]
        self.target_ranking_chart.setChart(self._bar_chart(
            "Ranking / Classificação", ranking_labels, [("Score", ranking_values)]))

    @staticmethod
    def _sync_entities(combo: QComboBox, entities: list[dict]) -> None:
        selected = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem("Todas as entidades", None)
        for entity in entities:
            combo.addItem(f"{entity['code']} — {entity['name']}", entity["id"])
        index = combo.findData(selected)
        combo.setCurrentIndex(max(index, 0))
        combo.blockSignals(False)

    def _show_target_values(self, value: dict, target: QLabel, actual: QLabel,
                            achievement: QLabel) -> None:
        target.setText(self.number(value["target"]))
        actual.setText(self.number(value["actual"]))
        achievement.setText(self.percentage(value["achievement_percentage"]))

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    @staticmethod
    def _card(
        title: str,
        initial: str = "R$ 0,00",
        *,
        role: str = "neutral",
    ) -> tuple[QWidget, QLabel]:
        card = QWidget()
        card.setObjectName("summaryCard")
        card.setProperty("cardRole", role)
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
    def _add_card(
        cls,
        layout: QHBoxLayout,
        title: str,
        initial: str = "R$ 0,00",
        *,
        role: str = "neutral",
    ) -> QLabel:
        card, value = cls._card(title, initial, role=role)
        layout.addWidget(card, 1)
        return value

    @staticmethod
    def _target_card(title: str) -> tuple[QWidget, QLabel, QLabel, QLabel]:
        card = QWidget()
        card.setObjectName("summaryCard")
        card.setProperty("cardRole", "target")
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
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(False)
        chart.setTitleBrush(QColor("#172554"))
        chart.setTitleFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        chart.legend().setFont(QFont("Segoe UI", 8))
        chart.legend().setLabelColor(QColor("#475569"))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        view = DashboardChartView(chart)
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
            label.setText(self.currency(getattr(financial, field, None)))
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
        budget_labels = ("Receitas", "Despesas", "Resultado")
        for row, values in enumerate(budget_rows):
            self.budget_table.setItem(row, 0, QTableWidgetItem(budget_labels[row]))
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

    @classmethod
    def _bar_chart(cls, title: str, categories: list[str], series_data) -> QChart:
        series = QBarSeries()
        series.setLabelsVisible(False)
        series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsOutsideEnd)
        maximum = 0.0
        minimum = 0.0
        for index, (name, values) in enumerate(series_data):
            bar_set = QBarSet(name)
            color = cls.CHART_COLORS.get(
                name, cls.CHART_FALLBACK[index % len(cls.CHART_FALLBACK)]
            )
            bar_set.setColor(QColor(color))
            bar_set.setBorderColor(QColor(color))
            numeric = [float(value) for value in values]
            bar_set.append(numeric)
            if numeric:
                maximum = max(maximum, *numeric)
                minimum = min(minimum, *numeric)
            series.append(bar_set)
        chart = QChart()
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(False)
        chart.addSeries(series)
        chart.setTitleBrush(QColor("#172554"))
        chart.setTitleFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        chart.setTitle(title)
        chart.legend().setVisible(True)
        chart.legend().setFont(QFont("Segoe UI", 8))
        chart.legend().setLabelColor(QColor("#475569"))
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        axis_x = QBarCategoryAxis()
        axis_x.setLabelsFont(QFont("Segoe UI", 8))
        axis_x.setLabelsColor(QColor("#475569"))
        axis_x.setGridLineVisible(False)
        axis_x.append(categories)
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)
        axis_y = QValueAxis()
        axis_y.setLabelsFont(QFont("Segoe UI", 8))
        axis_y.setLabelsColor(QColor("#64748B"))
        axis_y.setGridLineColor(QColor("#E2E8F0"))
        axis_y.setRange(0, maximum * 1.28 if maximum > 0 else 1)
        axis_y.setLabelFormat("%.1f")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)
        percentage_chart = "%" in title or any("%" in name for name, _ in series_data)
        chart._dashboard_labels = {
            "categories": list(categories),
            "series_values": [[float(v) for v in values] for _, values in series_data],
            "label_kind": "percentage" if percentage_chart else "number",
        }
        if percentage_chart:
            for bar_set, (name, _) in zip(series.barSets(), series_data):
                bar_set.setLabel(name)
        return chart

    @classmethod
    def _distribution_chart(cls, title: str, distribution: dict, series_name: str) -> QChart:
        if not distribution:
            return cls._bar_chart(title, ["Sem dados"], [(series_name, [0])])
        values = list(distribution.values())
        total = sum((cls.decimal(value) for value in values), Decimal("0"))
        categories = []
        for label, value in distribution.items():
            numeric = cls.decimal(value)
            percentage = Decimal("0") if total == 0 else numeric / total * Decimal("100")
            categories.append(f"{label} ({percentage:.1f}%)".replace(".", ","))
        return cls._bar_chart(title, categories, [(series_name, values)])

    @staticmethod
    def month_label(value: int) -> str:
        labels = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
                  "Jul", "Ago", "Set", "Out", "Nov", "Dez")
        try:
            month = int(value)
        except (TypeError, ValueError):
            return str(value)
        return labels[month - 1] if 1 <= month <= 12 else str(value)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    @staticmethod
    def currency(value: Decimal | None) -> str:
        if value is None:
            return "—"
        value = Decimal(str(value))
        formatted = f"{value:,.2f}"
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def number(value: Decimal) -> str:
        value = Decimal(str(value))
        formatted = f"{value:,.4f}"
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def integer(value: int) -> str:
        return f"{value:,}".replace(",", ".")

    @staticmethod
    def percentage(value: Decimal | None) -> str:
        return ("—" if value is None else
                f"{Decimal(str(value)):.4f}%".replace(".", ","))

    @staticmethod
    def decimal(value) -> Decimal:
        return Decimal(str(value or 0))
