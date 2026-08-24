from app.core.config import get_settings


def test_default_settings_are_available() -> None:
    settings = get_settings()
    assert settings.app_name
    assert settings.database_url.startswith(("sqlite", "postgresql"))

