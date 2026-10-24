"""Fail-closed database identity checks for the homologation API."""

from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_interface
import os

from sqlalchemy import text
from sqlalchemy.engine import Engine, URL, make_url


EXPECTED_HOST = "127.0.0.1"
EXPECTED_PORT = 5432
EXPECTED_DATABASE = "ja_finance_homologacao"
EXPECTED_USER = "ja_finance_hml"
EXPECTED_SSLMODE = "disable"


class HomologationTargetError(RuntimeError):
    """Raised before serving requests when the homologation target diverges."""


@dataclass(frozen=True, slots=True)
class PostgreSQLIdentity:
    database: str
    username: str
    server_address: str
    server_port: int


def _fail(detail: str) -> None:
    raise HomologationTargetError(
        f"Destino PostgreSQL de homologacao bloqueado: {detail}."
    )


def validate_homologation_url(database_url: str | URL) -> URL:
    """Validate only non-secret connection coordinates."""
    try:
        url = make_url(database_url) if isinstance(database_url, str) else database_url
    except Exception:
        _fail("URL de conexao invalida")

    if url.get_backend_name() != "postgresql":
        _fail("dialeto diferente de PostgreSQL")
    if url.host != EXPECTED_HOST:
        _fail("host divergente")
    if url.port != EXPECTED_PORT:
        _fail("porta divergente")
    if url.database != EXPECTED_DATABASE:
        _fail("banco divergente")
    if url.username != EXPECTED_USER:
        _fail("usuario divergente")
    if not url.password:
        _fail("credencial de conexao ausente")
    if str(url.query.get("sslmode", "")).casefold() != EXPECTED_SSLMODE:
        _fail("modo SSL divergente")
    return url


def _normalized_address(value: object) -> str:
    try:
        return str(ip_interface(str(value)).ip)
    except ValueError:
        _fail("endereco PostgreSQL invalido")


def verify_homologation_engine(
    engine: Engine,
    database_url: str | URL,
) -> PostgreSQLIdentity:
    """Confirm configured coordinates and the live read-only DB identity."""
    validate_homologation_url(database_url)
    validate_homologation_url(engine.url)

    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT current_database(), current_user, "
                    "inet_server_addr()::text, inet_server_port()"
                )
            ).one()
    except Exception:
        raise HomologationTargetError(
            "Nao foi possivel confirmar a identidade PostgreSQL de homologacao."
        ) from None

    identity = PostgreSQLIdentity(
        database=str(row[0]),
        username=str(row[1]),
        server_address=_normalized_address(row[2]),
        server_port=int(row[3]),
    )
    if identity.database != EXPECTED_DATABASE:
        _fail("identidade do banco divergente")
    if identity.username != EXPECTED_USER:
        _fail("identidade do usuario divergente")
    if identity.server_address != _normalized_address(EXPECTED_HOST):
        _fail("identidade do servidor divergente")
    if identity.server_port != EXPECTED_PORT:
        _fail("identidade da porta divergente")
    return identity


def enforce_homologation_target(
    engine: Engine,
    database_url: str | URL,
    *,
    app_env: str | None = None,
) -> PostgreSQLIdentity | None:
    """Apply the guard only to the explicitly named homologation environment."""
    environment = app_env if app_env is not None else os.getenv("APP_ENV", "")
    if environment.strip().casefold() != "homologacao":
        return None
    return verify_homologation_engine(engine, database_url)
