from app.core import config
from app.core.config import get_settings


def test_default_settings_are_available() -> None:
    settings = get_settings()
    assert settings.app_name
    assert settings.database_url.startswith(("sqlite", "postgresql"))


def test_frozen_desktop_defaults_to_local_service(monkeypatch) -> None:
    config.get_settings.cache_clear()
    monkeypatch.setattr(config, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.delenv("FINANCE_API_URL", raising=False)

    settings = config.get_settings()

    assert settings.api_url == "http://127.0.0.1:8000"
    config.get_settings.cache_clear()


def test_explicit_api_url_has_priority_in_frozen_desktop(monkeypatch) -> None:
    config.get_settings.cache_clear()
    monkeypatch.setattr(config, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    monkeypatch.setenv("FINANCE_API_URL", "http://127.0.0.1:9123/")

    settings = config.get_settings()

    assert settings.api_url == "http://127.0.0.1:9123"
    config.get_settings.cache_clear()
