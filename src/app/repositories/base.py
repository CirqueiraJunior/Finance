from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    """Shared dependency boundary; no CRUD is implemented in Sprint 01."""

    def __init__(self, session: Session) -> None:
        self.session = session

