from dataclasses import dataclass

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

    def options_for_description(self, description: str) -> tuple[CashflowCatalogOption, ...]:
        return tuple(
            CashflowCatalogOption(item.descricao, item.categoria, item.tipo)
            for item in self.repository.list_by_description(description)
        )
