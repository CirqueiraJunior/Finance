from datetime import timedelta

from fastapi.testclient import TestClient
import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.pool import NullPool

from finance_server.app_factory import (
    create_app, database_engine_options, runtime_environment_metadata, utcnow,
)
from finance_server.config import ServerSettings
from finance_server.email_service import FakeEmailService
from finance_server.models import (
    AuditLog, PasswordResetToken, PersonalRecoveryKey, RefreshSession, User,
    UserRole,
)
from finance_server.security import hash_password, validate_password, verify_password


PASSWORD = "Strong!Pass123"
NEW_PASSWORD = "New!StrongPass456"


@pytest.fixture
def api_context(tmp_path):
    email = FakeEmailService()
    settings = ServerSettings(
        f"sqlite:///{(tmp_path / 'api.db').as_posix()}", "s" * 64,
        access_token_minutes=15, refresh_token_days=7, reset_token_minutes=30,
    )
    app = create_app(settings, email_service=email, create_schema=True)
    with app.state.session_factory() as session:
        admin = User(nome="Administrador", email="admin@example.com", username="admin",
                     password_hash=hash_password(PASSWORD),
                     perfil=UserRole.ADMINISTRATOR.value, ativo=True)
        manager = User(nome="Gestor", email="gestor@example.com", username="gestor",
                       password_hash=hash_password(PASSWORD),
                       perfil=UserRole.MANAGER.value, ativo=True)
        inactive = User(nome="Inativo", email="off@example.com", username="off",
                        password_hash=hash_password(PASSWORD),
                        perfil=UserRole.READ_ONLY.value, ativo=False)
        session.add_all([admin, manager, inactive])
        session.commit()
    with TestClient(app) as client:
        yield client, app, email, settings
    app.state.engine.dispose()


def login(client, identifier="admin", password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"identifier": identifier, "password": password})


def test_postgresql_uses_provider_pool_without_persistent_local_pool():
    options = database_engine_options("postgresql+psycopg://user:password@db.example/finance")

    assert options["poolclass"] is NullPool
    assert options["pool_pre_ping"] is True
    assert options["connect_args"]["connect_timeout"] == 10


def test_sqlite_keeps_local_pool_configuration():
    assert database_engine_options("sqlite:///local.db") == {"pool_pre_ping": True}


def test_server_environment_metadata_keeps_central_protections():
    assert runtime_environment_metadata("postgresql") == {
        "environment": "SERVER",
        "database": "PostgreSQL central",
        "historical_import_enabled": False,
    }


def auth(pair):
    return {"Authorization": f"Bearer {pair['access_token']}"}


@pytest.mark.parametrize("password", ["Abc123", "Finance1"])
def test_password_policy_accepts_supported_passwords(password):
    validate_password(password)
    assert verify_password(password, hash_password(password))


@pytest.mark.parametrize("password", ["abc123", "ABC123", "Abcdef", "Ab12"])
def test_password_policy_rejects_passwords_outside_requirements(password):
    message = (
        "A senha deve possuir no mínimo 6 caracteres, incluindo uma letra maiúscula, "
        "uma letra minúscula e um número."
    )
    with pytest.raises(ValueError, match=message.replace(".", r"\.")):
        validate_password(password)


def test_user_creation_change_and_reset_share_password_policy(api_context):
    client, _, email, _ = api_context
    pair = login(client).json()
    created = client.post("/api/v1/users", headers=auth(pair), json={
        "nome": "Senha Curta", "email": "short@example.com", "username": "short",
        "password": "Abc123", "perfil": "CONSULTA",
    })
    assert created.status_code == 201
    assert client.post("/api/v1/auth/change-password", headers=auth(pair), json={
        "current_password": PASSWORD, "new_password": "Finance1",
    }).status_code == 204
    client.post("/api/v1/auth/forgot-password", json={"email": "short@example.com"})
    token = email.messages[-1][1]
    rejected = client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "abc123",
    })
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == (
        "A senha deve possuir no mínimo 6 caracteres, incluindo uma letra maiúscula, "
        "uma letra minúscula e um número."
    )


def test_health_login_hash_and_response_hides_password(api_context):
    client, app, _, _ = api_context
    assert client.get("/health").json() == {
        "status": "ok", "version": "1.0.0", "environment": "DEV",
        "database": "SQLite DEV", "historical_import_enabled": True,
    }
    response = login(client)
    assert response.status_code == 200
    pair = response.json()
    assert pair["access_token"] and pair["refresh_token"]
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "admin"))
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("$argon2id$")
        assert verify_password(PASSWORD, user.password_hash)
    users = client.get("/api/v1/users", headers=auth(pair)).json()
    assert "password_hash" not in users[0]


