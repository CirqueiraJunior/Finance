import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from finance_server import assisted_recovery
from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.models import (
    AssistedRecoveryRequest, AuditLog, PersonalRecoveryKey, RefreshSession,
    User, UserRole,
)
from finance_server.personal_recovery import generate_key
from finance_server.security import hash_password, verify_password


OLD_PASSWORD = "Finance1"
NEW_PASSWORD = "Finance2"


def b64decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def b64encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


@pytest.fixture
def assisted_context(tmp_path, monkeypatch):
    private = Ed25519PrivateKey.generate()
    public_path = tmp_path / "finance_public.pem"
    public_path.write_bytes(private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    der = private.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    monkeypatch.setattr(assisted_recovery, "PUBLIC_KEY_PATH", public_path)
    monkeypatch.setattr(
        assisted_recovery, "PUBLIC_KEY_FINGERPRINT", sha256(der).hexdigest().upper()
    )
    settings = ServerSettings(
        f"sqlite:///{(tmp_path / 'api.db').as_posix()}", "s" * 64
    )
    app = create_app(settings, create_schema=True)
    with app.state.session_factory() as session:
        session.add_all([
            User(
                nome="Usuário Ativo", email="active@example.com", username="active",
                password_hash=hash_password(OLD_PASSWORD),
                perfil=UserRole.READ_ONLY.value, ativo=True,
            ),
            User(
                nome="Usuário Inativo", email="inactive@example.com", username="inactive",
                password_hash=hash_password(OLD_PASSWORD),
                perfil=UserRole.READ_ONLY.value, ativo=False,
            ),
        ])
        session.commit()
    with TestClient(app) as client:
        yield client, app, private
    app.state.engine.dispose()


def create_request(client, identifier="active"):
    response = client.post(
        "/api/v1/auth/assisted-recovery/request", json={"identifier": identifier}
    )
    assert response.status_code == 200
    return response.json()


def request_payload(code):
    return json.loads(b64decode(code).decode())


def authorization(private, payload):
    raw = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    return f"{b64encode(raw)}.{b64encode(private.sign(raw))}"


def valid_authorization(client, private, **changes):
    created = create_request(client)
    request = request_payload(created["request_code"])
    payload = {
        "v": 1,
        "product": "FINANCE",
        "environment": request["environment"],
        "request_id": request["request_id"],
        "user_id": request["user_id"],
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
        **changes,
    }
    return authorization(private, payload), request


def test_official_public_key_fingerprint():
    key = assisted_recovery.load_public_key()
    der = key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    assert sha256(der).hexdigest().upper() == (
        "E7EC128B1D4FFEDF1C9B39B914AC6B6FE113D9FF797EC019999908925743F548"
    )


def test_request_is_finance_scoped_and_contains_no_secret(assisted_context):
    client, app, _ = assisted_context
    result = create_request(client, "active@example.com")
    payload = request_payload(result["request_code"])
    assert payload["product"] == "FINANCE"
    assert payload["environment"] == "DEV"
    assert payload["username"] == "active"
    serialized = json.dumps(payload).casefold()
    for forbidden in ("password", "hash", "token", "secret", "database_url"):
        assert forbidden not in serialized
    with app.state.session_factory() as session:
        assert session.scalar(select(AssistedRecoveryRequest))


def test_unknown_and_inactive_users_receive_neutral_response(assisted_context):
    client, app, _ = assisted_context
    unknown = create_request(client, "missing")
    inactive = create_request(client, "inactive")
    assert unknown == inactive == {"message": "Solicitação processada.", "request_code": None}
    with app.state.session_factory() as session:
        assert not list(session.scalars(select(AssistedRecoveryRequest)))


def test_valid_authorization_changes_password_consumes_and_revokes(assisted_context):
    client, app, private = assisted_context
    with app.state.session_factory() as session:
        user = session.scalar(select(User).where(User.username == "active"))
        _, old_key = generate_key(session, user)
        old_key_id = old_key.id
        session.commit()
    login = client.post(
        "/api/v1/auth/login", json={"identifier": "active", "password": OLD_PASSWORD}
    ).json()
    code, request = valid_authorization(client, private)
    assert client.post(
        "/api/v1/auth/assisted-recovery/validate", json={"authorization": code}
    ).json() == {"valid": True}
    completed = client.post(
        "/api/v1/auth/assisted-recovery/complete",
        json={"authorization": code, "new_password": NEW_PASSWORD},
    )
    assert completed.status_code == 204
    assert not completed.content
    with app.state.session_factory() as session:
        user = session.get(User, request["user_id"])
        assert user.personal_recovery_key_pending is True
        assert session.get(PersonalRecoveryKey, old_key_id).revoked_at is not None
    assert client.post(
        "/api/v1/auth/login", json={"identifier": "active", "password": OLD_PASSWORD}
    ).status_code == 401
    first_login = client.post(
        "/api/v1/auth/login", json={"identifier": "active", "password": NEW_PASSWORD}
    )
    assert first_login.status_code == 200
    replacement = first_login.json()["personal_recovery_key"]
    assert replacement.startswith("FIN-")
    assert "personal_recovery_key" not in client.post(
        "/api/v1/auth/login", json={"identifier": "active", "password": NEW_PASSWORD}
    ).json()
    assert client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    ).status_code == 401
    with app.state.session_factory() as session:
        item = session.scalar(select(AssistedRecoveryRequest))
        user = session.get(User, request["user_id"])
        log = session.scalar(select(AuditLog).where(
            AuditLog.action == "PASSWORD_ASSISTED_RECOVERY_COMPLETED"
        ))
        assert item.used_at is not None
        assert verify_password(NEW_PASSWORD, user.password_hash)
        assert user.personal_recovery_key_pending is False
        assert session.get(PersonalRecoveryKey, old_key_id).revoked_at is not None
        assert len(list(session.scalars(select(PersonalRecoveryKey)))) == 2
        assert log and "authorization" not in json.dumps(log.details or {}).casefold()


