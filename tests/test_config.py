import os

import pytest

from chatbot.config import config, is_document_source, validate_config


def test_config_loads():
    assert config.OLLAMA_URL.startswith("http")
    assert config.MAX_FILES >= 1
    assert config.MAX_IMAGE_SIZE_MB >= 1


def test_is_document_source():
    assert is_document_source(name="readme.md")
    assert is_document_source(name="notes.TXT")
    assert is_document_source(name="doc.PDF")
    assert not is_document_source(name="script.exe")
    assert not is_document_source(name="image.png")


def test_is_pdf_source_by_mime_and_magic(temp_dir):
    from chatbot.config import file_is_pdf_bytes, is_pdf_source

    assert is_pdf_source(mime="application/pdf")
    assert is_pdf_source(name="paper.pdf")
    bin_path = os.path.join(temp_dir, "upload.bin")
    with open(bin_path, "wb") as handle:
        handle.write(b"%PDF-1.4\n")
    assert file_is_pdf_bytes(bin_path)
    assert is_pdf_source(path=bin_path)


def test_production_requires_secrets(monkeypatch):
    monkeypatch.setattr(config, "ENV", "production")
    monkeypatch.setattr(config, "AUTH_MODE", "password")
    monkeypatch.setattr(config, "DATABASE_URL", "")
    monkeypatch.setattr(config, "CHAINLIT_AUTH_SECRET", None)
    monkeypatch.setattr(config, "AUTH_PASSWORD", "")

    with pytest.raises(ValueError, match="DATABASE_URL"):
        validate_config()

    monkeypatch.setattr(config, "DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
    with pytest.raises(ValueError, match="CHAINLIT_AUTH_SECRET"):
        validate_config()

    monkeypatch.setattr(config, "CHAINLIT_AUTH_SECRET", "secret-test")
    validate_config()


def test_invalid_auth_mode(monkeypatch):
    monkeypatch.setattr(config, "AUTH_MODE", "invalid")
    with pytest.raises(ValueError, match="AUTH_MODE"):
        validate_config()
