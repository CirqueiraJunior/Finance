import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from finance_server.config import get_server_settings
from finance_server.initial_setup import (
    InitialAdministratorData,
    InitialSetupUnavailableError,
    create_initial_administrator,
)


def main() -> int:
    settings = get_server_settings()
    values = {name: os.getenv(name, "").strip() for name in (
        "BOOTSTRAP_ADMIN_NAME", "BOOTSTRAP_ADMIN_EMAIL",
        "BOOTSTRAP_ADMIN_USERNAME", "BOOTSTRAP_ADMIN_PASSWORD",
    )}
    if not all(values.values()):
        raise SystemExit("Variáveis BOOTSTRAP_ADMIN_* obrigatórias não configuradas.")
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        try:
            create_initial_administrator(
                session,
                InitialAdministratorData(
                    nome=values["BOOTSTRAP_ADMIN_NAME"],
                    email=values["BOOTSTRAP_ADMIN_EMAIL"],
                    username=values["BOOTSTRAP_ADMIN_USERNAME"],
                    password=values["BOOTSTRAP_ADMIN_PASSWORD"],
                ),
                origin="CLI_BOOTSTRAP",
            )
            session.commit()
        except InitialSetupUnavailableError as error:
            session.rollback()
            raise SystemExit(f"Bootstrap recusado: {error}") from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
