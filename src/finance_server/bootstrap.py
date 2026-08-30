import os

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from finance_server.config import get_server_settings
from finance_server.models import User, UserRole
from finance_server.security import hash_password


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
        if session.scalar(select(User.id).where(User.perfil == UserRole.ADMINISTRATOR.value)):
            raise SystemExit("Bootstrap recusado: já existe Administrador.")
        session.add(User(
            nome=values["BOOTSTRAP_ADMIN_NAME"],
            email=values["BOOTSTRAP_ADMIN_EMAIL"].casefold(),
            username=values["BOOTSTRAP_ADMIN_USERNAME"].casefold(),
            password_hash=hash_password(values["BOOTSTRAP_ADMIN_PASSWORD"]),
            perfil=UserRole.ADMINISTRATOR.value, ativo=True,
        ))
        session.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
