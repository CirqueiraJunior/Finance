from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finance_server.models import AuditLog, User, UserRole
from finance_server.security import hash_password


class InitialSetupUnavailableError(RuntimeError):
    """Raised when a database is no longer eligible for initial setup."""


@dataclass(frozen=True, slots=True)
class InitialAdministratorData:
    nome: str
    email: str
    username: str
    password: str


def users_exist(db: Session) -> bool:
    return bool(db.scalar(select(func.count(User.id))))


def _lock_initial_setup(db: Session) -> None:
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        # BEGIN IMMEDIATE serializes the check-and-create operation between
        # independent Finance processes without requiring a schema change.
        db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    elif dialect == "postgresql":
        # Transaction-scoped and installation-independent; it cannot remain
        # held after commit or rollback.
        db.execute(text("SELECT pg_advisory_xact_lock(1179799633)"))


def create_initial_administrator(
    db: Session,
    data: InitialAdministratorData,
    *,
    origin: str,
) -> User:
    """Create the only first user; caller owns commit/rollback."""

    _lock_initial_setup(db)
    if users_exist(db):
        raise InitialSetupUnavailableError(
            "A configuração inicial não está mais disponível."
        )

    target = User(
        nome=data.nome.strip(),
        email=data.email.strip().casefold(),
        username=data.username.strip().casefold(),
        password_hash=hash_password(data.password),
        perfil=UserRole.ADMINISTRATOR.value,
        ativo=True,
        must_change_password=False,
        personal_recovery_key_pending=True,
    )
    db.add(target)
    try:
        db.flush()
    except IntegrityError as error:
        raise InitialSetupUnavailableError(
            "A configuração inicial não está mais disponível."
        ) from error

    db.add(
        AuditLog(
            user_id=target.id,
            action="INITIAL_ADMINISTRATOR_CREATED",
            entity_type="User",
            entity_id=str(target.id),
            details={
                "perfil": target.perfil,
                "username": target.username,
                "email": target.email,
            },
            origin=origin,
        )
    )
    return target
