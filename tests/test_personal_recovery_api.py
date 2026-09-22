from sqlalchemy import select

from finance_server.models import AuditLog, PersonalRecoveryKey, RefreshSession, User
from finance_server.security import token_hash, verify_password
from tests.test_multiuser_api import PASSWORD, api_context, auth, login


def _create_temporary_user(client):
    admin = login(client).json()
    response = client.post(
        "/api/v1/users",
        headers=auth(admin),
        json={
            "nome": "Recuperação Pessoal",
            "email": "personal@example.com",
            "username": "personal",
            "password": "Abc123",
            "perfil": "CONSULTA",
        },
    )
    assert response.status_code == 201


def _complete_first_access(client):
    temporary = login(client, "personal", "Abc123").json()
    response = client.post(
        "/api/v1/auth/complete-password-change",
        headers=auth(temporary),
        json={"new_password": "Finance1"},
    )
    assert response.status_code == 200
    return response.json(), temporary


def test_first_change_creates_one_time_personal_key_as_hash_only(api_context):
    client, app, _, _ = api_context
    _create_temporary_user(client)
    completed, _ = _complete_first_access(client)
    raw = completed["personal_recovery_key"]
    assert raw.startswith("FIN-")
    assert "personal_recovery_key" not in login(client, "personal", "Finance1").json()

    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "personal"))
        stored = session.scalar(
            select(PersonalRecoveryKey).where(PersonalRecoveryKey.user_id == user.id)
        )
        assert stored.key_hash == token_hash(raw)
        assert raw not in stored.key_hash
        serialized_audit = str(
            list(session.scalars(select(AuditLog).where(AuditLog.user_id == user.id)))
        )
        assert raw not in serialized_audit


def test_personal_key_is_single_use_changes_password_and_revokes_sessions(api_context):
    client, app, _, _ = api_context
    _create_temporary_user(client)
    completed, temporary = _complete_first_access(client)
    current = login(client, "personal", "Finance1").json()
    raw = completed["personal_recovery_key"]
    response = client.post(
        "/api/v1/auth/personal-recovery",
        json={"identifier": "personal", "recovery_key": raw, "new_password": "Finance2"},
    )
    assert response.status_code == 204
    assert login(client, "personal", "Finance1").status_code == 401
    recovered_login = login(client, "personal", "Finance2")
    assert recovered_login.status_code == 200
    replacement = recovered_login.json()["personal_recovery_key"]
    assert replacement.startswith("FIN-") and replacement != raw
    assert "personal_recovery_key" not in login(client, "personal", "Finance2").json()
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": temporary["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": current["refresh_token"]}).status_code == 401
    reused = client.post(
        "/api/v1/auth/personal-recovery",
        json={"identifier": "personal", "recovery_key": raw, "new_password": "Finance3"},
    )
    assert reused.status_code == 400
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "personal"))
        keys = list(session.scalars(
            select(PersonalRecoveryKey).where(PersonalRecoveryKey.user_id == user.id)
        ))
        assert keys[0].used_at is not None
        assert keys[1].key_hash == token_hash(replacement)
        assert user.personal_recovery_key_pending is False
        assert session.scalar(select(AuditLog).where(
            AuditLog.user_id == user.id,
            AuditLog.action == "PASSWORD_PERSONAL_RECOVERY_COMPLETED",
        ))


def test_manual_regeneration_endpoint_no_longer_exists(api_context):
    client, _, _, _ = api_context
    admin = login(client).json()
    assert client.post(
        "/api/v1/auth/personal-recovery-key/regenerate", headers=auth(admin)
    ).status_code == 404


def test_pending_key_is_not_generated_during_temporary_login(api_context):
    client, app, _, _ = api_context
    _create_temporary_user(client)
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "personal"))
        user.personal_recovery_key_pending = True
        session.commit()
    temporary = login(client, "personal", "Abc123").json()
    assert temporary["must_change_password"] is True
    assert "personal_recovery_key" not in temporary
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "personal"))
        assert user.personal_recovery_key_pending is True
        assert not list(session.scalars(select(PersonalRecoveryKey)))


def test_personal_recovery_validates_policy_and_hides_user_enumeration(api_context):
    client, app, _, _ = api_context
    unknown = client.post(
        "/api/v1/auth/personal-recovery",
        json={"identifier": "missing", "recovery_key": "wrong", "new_password": "Finance2"},
    )
    known = client.post(
        "/api/v1/auth/personal-recovery",
        json={"identifier": "admin", "recovery_key": "wrong", "new_password": "Finance2"},
    )
    assert unknown.status_code == known.status_code == 400
    assert unknown.json() == known.json()
    _create_temporary_user(client)
    completed, _ = _complete_first_access(client)
    generated = completed["personal_recovery_key"]
    invalid_policy = client.post(
        "/api/v1/auth/personal-recovery",
        json={"identifier": "personal", "recovery_key": generated, "new_password": "abcdef"},
    )
    assert invalid_policy.status_code == 422
    with app.state.session_factory() as session:
        key = session.scalar(select(PersonalRecoveryKey))
        assert key.used_at is None and key.revoked_at is None


def test_administrator_can_reset_another_administrator_while_manager_remains_blocked(
    api_context,
):
    client, app, _, _ = api_context
    pair = login(client).json()
    with app.state.session_factory() as session:
        target = User(
            nome="Outro Admin", email="other-admin@example.com", username="other-admin",
            password_hash="unused", perfil="ADMINISTRADOR", ativo=True,
        )
        session.add(target)
        session.commit()
        target_id = target.id
    response = client.post(
        f"/api/v1/users/{target_id}/reset-password",
        headers=auth(pair), json={"temporary_password": "Finance2"},
    )
    assert response.status_code == 204
    with app.state.session_factory() as session:
        refreshed = session.get(User, target_id)
        assert refreshed.must_change_password is True
        assert verify_password("Finance2", refreshed.password_hash)
        event = session.scalar(
            select(AuditLog).where(
                AuditLog.action == "USER_PASSWORD_RESET_BY_ADMIN",
                AuditLog.entity_id == target_id,
            )
        )
        assert event is not None

    manager_pair = login(client, "gestor").json()
    blocked = client.post(
        f"/api/v1/users/{target_id}/reset-password",
        headers=auth(manager_pair), json={"temporary_password": "Finance3"},
    )
    assert blocked.status_code == 403
