from dataclasses import fields

from app.services.budget_service import BudgetComparison, BudgetDetail


def test_detail_contract_preserves_existing_comparisons():
    comparison = BudgetComparison(
        "DESPESA", "Administrativo", "ADMINISTRATIVO",
        100, 50, 50, 50,
    )
    assert comparison.details == ()
    assert "details" in {field.name for field in fields(comparison)}


def test_detail_distinguishes_unmatched_values():
    budgeted = BudgetDetail("IPVA", 300, 200, 100)
    unmatched = BudgetDetail(
        "Outra despesa", 0, 50, -50, True,
    )
    assert budgeted.unmatched is False
    assert unmatched.unmatched is True
    assert budgeted.actual + unmatched.actual == 250
