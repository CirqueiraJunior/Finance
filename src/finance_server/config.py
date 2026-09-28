from dataclasses import dataclass
import base64
import binascii
import os


@dataclass(frozen=True, slots=True)
class ControlCenterIdentityTrust:
    enabled: bool
    kid: str
    public_key_b64: str


@dataclass(frozen=True, slots=True)
class ServerSettings:
    database_url: str
    secret_key: str
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    reset_token_minutes: int = 30
    assisted_recovery_request_minutes: int = 1440
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    control_center_identity_enabled: bool = False
    control_center_identity_kid: str = ""
    control_center_identity_public_key_b64: str = ""

    def __post_init__(self) -> None:
        _validate_control_center_identity_trust(
            self.control_center_identity_enabled,
            self.control_center_identity_kid,
            self.control_center_identity_public_key_b64,
        )


def get_control_center_identity_trust() -> ControlCenterIdentityTrust:
    """Load the Control Center public trust anchor from the environment."""

    enabled = (
        os.getenv("CONTROL_CENTER_IDENTITY_ENABLED", "false")
        .strip()
        .casefold()
        in {"1", "true", "yes", "on"}
    )
    kid = os.getenv("CONTROL_CENTER_IDENTITY_KID", "").strip()
    public_key_b64 = os.getenv(
        "CONTROL_CENTER_IDENTITY_PUBLIC_KEY_B64", ""
    ).strip()
    _validate_control_center_identity_trust(enabled, kid, public_key_b64)
    return ControlCenterIdentityTrust(enabled, kid, public_key_b64)


def _validate_control_center_identity_trust(
    enabled: bool,
    kid: str,
    public_key_b64: str,
) -> None:
    if not enabled:
        return
    if not kid:
        raise RuntimeError(
            "CONTROL_CENTER_IDENTITY_KID must be configured when identity "
            "exchange is enabled."
        )
    if not public_key_b64:
        raise RuntimeError(
            "CONTROL_CENTER_IDENTITY_PUBLIC_KEY_B64 must be configured when "
            "identity exchange is enabled."
        )
    try:
        public_key = base64.b64decode(public_key_b64, validate=True)
    except (ValueError, binascii.Error) as error:
        raise RuntimeError(
            "CONTROL_CENTER_IDENTITY_PUBLIC_KEY_B64 is invalid."
        ) from error
    if len(public_key) != 32:
        raise RuntimeError(
            "CONTROL_CENTER_IDENTITY_PUBLIC_KEY_B64 must encode a 32-byte "
            "Ed25519 public key."
        )


def get_server_settings() -> ServerSettings:
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY do servidor deve possuir ao menos 32 caracteres.")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL do servidor não configurada. "
            "Use finance-dev ou finance-server."
        )
    identity_trust = get_control_center_identity_trust()
    return ServerSettings(
        database_url=database_url,
        secret_key=secret,
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15")),
        refresh_token_days=int(os.getenv("REFRESH_TOKEN_DAYS", "7")),
        reset_token_minutes=int(os.getenv("RESET_TOKEN_MINUTES", "30")),
        assisted_recovery_request_minutes=int(
            os.getenv("ASSISTED_RECOVERY_REQUEST_MINUTES", "1440")
        ),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", ""),
        control_center_identity_enabled=identity_trust.enabled,
        control_center_identity_kid=identity_trust.kid,
        control_center_identity_public_key_b64=identity_trust.public_key_b64,
    )
