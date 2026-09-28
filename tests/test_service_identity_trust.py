"""Configuration tests for the Control Center public trust anchor."""

import base64

import pytest

from finance_server.app_factory import create_app
from finance_server.config import (
    ServerSettings,
    get_control_center_identity_trust,
)


KID = "cc-ed25519-b189c79a767b6f68"
PUBLIC_KEY_B64 = "l9ch1W86s3WTt/et8PkhSzM+XTMzRN8l4wFrZ8aupY8="


def _set_identity_environment(monkeypatch, *, enabled, kid, public_key):
    monkeypatch.setenv("CONTROL_CENTER_IDENTITY_ENABLED", enabled)
    monkeypatch.setenv("CONTROL_CENTER_IDENTITY_KID", kid)
    monkeypatch.setenv(
        "CONTROL_CENTER_IDENTITY_PUBLIC_KEY_B64",
        public_key,
    )


def test_valid_identity_trust_is_loaded(monkeypatch):
    _set_identity_environment(
        monkeypatch,
        enabled="true",
        kid=KID,
        public_key=PUBLIC_KEY_B64,
    )

    trust = get_control_center_identity_trust()

    assert trust.enabled is True
    assert trust.kid == KID
    assert trust.public_key_b64 == PUBLIC_KEY_B64


def test_disabled_identity_remains_backward_compatible(monkeypatch):
    _set_identity_environment(
        monkeypatch,
        enabled="false",
        kid="",
        public_key="",
    )

    trust = get_control_center_identity_trust()

    assert trust.enabled is False
    assert trust.kid == ""
    assert trust.public_key_b64 == ""


def test_enabled_identity_requires_kid(monkeypatch):
    _set_identity_environment(
        monkeypatch,
        enabled="true",
        kid="",
        public_key=PUBLIC_KEY_B64,
    )

    with pytest.raises(RuntimeError, match="IDENTITY_KID"):
        get_control_center_identity_trust()


def test_enabled_identity_requires_public_key(monkeypatch):
    _set_identity_environment(
        monkeypatch,
        enabled="true",
        kid=KID,
        public_key="",
    )

    with pytest.raises(RuntimeError, match="PUBLIC_KEY_B64"):
        get_control_center_identity_trust()


def test_invalid_base64_is_rejected_without_echoing_value(monkeypatch):
    invalid_value = "not-a-public-key-secret-value"
    _set_identity_environment(
        monkeypatch,
        enabled="true",
        kid=KID,
        public_key=invalid_value,
    )

    with pytest.raises(RuntimeError) as captured:
        get_control_center_identity_trust()

    assert invalid_value not in str(captured.value)


def test_public_key_must_decode_to_32_bytes(monkeypatch):
    _set_identity_environment(
        monkeypatch,
        enabled="true",
        kid=KID,
        public_key=base64.b64encode(b"x" * 31).decode("ascii"),
    )

    with pytest.raises(RuntimeError, match="32-byte"):
        get_control_center_identity_trust()


def test_direct_server_settings_reject_partial_identity_configuration():
    with pytest.raises(RuntimeError, match="IDENTITY_KID"):
        ServerSettings(
            database_url="sqlite+pysqlite:///:memory:",
            secret_key="S" * 48,
            control_center_identity_enabled=True,
            control_center_identity_kid="",
            control_center_identity_public_key_b64=PUBLIC_KEY_B64,
        )


def test_valid_identity_trust_allows_application_creation():
    settings = ServerSettings(
        database_url="sqlite+pysqlite:///:memory:",
        secret_key="S" * 48,
        control_center_identity_enabled=True,
        control_center_identity_kid=KID,
        control_center_identity_public_key_b64=PUBLIC_KEY_B64,
    )

    app = create_app(settings=settings)

    assert app is not None
