from __future__ import annotations

import secrets

from finance_server.environment import (
    EnvironmentCommandError,
    ServerConnectionConfig,
)
from finance_server.service_config import ServiceServerConfigStore


def provision_service_configuration(
    *,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    store: ServiceServerConfigStore | None = None,
) -> None:
    """Persist the Windows-service configuration using machine-scope DPAPI."""
    host = host.strip()
    database = database.strip()
    username = username.strip()
    if not host or not database or not username:
        raise EnvironmentCommandError(
            "Host, banco e usuÃ¡rio PostgreSQL sÃ£o obrigatÃ³rios."
        )
    if not 1 <= port <= 65535:
        raise EnvironmentCommandError("A porta PostgreSQL Ã© invÃ¡lida.")
    if not password:
        raise EnvironmentCommandError("A senha PostgreSQL Ã© obrigatÃ³ria.")

    target = store or ServiceServerConfigStore()
    connection = ServerConnectionConfig(
        host=host,
        port=port,
        database=database,
        username=username,
        sslmode="require",
    )
    secret_key = secrets.token_urlsafe(48)
    target.save(connection, password=password, secret_key=secret_key)

    recovered_connection, recovered_password, recovered_secret = target.load()
    if (
        recovered_connection != connection
        or recovered_password != password
        or recovered_secret != secret_key
    ):
        raise EnvironmentCommandError(
            "A validaÃ§Ã£o DPAPI da configuraÃ§Ã£o do serviÃ§o falhou."
        )
