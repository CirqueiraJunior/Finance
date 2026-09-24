from __future__ import annotations

import sys

import uvicorn

from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.environment import (
    EnvironmentCommandError,
    build_postgres_url,
)
from finance_server.service_config import ServiceServerConfigStore


API_HOST = "127.0.0.1"
API_PORT = 8000


def build_service_settings() -> ServerSettings:
    connection, password, secret_key = ServiceServerConfigStore().load()

    database_url = build_postgres_url(connection, password)

    return ServerSettings(
        database_url=database_url,
        secret_key=secret_key,
    )


def create_service_app():
    settings = build_service_settings()
    return create_app(settings=settings)


def run() -> int:
    try:
        settings = build_service_settings()
    except EnvironmentCommandError as error:
        print(f"FinanceServer configuration error: {error}", file=sys.stderr)
        return 2

    app = create_app(settings=settings)

    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info",
        access_log=True,
    )

    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
