import pytest

from finance_server.environment import EnvironmentCommandError
from finance_server.service_setup import provision_service_configuration


class MemoryStore:
    def __init__(self):
        self.saved = None

    def save(self, connection, *, password, secret_key):
        self.saved = (connection, password, secret_key)

    def load(self):
        return self.saved


def test_provision_service_configuration_saves_machine_store_contract():
    store = MemoryStore()

    provision_service_configuration(
        host=" db.example ",
        port=5432,
        database=" postgres ",
        username=" finance.user ",
        password="Password1",
        store=store,
    )

    connection, password, secret_key = store.saved
    assert (
        connection.host,
        connection.port,
        connection.database,
        connection.username,
        connection.sslmode,
    ) == ("db.example", 5432, "postgres", "finance.user", "require")
    assert password == "Password1"
    assert len(secret_key) >= 32


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"host": ""}, "Host, banco e usuário"),
        ({"port": 0}, "porta PostgreSQL"),
        ({"password": ""}, "senha PostgreSQL"),
    ],
)
def test_provision_service_configuration_rejects_invalid_input(overrides, message):
    arguments = {
        "host": "db.example",
        "port": 5432,
        "database": "postgres",
        "username": "finance.user",
        "password": "Password1",
        "store": MemoryStore(),
    }
    arguments.update(overrides)

    with pytest.raises(EnvironmentCommandError, match=message):
        provision_service_configuration(**arguments)
