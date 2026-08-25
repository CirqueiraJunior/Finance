class EntityDomainError(Exception):
    """Base exception for Entity domain validation errors."""


class InvalidEntityCodeError(EntityDomainError):
    """Raised when an entity code is reserved or otherwise invalid."""


class EntityCodeAlreadyExistsError(EntityDomainError):
    """Raised when an entity code is already registered."""


class EntityAliasAlreadyExistsError(EntityDomainError):
    """Raised when an alias is already registered for the same entity."""


class BOEDomainError(Exception):
    """Base exception for BOE import errors."""


class BOEValidationError(BOEDomainError):
    """Raised when an import is requested with blocking validation issues."""

    def __init__(self, result: object) -> None:
        super().__init__("O arquivo BOE possui erros impeditivos e não pode ser importado.")
        self.result = result


class BOEDuplicateImportError(BOEDomainError):
    """Raised when a BOE file or reference period was already imported."""


class CashflowDomainError(Exception):
    """Base exception for cashflow validation and consistency errors."""


class CashflowValidationError(CashflowDomainError):
    """Raised when cashflow input violates an approved Sprint 04 rule."""


class CashflowDuplicateBOEError(CashflowDomainError):
    """Raised when a BOE already has a direct revenue entry."""


class BudgetDomainError(Exception):
    """Base exception for budget validation errors."""


class BudgetValidationError(BudgetDomainError):
    """Raised when budget input is invalid."""


class BudgetDuplicateError(BudgetDomainError):
    """Raised when a period/type/category budget already exists."""


class InvestmentDomainError(Exception):
    """Base exception for investment movement errors."""


class InvestmentValidationError(InvestmentDomainError):
    """Raised when investment movement input is invalid."""


class InvestmentBalanceError(InvestmentDomainError):
    """Raised when a redemption exceeds the balance available on its date."""


class TargetDomainError(Exception):
    """Base exception for operational target errors."""


class TargetValidationError(TargetDomainError):
    """Raised when a Meta x Realizado input is invalid."""


class TargetDuplicateError(TargetDomainError):
    """Raised when an Entity already has a target for the period/indicator."""