def test_invalid_and_inactive_login_are_generic_and_audited(api_context):
    client, app, _, _ = api_context
    for identifier, password in (("unknown", PASSWORD), ("admin", "wrong"), ("off", PASSWORD)):
        response = login(client, identifier, password)
        assert response.status_code == 401
        assert response.json()["detail"] == "Usuário ou senha inválidos."
    with app.state.session_factory() as session:
        assert len(list(session.scalars(select(AuditLog).where(AuditLog.action == "LOGIN_FAILED")))) == 3


def test_refresh_rotates_and_logout_revokes_session(api_context):
    client, _, _, _ = api_context
    pair = login(client).json()
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert refreshed.status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401
    new_pair = refreshed.json()
    assert client.post("/api/v1/auth/logout", json={"refresh_token": new_pair["refresh_token"]},
                       headers=auth(new_pair)).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new_pair["refresh_token"]}).status_code == 401


def test_forgot_reset_is_neutral_single_use_and_revokes_sessions(api_context):
    client, app, email, _ = api_context
    pair = login(client).json()
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "none@example.com"})
    known = client.post("/api/v1/auth/forgot-password", json={"email": "admin@example.com"})
    assert unknown.json() == known.json()
    assert known.json()["message"].startswith("Se o endereço")
    token = email.messages[-1][1]
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": NEW_PASSWORD}).status_code == 204
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": PASSWORD}).status_code == 400
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]}).status_code == 401
    assert login(client, "admin", NEW_PASSWORD).status_code == 200


def test_expired_reset_token_is_rejected(api_context):
    client, app, email, _ = api_context
    client.post("/api/v1/auth/forgot-password", json={"email": "admin@example.com"})
    token = email.messages[-1][1]
    with app.state.session_factory() as session:
        item = session.scalar(select(PasswordResetToken))
        item.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert client.post("/api/v1/auth/reset-password", json={"token": token,
                                                              "new_password": NEW_PASSWORD}).status_code == 400


def test_change_password_validates_current_and_audits(api_context):
    client, app, _, _ = api_context
    pair = login(client).json()
    assert client.post("/api/v1/auth/change-password", headers=auth(pair),
                       json={"current_password": "wrong", "new_password": NEW_PASSWORD}).status_code == 400
    assert client.post("/api/v1/auth/change-password", headers=auth(pair),
                       json={"current_password": PASSWORD, "new_password": NEW_PASSWORD}).status_code == 204
    with app.state.session_factory() as session:
        assert session.scalar(select(AuditLog).where(AuditLog.action == "PASSWORD_CHANGED"))
        user = session.scalar(select(User).where(User.username == "admin"))
        assert user.personal_recovery_key_pending is False
        assert session.scalar(
            select(PersonalRecoveryKey).where(PersonalRecoveryKey.user_id == user.id)
        ) is None


def test_rbac_users_crud_and_403(api_context):
    client, app, _, _ = api_context
    manager_pair = login(client, "gestor").json()
    assert client.get("/api/v1/users", headers=auth(manager_pair)).status_code == 200
    admin_pair = login(client).json()
    created = client.post("/api/v1/users", headers=auth(manager_pair), json={
        "nome": "Operador", "email": "operator@example.com", "username": "operator",
        "password": PASSWORD, "perfil": "OPERADOR_FINANCEIRO",
    })
    assert created.status_code == 201
    user_id = created.json()["id"]
    updated = client.patch(f"/api/v1/users/{user_id}", headers=auth(admin_pair),
                           json={"ativo": False, "perfil": "CONSULTA"})
    assert updated.status_code == 200
    assert updated.json()["ativo"] is False
    assert login(client, "operator").status_code == 401
    audit = client.get("/api/v1/audit", headers=auth(admin_pair))
    assert audit.status_code == 200
    serialized = str(audit.json()).casefold()
    assert "password_hash" not in serialized and PASSWORD.casefold() not in serialized