@pytest.mark.parametrize(
    "changes, message",
    [
        ({"exp": 1}, "expirou"),
        ({"product": "BOOKMAKER"}, "não pertence ao Finance"),
        ({"environment": "SERVER"}, "outro ambiente"),
        ({"request_id": "different"}, "não localizada"),
        ({"user_id": 999}, "não corresponde ao usuário"),
    ],
)
def test_invalid_authorization_bindings_are_rejected(
    assisted_context, changes, message
):
    client, _, private = assisted_context
    code, _ = valid_authorization(client, private, **changes)
    response = client.post(
        "/api/v1/auth/assisted-recovery/validate", json={"authorization": code}
    )
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_missing_product_and_invalid_signature_are_rejected(assisted_context):
    client, _, private = assisted_context
    code, request = valid_authorization(client, private)
    payload = json.loads(b64decode(code.split(".", 1)[0]))
    payload.pop("product")
    missing = authorization(private, payload)
    assert client.post(
        "/api/v1/auth/assisted-recovery/validate", json={"authorization": missing}
    ).status_code == 400
    invalid = f"{code.rsplit('.', 1)[0]}.{b64encode(b'x' * 64)}"
    response = client.post(
        "/api/v1/auth/assisted-recovery/validate", json={"authorization": invalid}
    )
    assert response.status_code == 400
    assert "Assinatura" in response.json()["detail"]


def test_nonexistent_request_is_rejected(assisted_context):
    client, _, private = assisted_context
    payload = {
        "v": 1, "product": "FINANCE", "environment": "DEV",
        "request_id": "not-persisted", "user_id": 1,
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
    }
    response = client.post(
        "/api/v1/auth/assisted-recovery/validate",
        json={"authorization": authorization(private, payload)},
    )
    assert response.status_code == 400
    assert "não localizada" in response.json()["detail"]


def test_used_authorization_and_invalid_password_are_rejected(assisted_context):
    client, _, private = assisted_context
    code, _ = valid_authorization(client, private)
    weak = client.post(
        "/api/v1/auth/assisted-recovery/complete",
        json={"authorization": code, "new_password": "abcdef"},
    )
    assert weak.status_code == 422
    assert client.post(
        "/api/v1/auth/assisted-recovery/complete",
        json={"authorization": code, "new_password": NEW_PASSWORD},
    ).status_code == 204
    reused = client.post(
        "/api/v1/auth/assisted-recovery/complete",
        json={"authorization": code, "new_password": "Finance3"},
    )
    assert reused.status_code == 400
    assert "já foi utilizada" in reused.json()["detail"]
