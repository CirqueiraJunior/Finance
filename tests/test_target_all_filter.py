from decimal import Decimal
from types import SimpleNamespace
from typing import NamedTuple

from app.gui.controllers.target_controller import TargetController


class Comparison(NamedTuple):
    entity_code: int
    target: Decimal
    actual: Decimal


class Summary(NamedTuple):
    entity_count: int
    target_total: Decimal
    actual_total: Decimal
    difference_total: Decimal
    achievement: Decimal | None


class Result(NamedTuple):
    comparisons: tuple[Comparison, ...]
    summary: Summary


class FakeTargetService:
    def __init__(self):
        self.calls = []

    def get_target_vs_actual(self, year, month, indicator, entity_id):
        self.calls.append((year, month, indicator, entity_id))

        if indicator == "CONSULTAS":
            comparisons = (
                Comparison(1, Decimal("10"), Decimal("8")),
            )
        elif indicator == "REGISTROS":
            comparisons = (
                Comparison(1, Decimal("20"), Decimal("25")),
                Comparison(2, Decimal("5"), Decimal("5")),
            )
        else:
            raise AssertionError(f"Unexpected indicator: {indicator}")

        zero = Decimal("0")
        target_total = sum((item.target for item in comparisons), zero)
        actual_total = sum((item.actual for item in comparisons), zero)

        return Result(
            comparisons,
            Summary(
                len({item.entity_code for item in comparisons}),
                target_total,
                actual_total,
                actual_total - target_total,
                None,
            ),
        )


def test_all_indicators_combines_queries_and_registrations():
    service = FakeTargetService()
    controller = SimpleNamespace(service=service)

    result = TargetController._get_target_vs_actual(
        controller,
        2026,
        10,
        "TODAS",
        None,
    )

    assert [call[2] for call in service.calls] == [
        "CONSULTAS",
        "REGISTROS",
    ]

    assert len(result.comparisons) == 3
    assert result.summary.entity_count == 2
    assert result.summary.target_total == Decimal("35")
    assert result.summary.actual_total == Decimal("38")
    assert result.summary.difference_total == Decimal("3")
    assert result.summary.achievement == Decimal("108.5714")


def test_single_indicator_delegates_directly():
    service = FakeTargetService()
    controller = SimpleNamespace(service=service)

    result = TargetController._get_target_vs_actual(
        controller,
        2026,
        10,
        "CONSULTAS",
        (1,),
    )

    assert len(service.calls) == 1
    assert service.calls[0] == (
        2026,
        10,
        "CONSULTAS",
        (1,),
    )
    assert len(result.comparisons) == 1