def test_manager_cannot_administer_or_create_administrator(api_context):
    client, _, _, _ = api_context
    manager = auth(login(client, "gestor").json())
    users = client.get("/api/v1/users", headers=manager).json()
    administrator = next(item for item in users if item["perfil"] == "ADMINISTRADOR")

    created = client.post("/api/v1/users", headers=manager, json={
        "nome": "Consulta", "email": "consulta@example.com", "username": "consulta",
        "password": PASSWORD, "perfil": "CONSULTA",
    })
    assert created.status_code == 201
    target_id = created.json()["id"]
    assert client.patch(
        f"/api/v1/users/{target_id}", headers=manager,
        json={"nome": "Consulta editada"},
    ).status_code == 200

    assert client.patch(
        f"/api/v1/users/{administrator['id']}", headers=manager,
        json={"nome": "Bloqueado"},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/users/{administrator['id']}", headers=manager,
        json={"ativo": False},
    ).status_code == 403
    assert client.post(
        f"/api/v1/users/{administrator['id']}/reset-password",
        headers=manager, json={"temporary_password": "Finance1"},
    ).status_code == 403
    assert client.patch(
        f"/api/v1/users/{target_id}", headers=manager,
        json={"perfil": "ADMINISTRADOR"},
    ).status_code == 403
    assert client.post("/api/v1/users", headers=manager, json={
        "nome": "Admin proibido", "email": "forbidden@example.com",
        "username": "forbidden", "password": PASSWORD,
        "perfil": "ADMINISTRADOR",
    }).status_code == 403


