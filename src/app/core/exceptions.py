class EntityDomainError(Exception):
    """Base exception for Entity domain validation errors."""


class InvalidEntityCodeError(EntityDomainError):
    """Raised when an entity code is reserved or otherwise invalid."""


class EntityCodeAlreadyExistsError(EntityDomainError):
    """Raised when an entity code is already registered."""


class EntityAliasAlreadyExistsError(EntityDomainError):
    """Raised when an alias is already registered for the same entity."""

