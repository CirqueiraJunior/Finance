import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import select

from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.models import AuditLog, RefreshSession, User, UserRole
from finance_server.security import hash_password


PASSWORD = "Strong!Pass123"


def canonical_time(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def signer_material():
    private = Ed25519PrivateKey.generate()

    public = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    kid = f"cc-ed25519-{hashlib.sha256(public).hexdigest()[:16]}"

    return (
        private,
        kid,
        base64.b64encode(public).decode("ascii"),
    )


def build_proof(
    private,
    kid,
    nonce,
    *,
    email="gestor@example.com",
    audience="finance",
    active=True,
    expired=False,
    product_access=None,
):
    now = datetime.now(timezone.utc)

    issued = (
        now - timedelta(minutes=5)
        if expired
        else now
    )

    claims = {
        "active": active,
        "aud": audience,
        "email": email,
        "exp": canonical_time(
            issued + timedelta(seconds=90)
        ),
        "iat": canonical_time(issued),
        "iss": "ja-technology-control-center",
        "jti": "proof-jti-001",
        "name": "Gestor",
        "nonce": nonce,
        "product_access": (
            ["finance"]
            if product_access is None
            else product_access
        ),
        "sid": "central-session-001",
        "sub": "central-user-001",
    }

    payload = json.dumps(
        claims,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")

    document = {
        "alg": "Ed25519",
        "kid": kid,
        "payload": base64.b64encode(
            payload
        ).decode("ascii"),
        "signature": base64.b64encode(
            private.sign(payload)
        ).decode("ascii"),
        "v": 1,
    }

    return json.dumps(
        document,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def make_context(tmp_path):
    private, kid, public_b64 = signer_material()

    settings = ServerSettings(
        database_url=(
            f"sqlite:///{(tmp_path / 'exchange.db').as_posix()}"
        ),
        secret_key="s" * 64,
        access_token_minutes=15,
        refresh_token_days=7,
        control_center_identity_enabled=True,
        control_center_identity_kid=kid,
        control_center_identity_public_key_b64=public_b64,
    )

    app = create_app(
        settings,
        create_schema=True,
    )

    with app.state.session_factory() as session:
        session.add_all([
            User(
                nome="Gestor",
                email="gestor@example.com",
                username="gestor",
                password_hash=hash_password(PASSWORD),
                perfil=UserRole.MANAGER.value,
                ativo=True,
            ),
            User(
                nome="Inativo",
                email="off@example.com",
                username="off",
                password_hash=hash_password(PASSWORD),
                perfil=UserRole.READ_ONLY.value,
                ativo=False,
            ),
        ])

        session.commit()

    return app, private, kid


def challenge(client: TestClient) -> str:
    response = client.post(
        "/api/v1/auth/identity-challenge"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["nonce"]
    assert data["expires_in"] == 60

    return data["nonce"]


def test_identity_exchange_returns_native_finance_session(tmp_path):
    app, private, kid = make_context(tmp_path)

    with TestClient(app) as client:
        nonce = challenge(client)

        response = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": build_proof(
                    private,
                    kid,
                    nonce,
                ),
            },
        )

        assert response.status_code == 200

        pair = response.json()

        assert pair["access_token"]
        assert pair["refresh_token"]
        assert pair["token_type"] == "bearer"

        me = client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization":
                    f"Bearer {pair['access_token']}"
            },
        )

        assert me.status_code == 200
        assert me.json()["email"] == "gestor@example.com"
        assert me.json()["perfil"] == "GESTOR"

        with app.state.session_factory() as session:
            user = session.scalar(
                select(User).where(
                    User.email == "gestor@example.com"
                )
            )

            assert user is not None
            assert user.ultimo_login is not None

            refresh = session.scalar(
                select(RefreshSession).where(
                    RefreshSession.user_id == user.id
                )
            )

            assert refresh is not None

            audit = session.scalar(
                select(AuditLog).where(
                    AuditLog.action
                    == "IDENTITY_EXCHANGE"
                )
            )

            assert audit is not None
            assert audit.user_id == user.id
            assert (
                audit.details["central_sub"]
                == "central-user-001"
            )

    app.state.engine.dispose()


def test_identity_exchange_challenge_is_single_use(tmp_path):
    app, private, kid = make_context(tmp_path)

    with TestClient(app) as client:
        nonce = challenge(client)

        signed = build_proof(
            private,
            kid,
            nonce,
        )

        first = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": signed,
            },
        )

        second = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": signed,
            },
        )

        assert first.status_code == 200
        assert second.status_code == 401

    app.state.engine.dispose()


def test_identity_exchange_rejects_wrong_audience(tmp_path):
    app, private, kid = make_context(tmp_path)

    with TestClient(app) as client:
        nonce = challenge(client)

        response = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": build_proof(
                    private,
                    kid,
                    nonce,
                    audience="bookmaker",
                ),
            },
        )

        assert response.status_code == 401

    app.state.engine.dispose()


def test_identity_exchange_rejects_missing_finance_access(tmp_path):
    app, private, kid = make_context(tmp_path)

    with TestClient(app) as client:
        nonce = challenge(client)

        response = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": build_proof(
                    private,
                    kid,
                    nonce,
                    product_access=["bookmaker"],
                ),
            },
        )

        assert response.status_code == 401

    app.state.engine.dispose()


def test_identity_exchange_rejects_expired_proof(tmp_path):
    app, private, kid = make_context(tmp_path)

    with TestClient(app) as client:
        nonce = challenge(client)

        response = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": build_proof(
                    private,
                    kid,
                    nonce,
                    expired=True,
                ),
            },
        )

        assert response.status_code == 401

    app.state.engine.dispose()


def test_identity_exchange_rejects_invalid_signature(tmp_path):
    app, _, kid = make_context(tmp_path)

    attacker = Ed25519PrivateKey.generate()

    with TestClient(app) as client:
        nonce = challenge(client)

        response = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": build_proof(
                    attacker,
                    kid,
                    nonce,
                ),
            },
        )

        assert response.status_code == 401

    app.state.engine.dispose()


def test_identity_exchange_rejects_wrong_nonce(tmp_path):
    app, private, kid = make_context(tmp_path)

    with TestClient(app) as client:
        nonce = challenge(client)

        response = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": build_proof(
                    private,
                    kid,
                    "different-nonce",
                ),
            },
        )

        assert response.status_code == 401

    app.state.engine.dispose()


def test_identity_exchange_rejects_inactive_finance_user(tmp_path):
    app, private, kid = make_context(tmp_path)

    with TestClient(app) as client:
        nonce = challenge(client)

        response = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": build_proof(
                    private,
                    kid,
                    nonce,
                    email="off@example.com",
                ),
            },
        )

        assert response.status_code == 401

    app.state.engine.dispose()


def test_identity_exchange_rejects_unknown_finance_user(tmp_path):
    app, private, kid = make_context(tmp_path)

    with TestClient(app) as client:
        nonce = challenge(client)

        response = client.post(
            "/api/v1/auth/identity-exchange",
            json={
                "nonce": nonce,
                "proof": build_proof(
                    private,
                    kid,
                    nonce,
                    email="unknown@example.com",
                ),
            },
        )

        assert response.status_code == 401

    app.state.engine.dispose()


def test_identity_exchange_disabled_by_default(tmp_path):
    settings = ServerSettings(
        database_url=(
            f"sqlite:///{(tmp_path / 'disabled.db').as_posix()}"
        ),
        secret_key="s" * 64,
    )

    app = create_app(
        settings,
        create_schema=True,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/auth/identity-challenge"
        )

        assert response.status_code == 404

    app.state.engine.dispose()