@pytest.mark.parametrize(
    "target_role",
    ["OPERADOR_FINANCEIRO", "OPERADOR_BOE", "CONSULTA"],
)
def test_manager_can_toggle_non_administrator_without_losing_session(
    api_context, target_role,
):
    client, _, _, _ = api_context
    manager = auth(login(client, "gestor").json())
    suffix = target_role.casefold()
    created = client.post("/api/v1/users", headers=manager, json={
        "nome": target_role,
        "email": f"{suffix}@example.com",
        "username": suffix,
        "password": PASSWORD,
        "perfil": target_role,
    })
    assert created.status_code == 201

    disabled = client.patch(
        f"/api/v1/users/{created.json()['id']}",
        headers=manager,
        json={"ativo": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["ativo"] is False
    assert client.get("/api/v1/users", headers=manager).status_code == 200

    enabled = client.patch(
        f"/api/v1/users/{created.json()['id']}",
        headers=manager,
        json={"ativo": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["ativo"] is True


def test_administrator_can_toggle_common_user(api_context):
    client, _, _, _ = api_context
    administrator = auth(login(client).json())
    created = client.post("/api/v1/users", headers=administrator, json={
        "nome": "Operador", "email": "toggle@example.com", "username": "toggle",
        "password": PASSWORD, "perfil": "OPERADOR_FINANCEIRO",
    })

    response = client.patch(
        f"/api/v1/users/{created.json()['id']}",
        headers=administrator,
        json={"ativo": False},
    )
    assert response.status_code == 200
    assert response.json()["ativo"] is False


def test_operators_follow_their_final_operational_permissions(api_context):
    client, app, _, _ = api_context
    with app.state.session_factory() as session:
        session.add_all([
            User(
                nome="Financeiro", email="fin@example.com", username="fin",
                password_hash=hash_password(PASSWORD),
                perfil=UserRole.FINANCE_OPERATOR.value, ativo=True,
            ),
            User(
                nome="BOE", email="boe@example.com", username="boe",
                password_hash=hash_password(PASSWORD),
                perfil=UserRole.BOE_OPERATOR.value, ativo=True,
            ),
        ])
        session.commit()
    financial = auth(login(client, "fin").json())
    boe = auth(login(client, "boe").json())

    assert client.get("/api/v1/cashflow", headers=financial).status_code == 200
    assert client.get("/api/v1/budgets?year=2026", headers=financial).status_code == 200
    assert client.get("/api/v1/catalog", headers=financial).status_code == 200
    assert client.get("/api/v1/entities", headers=financial).status_code == 403
    created_cashflow = client.post("/api/v1/cashflow", headers=financial, json={
        "periodo_ano": 2026, "periodo_mes": 9,
        "data_lancamento": "2026-09-15", "descricao": "Operação autorizada",
        "tipo": "RECEITA", "categoria": "RECEITA_INDIRETA", "valor": "10.00",
    })
    assert created_cashflow.status_code == 201
    assert client.post("/api/v1/budgets", headers=financial, json={}).status_code == 403
    created_catalog = client.post("/api/v1/catalog", headers=financial, json={
        "description": "Item operacional", "category": "RECEITA_INDIRETA",
        "movement_type": "RECEITA", "active": True,
    })
    assert created_catalog.status_code == 201
    updated_catalog = client.patch(
        f"/api/v1/catalog/{created_catalog.json()['id']}",
        headers=financial,
        json={
            "description": "Item operacional editado",
            "category": "RECEITA_INDIRETA",
            "movement_type": "RECEITA",
            "active": True,
        },
    )
    assert updated_catalog.status_code == 200

    assert client.get("/api/v1/boe", headers=boe).status_code == 200
    assert client.get("/api/v1/entities", headers=boe).status_code == 200
    assert client.get("/api/v1/catalog", headers=boe).status_code == 403
    assert client.post(
        "/api/v1/boe/import", headers=boe,
        files={"file": ("boe.xlsx", b"not-used")},
    ).status_code == 403
    assert client.post("/api/v1/entities", headers=boe, json={}).status_code == 403


def test_read_only_keeps_entity_lookup_without_registration_writes(api_context):
    client, app, _, _ = api_context
    with app.state.session_factory() as session:
        session.add(User(
            nome="Consulta", email="consulta@example.com", username="consulta",
            password_hash=hash_password(PASSWORD),
            perfil=UserRole.READ_ONLY.value, ativo=True,
        ))
        session.commit()
    read_only = auth(login(client, "consulta").json())

    assert client.get("/api/v1/entities", headers=read_only).status_code == 200
    assert client.post(
        "/api/v1/entities", headers=read_only, json={}
    ).status_code == 403


def test_temporary_password_requires_change_before_functional_access(api_context):
    client, app, _, _ = api_context
    admin_pair = login(client).json()
    created = client.post("/api/v1/users", headers=auth(admin_pair), json={
        "nome": "Primeiro Acesso", "email": "first@example.com", "username": "first",
        "password": "Abc123", "perfil": "CONSULTA",
    })
    assert created.status_code == 201
    assert created.json()["must_change_password"] is True

    temporary_pair = login(client, "first", "Abc123")
    assert temporary_pair.status_code == 200
    assert temporary_pair.json()["must_change_password"] is True
    assert client.get("/api/v1/dashboard?year=2026&month=1",
                      headers=auth(temporary_pair.json())).status_code == 403
    assert client.post(
        "/api/v1/auth/change-password", headers=auth(temporary_pair.json()),
        json={"current_password": "Abc123", "new_password": "Finance1"},
    ).status_code == 409

    invalid = client.post(
        "/api/v1/auth/complete-password-change",
        headers=auth(temporary_pair.json()), json={"new_password": "abcdef"},
    )
    assert invalid.status_code == 422
    completed = client.post(
        "/api/v1/auth/complete-password-change",
        headers=auth(temporary_pair.json()), json={"new_password": "Finance1"},
    )
    assert completed.status_code == 200
    assert completed.json()["must_change_password"] is False
    assert client.get("/api/v1/dashboard?year=2026&month=1",
                      headers=auth(completed.json())).status_code == 200
    assert login(client, "first", "Finance1").json()["must_change_password"] is False

    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "first"))
        assert user.must_change_password is False
        assert session.scalar(select(AuditLog).where(
            AuditLog.user_id == user.id,
            AuditLog.action == "PASSWORD_INITIAL_CHANGED",
        ))


def test_expired_access_token_is_rejected(api_context):
    client, _, _, settings = api_context
    pair = login(client).json()
    payload = jwt.decode(pair["access_token"], settings.secret_key, algorithms=["HS256"])
    payload["exp"] = utcnow() - timedelta(seconds=1)
    expired = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    assert client.get("/api/v1/users", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_two_users_share_cashflow_and_detect_conflict(api_context):
    client, app, _, _ = api_context
    with app.state.session_factory() as session:
        session.add(User(nome="Gestor A", email="finance.a@example.com", username="finance.a",
                         password_hash=hash_password(PASSWORD), perfil="GESTOR", ativo=True))
        session.add(User(nome="Gestor B", email="finance.b@example.com", username="finance.b",
                         password_hash=hash_password(PASSWORD), perfil="GESTOR", ativo=True))
        session.commit()
    pair_a = login(client, "finance.a").json()
    pair_b = login(client, "finance.b").json()
    created = client.post("/api/v1/cashflow", headers=auth(pair_a), json={
        "periodo_ano": 2026, "periodo_mes": 8, "data_lancamento": "2026-08-28",
        "descricao": "Compartilhado", "tipo": "RECEITA", "categoria": "RECEITA_INDIRETA",
        "valor": "100.00",
    })
    assert created.status_code == 201
    entry = created.json()
    assert client.get("/api/v1/cashflow", headers=auth(pair_b)).json()[0]["descricao"] == "Compartilhado"
    updated = client.patch(f"/api/v1/cashflow/{entry['id']}", headers=auth(pair_a),
                           json={"expected_version": 1, "valor": "125.00"})
    assert updated.status_code == 200 and updated.json()["version"] == 2
    conflict = client.patch(f"/api/v1/cashflow/{entry['id']}", headers=auth(pair_b),
                            json={"expected_version": 1, "valor": "150.00"})
    assert conflict.status_code == 409
    assert client.get("/api/v1/cashflow", headers=auth(pair_b)).json()[0]["valor"] == "125.0000"
