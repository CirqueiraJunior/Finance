"""Preflight de segurança do ambiente PostgreSQL de homologação."""

import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sqlalchemy import create_engine

from finance_server.app_factory import database_engine_options
from finance_server.config import get_server_settings
from finance_server.homologation_guard import (
    HomologationTargetError,
    verify_homologation_engine,
)


def main() -> int:
    if os.environ.get("APP_ENV", "").strip().casefold() != "homologacao":
        print("BLOQUEADO: APP_ENV nao identifica homologacao.")
        return 1

    try:
        settings = get_server_settings()
    except RuntimeError:
        print("BLOQUEADO: configuracao da API incompleta.")
        return 1

    engine = None
    try:
        engine = create_engine(
            settings.database_url,
            **database_engine_options(settings.database_url),
        )
        verify_homologation_engine(engine, settings.database_url)
    except HomologationTargetError:
        print("CONEXAO_HOMOLOGACAO_REPROVADA")
        return 1
    except Exception:
        print("CONEXAO_HOMOLOGACAO_REPROVADA")
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    print("CONFIGURACAO_EFETIVA_CONFIRMADA")
    print("IDENTIDADE_POSTGRESQL_CONFIRMADA")
    print("PREFLIGHT_HOMOLOGACAO_APROVADO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
