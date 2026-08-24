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
