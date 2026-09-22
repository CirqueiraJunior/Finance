from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.models import AuditLog, User, UserRole
from finance_server.security import verify_password


PASSWORD = "Finance1"
PAYLOAD = {
    "nome": "Administrador Inicial",
    "email": "Initial.Admin@Example.com",
    "username": "Initial.Admin",
    "password": PASSWORD,
}


def make_app(tmp_path, name="setup.db"):
    settings = ServerSettings(
        f"sqlite:///{(tmp_path / name).as_posix()}", "s" * 64
    )
    return create_app(settings, create_schema=True)


def local_client(app, **kwargs):
    return TestClient(app, client=("127.0.0.1", 50000), **kwargs)


def test_status_and_first_administrator_are_derived_from_users(tmp_path):
    app = make_app(tmp_path)
    with local_client(app) as client:
        assert client.get("/api/v1/setup/status").json() == {
            "requires_initial_setup": True
        }
        response = client.post("/api/v1/setup/administrator", json=PAYLOAD)
        assert response.status_code == 201
        assert response.json()["perfil"] == UserRole.ADMINISTRATOR.value
        assert response.json()["must_change_password"] is False
        assert client.get("/api/v1/setup/status").json() == {
            "requires_initial_setup": False
        }
        first_login = client.post(
            "/api/v1/auth/login",
            json={"identifier": "initial.admin", "password": PASSWORD},
        )
        assert first_login.status_code == 200
        assert first_login.json()["personal_recovery_key"]
        second_login = client.post(
            "/api/v1/auth/login",
            json={"identifier": "initial.admin", "password": PASSWORD},
        )
        assert second_login.status_code == 200
        assert "personal_recovery_key" not in second_login.json()

    with app.state.session_factory() as session:
        user = session.scalar(select(User))
        assert user.email == "initial.admin@example.com"
        assert user.username == "initial.admin"
        assert user.ativo is True
        assert user.must_change_password is False
        assert user.personal_recovery_key_pending is False
        assert user.password_hash != PASSWORD
        assert verify_password(PASSWORD, user.password_hash)
        log = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "INITIAL_ADMINISTRATOR_CREATED"
            )
        )
        assert log is not None
        serialized = str(log.details).casefold()
        assert "password" not in serialized
        assert PASSWORD.casefold() not in serialized
    app.state.engine.dispose()


def test_setup_is_unavailable_when_any_user_exists_and_second_create_is_blocked(
    tmp_path,
):
    app = make_app(tmp_path)
    with app.state.session_factory() as session:
        session.add(
            User(
                nome="Consulta",
                email="consulta@example.com",
                username="consulta",
                password_hash="hash",
                perfil=UserRole.READ_ONLY.value,
                ativo=True,
            )
        )
        session.commit()
    with local_client(app) as client:
        assert client.get("/api/v1/setup/status").json() == {
            "requires_initial_setup": False
        }
        response = client.post("/api/v1/setup/administrator", json=PAYLOAD)
        assert response.status_code == 409
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(User.id))) == 1
    app.state.engine.dispose()


def test_setup_rejects_invalid_password_and_client_selected_profile(tmp_path):
    app = make_app(tmp_path)
    with local_client(app) as client:
        invalid = client.post(
            "/api/v1/setup/administrator",
            json={**PAYLOAD, "password": "abc123"},
        )
        assert invalid.status_code == 422
        selected = client.post(
            "/api/v1/setup/administrator",
            json={**PAYLOAD, "perfil": UserRole.READ_ONLY.value},
        )
        assert selected.status_code == 422
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(User.id))) == 0
    app.state.engine.dispose()


def test_setup_is_local_only(tmp_path):
    app = make_app(tmp_path)
    with TestClient(app, client=("198.51.100.4", 50000)) as remote:
        assert remote.get("/api/v1/setup/status").status_code == 403
        assert remote.post(
            "/api/v1/setup/administrator", json=PAYLOAD
        ).status_code == 403
    with local_client(app) as local:
        assert local.get(
            "/api/v1/setup/status",
            headers={"X-Forwarded-For": "198.51.100.4"},
        ).status_code == 403
    app.state.engine.dispose()


def test_concurrent_setup_creates_exactly_one_user(tmp_path):
    app = make_app(tmp_path)

    def create(index):
        payload = {
            **PAYLOAD,
            "email": f"admin{index}@example.com",
            "username": f"admin{index}",
        }
        with local_client(app) as client:
            return client.post(
                "/api/v1/setup/administrator", json=payload
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(create, (1, 2)))

    assert sorted(statuses) == [201, 409]
    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(User.id))) == 1
        assert session.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "INITIAL_ADMINISTRATOR_CREATED"
            )
        ) == 1
    app.state.engine.dispose()


def test_failure_while_auditing_rolls_back_user(tmp_path):
    app = make_app(tmp_path)
    session_class = app.state.session_factory.class_

    def fail_audit(session, _flush_context, _instances):
        if any(isinstance(item, AuditLog) for item in session.new):
            raise RuntimeError("audit failure")

    event.listen(session_class, "before_flush", fail_audit)
    try:
        with local_client(app, raise_server_exceptions=False) as client:
            response = client.post(
                "/api/v1/setup/administrator", json=PAYLOAD
            )
            assert response.status_code == 500
    finally:
        event.remove(session_class, "before_flush", fail_audit)

    with app.state.session_factory() as session:
        assert session.scalar(select(func.count(User.id))) == 0
        assert session.scalar(select(func.count(AuditLog.id))) == 0
    app.state.engine.dispose()
