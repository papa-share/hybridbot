import pytest

from chatbot.config import config, validate_config


def test_config_loads():
    assert config.OLLAMA_URL.startswith("http")
    assert config.MAX_FILES >= 1
    assert config.MAX_IMAGE_SIZE_MB >= 1


def test_production_requires_secrets(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("AUTH_MODE", "password")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CHAINLIT_AUTH_SECRET", raising=False)
    monkeypatch.delenv("AUTH_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="DATABASE_URL"):
        validate_config()

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    with pytest.raises(ValueError, match="CHAINLIT_AUTH_SECRET"):
        validate_config()

    monkeypatch.setenv("CHAINLIT_AUTH_SECRET", "secret-test")
    with pytest.raises(ValueError, match="AUTH_PASSWORD"):
        validate_config()


def test_invalid_auth_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "invalid")
    with pytest.raises(ValueError, match="AUTH_MODE"):
        validate_config()
