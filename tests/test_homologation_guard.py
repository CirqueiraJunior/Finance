from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.homologation_guard import (
    HomologationTargetError,
    enforce_homologation_target,
    verify_homologation_engine,
)


VALID_URL = (
    "postgresql+psycopg://ja_finance_hml:test-only@127.0.0.1:5432/"
    "ja_finance_homologacao?sslmode=disable"
)


class _Result:
    def __init__(self, identity):
        self.identity = identity

    def one(self):
        return self.identity


class _Connection:
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        self.engine.connect_count += 1
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, _statement):
        return _Result(self.engine.identity)


class _Engine:
    def __init__(self, url=VALID_URL, identity=None):
        self.url = make_url(url)
        self.identity = identity or (
            "ja_finance_homologacao",
            "ja_finance_hml",
            "127.0.0.1/32",
            5432,
        )
        self.connect_count = 0

    def connect(self):
        return _Connection(self)


def test_homologation_guard_confirms_configured_and_live_identity():
    engine = _Engine()

    identity = verify_homologation_engine(engine, VALID_URL)

    assert identity.database == "ja_finance_homologacao"
    assert identity.username == "ja_finance_hml"
    assert identity.server_address == "127.0.0.1"
    assert engine.connect_count == 1


@pytest.mark.parametrize(
    "url",
    [
        VALID_URL.replace("127.0.0.1", "localhost"),
        VALID_URL.replace(":5432/", ":5433/"),
        VALID_URL.replace("ja_finance_hml", "outro_usuario", 1),
        VALID_URL.replace("ja_finance_homologacao", "outro_banco"),
        VALID_URL.replace("sslmode=disable", "sslmode=prefer"),
        VALID_URL.replace("sslmode=disable", "sslmode=require"),
    ],
)
def test_homologation_guard_blocks_wrong_configured_target_before_connect(url):
    engine = _Engine(url=url)

    with pytest.raises(HomologationTargetError):
        verify_homologation_engine(engine, url)

    assert engine.connect_count == 0


@pytest.mark.parametrize(
    "identity",
    [
        ("outro_banco", "ja_finance_hml", "127.0.0.1", 5432),
        ("ja_finance_homologacao", "outro_usuario", "127.0.0.1", 5432),
        ("ja_finance_homologacao", "ja_finance_hml", "127.0.0.2", 5432),
        ("ja_finance_homologacao", "ja_finance_hml", "127.0.0.2/32", 5432),
        ("ja_finance_homologacao", "ja_finance_hml", "127.0.0.1", 5433),
    ],
)
def test_homologation_guard_blocks_wrong_live_identity(identity):
    engine = _Engine(identity=identity)

    with pytest.raises(HomologationTargetError):
        verify_homologation_engine(engine, VALID_URL)


def test_guard_is_inert_outside_homologation():
    engine = _Engine()

    result = enforce_homologation_target(
        engine,
        VALID_URL,
        app_env="server",
    )

    assert result is None
    assert engine.connect_count == 0


def test_guard_runs_for_homologation():
    engine = _Engine()

    identity = enforce_homologation_target(
        engine,
        VALID_URL,
        app_env="homologacao",
    )

    assert identity is not None
    assert engine.connect_count == 1


def test_api_startup_blocks_wrong_target_in_homologation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "homologacao")
    settings = ServerSettings(
        database_url="sqlite+pysqlite:///:memory:",
        secret_key="s" * 48,
    )

    with pytest.raises(HomologationTargetError):
        create_app(settings=settings)
