from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.importers.historical_parser import BudgetImportData
from app.models.budget_entry import BudgetEntry
from app.repositories.budget_repository import BudgetRepository
from app.services.budget_import_service import BudgetImportService


class Workbook:
    def __init__(self):
        self.amounts = ("100", "200", "300")

    def parse(self, path):
        rows = [
            BudgetImportData(
                number, 2025, 1, "DESPESA",
                "ADMINISTRATIVO", Decimal(value),
                "Impostos e Taxas",
            )
            for number, value in enumerate(self.amounts, 3)
        ]
        rows.extend([
            BudgetImportData(
                10, 2025, 1, "DESPESA",
                "ADMINISTRATIVO", Decimal("300"),
                "IPVA",
            ),
            BudgetImportData(
                11, 2025, 1, "DESPESA",
                "ADMINISTRATIVO", Decimal("0"),
                "Despesa Zerada",
            ),
        ])
        return SimpleNamespace(
            data=tuple(rows), errors=(), warnings=(),
            metadata=SimpleNamespace(
                detected_type="ORCAMENTO",
                file_path=Path(path),
                year=2025,
                sheets=("Orcado",),
            ),
        )


def test_detailed_budget_import_and_reimport():
    engine = create_engine("sqlite:///:memory:")
    BudgetEntry.__table__.create(engine)

    try:
        with Session(engine) as session:
            book = Workbook()
            repository = BudgetRepository(session)
            service = BudgetImportService(repository, book)
            first = service.validate("orcado.xlsx")
            assert first.can_import, first.errors
            assert len(first.preview) == 2
            assert first.new_count == 2
            assert first.total == Decimal("900")
            assert any("zeradas" in w for w in first.warnings)

            service.stage_import("orcado.xlsx")
            session.commit()

            again = service.validate("orcado.xlsx")
            assert again.unchanged_count == 2
            assert again.changed_count == 0
            assert again.total == Decimal("900")

            book.amounts = ("100", "200", "250")
            changed = service.validate("orcado.xlsx")
            assert changed.changed_count == 1
            assert changed.unchanged_count == 1
            assert changed.total == Decimal("850")
            assert changed.snapshot_hash != again.snapshot_hash

            row = next(
                p for p in changed.preview
                if p.source_label == "Impostos e Taxas"
            )
            assert row.previous_value == Decimal("600")
            assert row.value == Decimal("550")
            assert row.difference == Decimal("-50")

            service.stage_import("orcado.xlsx")
            session.commit()

            saved = repository.list_by_period(2025, 1)
            assert len(saved) == 2
            values = {r.descricao: r.valor_orcado for r in saved}
            assert values == {
                "Impostos e Taxas": Decimal("550"),
                "IPVA": Decimal("300"),
            }
            assert sum(values.values()) == Decimal("850")
    finally:
        engine.dispose()
