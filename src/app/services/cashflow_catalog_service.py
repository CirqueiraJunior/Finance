from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.models.cashflow_catalog_entry import CashflowCatalogEntry
from app.models.cashflow_entry import EXPENSE_CATEGORIES, CashflowCategory
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository


@dataclass(frozen=True, slots=True)
class CashflowCatalogOption:
    description: str
    category: str
    movement_type: str


class CashflowCatalogService:
    def __init__(self, repository: CashflowCatalogRepository) -> None:
        self.repository = repository

    def list_options(
        self, *, include_balance: bool = False
    ) -> tuple[CashflowCatalogOption, ...]:
        options = tuple(
            CashflowCatalogOption(item.descricao, item.categoria, item.tipo)
            for item in self.repository.list_active()
        )
        if include_balance:
            return options
        return tuple(
            option for option in options
            if option.movement_type != "SALDO"
            and option.category != "RECEITA_DIRETA"
        )

    def list_descriptions(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(option.description for option in self.list_options()))

    def list_budget_options(self) -> tuple[CashflowCatalogOption, ...]:
        """Opções ativas coerentes com o domínio Receita/Despesa do orçamento."""
        return tuple(
            CashflowCatalogOption(item.descricao, item.categoria, item.tipo)
            for item in self.repository.list_active()
            if item.tipo in {"RECEITA", "DESPESA"}
        )

    def list_entries(self) -> list[CashflowCatalogEntry]:
        return self.repository.list_all()

    def create_entry(
        self, *, description: str, category: str, movement_type: str,
        active: bool = True,
    ) -> CashflowCatalogEntry:
        description, category, movement_type = self._validate(
            description, category, movement_type
        )
        entry = CashflowCatalogEntry(
            descricao=description,
            categoria=category,
            tipo=movement_type,
            ativa=bool(active),
        )
        try:
            self.repository.add(entry)
            self.repository.session.commit()
        except IntegrityError as error:
            self.repository.session.rollback()
            raise ValueError("Essa combinação já existe no catálogo.") from error
        return entry

    def update_entry(
        self, entry_id: int, *, description: str, category: str,
        movement_type: str, active: bool,
    ) -> CashflowCatalogEntry:
        entry = self.repository.get_by_id(entry_id)
        if entry is None:
            raise ValueError("Item do catálogo não encontrado.")
        description, category, movement_type = self._validate(
            description, category, movement_type
        )
        entry.descricao = description
        entry.categoria = category
        entry.tipo = movement_type
        entry.ativa = bool(active)
        try:
            self.repository.session.commit()
        except IntegrityError as error:
            self.repository.session.rollback()
            raise ValueError("Essa combinação já existe no catálogo.") from error
        return entry

    @staticmethod
    def _validate(description: str, category: str | None, movement_type: str | None):
        description = description.strip()
        category = (category or "").strip().upper()
        movement_type = (movement_type or "").strip().upper()
        if not description:
            raise ValueError("A descrição é obrigatória.")
        valid_expenses = {item.value for item in EXPENSE_CATEGORIES}
        coherent = (
            (movement_type == "RECEITA" and category in {
                CashflowCategory.DIRECT_REVENUE.value,
                CashflowCategory.INDIRECT_REVENUE.value,
            })
            or (movement_type == "DESPESA" and category in valid_expenses)
            or (movement_type == "APLICACAO" and category == "INVESTIMENTO")
            or (movement_type == "RESGATE" and category == "RESGATE")
            or (movement_type == "SALDO" and category == "SALDO_APLICADO")
        )
        if not coherent:
            raise ValueError("Combinação incoerente entre Categoria e Tipo.")
        return description, category, movement_type

    def options_for_description(self, description: str) -> tuple[CashflowCatalogOption, ...]:
        return tuple(
            CashflowCatalogOption(item.descricao, item.categoria, item.tipo)
            for item in self.repository.list_by_description(description)
        )
