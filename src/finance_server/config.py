from dataclasses import dataclass
import os


@dataclass(frozen=True, slots=True)
class ServerSettings:
    database_url: str
    secret_key: str
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    reset_token_minutes: int = 30
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""


def get_server_settings() -> ServerSettings:
    secret = os.getenv("SECRET_KEY", "")
    if len(secret) < 32:
        raise RuntimeError("SECRET_KEY do servidor deve possuir ao menos 32 caracteres.")
    return ServerSettings(
        database_url=os.getenv("DATABASE_URL", "postgresql+psycopg://finance@localhost/finance"),
        secret_key=secret,
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "15")),
        refresh_token_days=int(os.getenv("REFRESH_TOKEN_DAYS", "7")),
        reset_token_minutes=int(os.getenv("RESET_TOKEN_MINUTES", "30")),
        smtp_host=os.getenv("SMTP_HOST", ""),
        smtp_port=int(os.getenv("SMTP_PORT", "587")),
        smtp_user=os.getenv("SMTP_USER", ""),
        smtp_password=os.getenv("SMTP_PASSWORD", ""),
        smtp_from=os.getenv("SMTP_FROM", ""),
    )
