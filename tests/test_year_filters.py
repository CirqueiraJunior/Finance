from datetime import date
from decimal import Decimal

from app.gui.pages.administracao import RankingParametersWidget
from app.gui.pages.financeiro import FinanceiroPage
from app.gui.pages.metas import MetasPage
from app.gui.pages.orcamento import OrcamentoPage
from app.gui.pages.relatorios import RelatoriosPage
from app.widgets.wheel_guard import WheelBlockedComboBox
from app.widgets.year_combo import populate_year_combo
from app.models.association_entry import AssociationEntry
from app.models.budget_entry import BudgetEntry
from app.models.entity import Entity
from app.models.ranking_parameter import RankingParameter
from app.models.target_entry import TargetEntry
from app.repositories.association_repository import AssociationRepository
from app.repositories.budget_repository import BudgetRepository
from app.repositories.ranking_parameter_repository import RankingParameterRepository
from app.repositories.target_repository import TargetRepository
from app.services.ranking_service import RankingService
from app.services.target_service import TargetService
from app.services.report_service import ReportService
from app.repositories.entity_repository import EntityRepository


def test_year_combo_orders_deduplicates_and_uses_integer_item_data(qtbot):
    combo = WheelBlockedComboBox()
    qtbot.addWidget(combo)

    selected = populate_year_combo(combo, [2025, 2026, 2025])

    assert [combo.itemData(index) for index in range(combo.count())] == [2025, 2026]
    assert isinstance(combo.currentData(), int)
    assert selected == (date.today().year if date.today().year in {2025, 2026} else 2026)


def test_year_combo_preserves_selection_and_empty_state_is_safe(qtbot):
    combo = WheelBlockedComboBox()
    qtbot.addWidget(combo)
    populate_year_combo(combo, [2024, 2025])
    combo.setCurrentIndex(combo.findData(2024))

    assert populate_year_combo(combo, [2024, 2025, 2026]) == 2024
    assert combo.currentData() == 2024
    assert populate_year_combo(combo, []) is None
    assert combo.count() == 0
    assert not combo.isEnabled()


def test_query_year_filters_use_wheel_blocked_combo(qtbot):
    pages = [FinanceiroPage(), OrcamentoPage(), MetasPage(), RelatoriosPage()]
    for page in pages:
        qtbot.addWidget(page)
        assert isinstance(page.year_filter, WheelBlockedComboBox)
    assert isinstance(pages[2].ranking_year, WheelBlockedComboBox)


def test_administration_distinguishes_legacy_and_parameterized_years(qtbot):
    widget = RankingParametersWidget()
    qtbot.addWidget(widget)
    widget.show()
    widget.set_configurations([
        {"year": 2026, "strategy": "parameterized", "editable": True},
        {"year": 2025, "strategy": "legacy_2025", "editable": False},
    ])

    assert [widget.year.itemData(index) for index in range(widget.year.count())] == [2025, 2026]
    widget.year.setCurrentIndex(widget.year.findData(2025))
    widget.show_selected_strategy()
    assert widget.legacy_strategy.isVisible()
    assert not widget.save_button.isVisible()

    widget.year.setCurrentIndex(widget.year.findData(2026))
    widget.show_selected_strategy()
    assert widget.parameter_form.isVisible()
    assert widget.save_button.isVisible()


def test_domain_year_sources_use_only_persisted_relevant_data(db_session):
    entity = Entity(codigo_entidade=7501, nome="Entidade")
    db_session.add(entity)
    db_session.flush()
    db_session.add_all([
        BudgetEntry(periodo_ano=2026, periodo_mes=1, tipo="DESPESA",
                    categoria="ADMINISTRATIVO", valor_orcado=Decimal("1")),
        TargetEntry(entity_id=entity.id, periodo_ano=2025, periodo_mes=1,
                    indicador="CONSULTAS", valor_meta=Decimal("1"),
                    valor_realizado=Decimal("1")),
        TargetEntry(entity_id=entity.id, periodo_ano=2026, periodo_mes=1,
                    indicador="CONSULTAS", valor_meta=Decimal("1"),
                    valor_realizado=Decimal("1")),
        AssociationEntry(entity_id=entity.id, periodo_ano=2026, periodo_mes=1,
                         valor_captacao=Decimal("1"), valor_execucao=Decimal("1"),
                         valor_cancelamento=Decimal("0")),
        RankingParameter.defaults_2026(),
    ])
    db_session.commit()

    assert BudgetRepository(db_session).available_years() == [2026]
    target_service = TargetService(
        TargetRepository(db_session), EntityRepository(db_session)
    )
    assert target_service.available_years() == [2025, 2026]
    ranking = RankingService(
        TargetRepository(db_session), AssociationRepository(db_session),
        RankingParameterRepository(db_session),
    )
    assert ranking.available_years() == [2025, 2026]


def test_report_years_cover_only_its_financial_boe_and_budget_domains():
    class Years:
        def __init__(self, values): self.values = values
        def available_years(self): return self.values

    class BOE:
        def list_imports(self):
            return [type("Import", (), {"periodo_ano": 2025, "status": "imported"})()]

    service = ReportService(Years([2024]), BOE(), Years([2026]))
    assert service.available_years() == [2024, 2025, 2026]
