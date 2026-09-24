import json

import pytest

from finance_server.environment import EnvironmentCommandError, ServerConnectionConfig
from finance_server.service_config import ServiceServerConfigStore, service_data_root


def test_service_data_root_uses_programdata_without_user_profile(tmp_path):
    assert service_data_root(tmp_path) == tmp_path / "J.A. Technology" / "Finance"


def test_service_config_round_trip_never_persists_plain_secrets(tmp_path, monkeypatch):
    acl_calls = []
    monkeypatch.setattr(
        "finance_server.service_config.restrict_service_acl",
        lambda path, *, directory: acl_calls.append((path, directory)),
    )
    protect = lambda value: b"protected:" + value[::-1]
    unprotect = lambda value: value.removeprefix(b"protected:")[::-1]
    store = ServiceServerConfigStore(tmp_path, protect=protect, unprotect=unprotect)
    connection = ServerConnectionConfig(
        host="database.example", port=5432, database="postgres",
        username="finance.user", sslmode="require",
    )

    store.save(connection, password="DatabasePassword1", secret_key="S" * 48)

    raw = store.path.read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert "DatabasePassword1" not in raw
    assert "S" * 48 not in raw
    assert payload["scope"] == "machine"
    assert store.load() == (connection, "DatabasePassword1", "S" * 48)
    assert acl_calls == [
        (tmp_path, True),
        (store.path.with_suffix(".tmp"), False),
        (store.path, False),
    ]


def test_service_config_converts_dpapi_failure_to_controlled_error(tmp_path):
    path = tmp_path / "server_config.json"
    path.write_text(json.dumps({
        "scope": "machine",
        "connection": {
            "host": "database.example", "port": 5432,
            "database": "postgres", "username": "finance.user",
            "sslmode": "require",
        },
        "password_dpapi": "YQ==",
        "secret_key_dpapi": "Yg==",
    }), encoding="utf-8")
    store = ServiceServerConfigStore(
        tmp_path, unprotect=lambda _value: (_ for _ in ()).throw(OSError("DPAPI"))
    )

    with pytest.raises(EnvironmentCommandError, match="inválida ou inacessível"):
        store.load()
