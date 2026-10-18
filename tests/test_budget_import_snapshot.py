from decimal import Decimal
from types import SimpleNamespace as NS

from app.services.budget_import_snapshot import budget_snapshot


def sample(value="100", description="Descrição", existing=True):
    row = NS(year=2026, month=1, entry_type="DESPESA",
             category="PESSOAL", value=Decimal(value), source_label=description)
    key = (2026, 1, "DESPESA", "PESSOAL")
    old = NS(id=7, valor_orcado=Decimal("95.0000"),
             descricao="Anterior", observacao="origem") if existing else None
    return NS(preview=(row,)), {key: old} if old else {}


def test_deterministic():
    v, e = sample()
    assert budget_snapshot(v, e) == budget_snapshot(v, e)


def test_incoming_change_changes_hash():
    v, e = sample()
    different, _ = sample(value="101")
    assert budget_snapshot(v, e) != budget_snapshot(different, e)


def test_existing_value_change_changes_hash():
    v, e = sample()
    previous = budget_snapshot(v, e)
    next(iter(e.values())).valor_orcado = Decimal("96")
    assert previous != budget_snapshot(v, e)


def test_existing_description_change_changes_hash():
    v, e = sample()
    previous = budget_snapshot(v, e)
    next(iter(e.values())).descricao = "Nova descrição"
    assert previous != budget_snapshot(v, e)


def test_existing_notes_change_changes_hash():
    v, e = sample()
    previous = budget_snapshot(v, e)
    next(iter(e.values())).observacao = "Atualização concorrente"
    assert previous != budget_snapshot(v, e)


def test_missing_vs_existing():
    v, e = sample(existing=False)
    missing = budget_snapshot(v, e)
    _, found = sample(existing=True)
    assert missing != budget_snapshot(v, found)


def test_import_order_does_not_change_hash():
    a, e = sample()
    b = NS(year=2026, month=2, entry_type="DESPESA",
           category="EVENTOS", value=Decimal("30"), source_label="Eventos")
    first = NS(preview=(a.preview[0], b))
    second = NS(preview=(b, a.preview[0]))
    assert budget_snapshot(first, e) == budget_snapshot(second, e)


def test_decimal_formatting_is_canonical():
    a, e = sample(value="100")
    b, _ = sample(value="100.0000")
    assert budget_snapshot(a, e) == budget_snapshot(b, e)
