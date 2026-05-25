import asyncio
import os
import time

import pytest

from chatbot import llm
from chatbot.document_load import DocumentLoadResult
from chatbot.llm import (
    _classify_ollama_error,
    _skip_model,
    _vision_pool,
    build_model_labels,
    get_catalog,
    invalidate_catalog,
    model_from_label,
    process_llm_request,
)


def test_skip_embed_ocr():
    assert _skip_model("nomic-embed-text:latest")
    assert _skip_model("glm-ocr:q8_0")
    assert not _skip_model("qwen3-vl:235b-cloud")


def test_model_from_label():
    assert model_from_label("[cloud] nemotron-3-super:cloud") == "nemotron-3-super:cloud"
    assert model_from_label("granite4:latest") == "granite4:latest"


def test_vision_pool_cloud_first():
    catalog = {
        "chat_local": [],
        "chat_cloud": [],
        "vision_local": ["gemma4:e2b"],
        "vision_cloud": ["devstral-small-2:24b-cloud", "gemma4:31b-cloud"],
    }
    assert _vision_pool(catalog) == [
        "devstral-small-2:24b-cloud",
        "gemma4:31b-cloud",
        "gemma4:e2b",
    ]


def test_build_model_labels():
    catalog = {
        "chat_local": ["granite4:latest"],
        "chat_cloud": ["nemotron-3-super:cloud"],
        "vision_local": ["gemma4:e2b"],
        "vision_cloud": ["qwen3-vl:235b-cloud"],
    }
    labels = build_model_labels(catalog)
    assert labels == [
        "[local] granite4:latest",
        "[vision local] gemma4:e2b",
        "[cloud] nemotron-3-super:cloud",
        "[vision cloud] qwen3-vl:235b-cloud",
    ]


def test_classify_ollama_error_subscription():
    msg, retryable = _classify_ollama_error(Exception("403 subscription required"))
    assert "abonnement" in msg.lower()
    assert retryable is True


def test_classify_ollama_error_image():
    msg, retryable = _classify_ollama_error(Exception("does not support image input"))
    assert "vision" in msg.lower()
    assert retryable is True


def test_classify_ollama_error_not_found():
    msg, retryable = _classify_ollama_error(Exception("404 model not found"), "ghost:latest")
    assert "ghost:latest" in msg
    assert retryable is False


def test_classify_ollama_error_connection():
    msg, retryable = _classify_ollama_error(Exception("connection refused"))
    assert "ollama" in msg.lower()
    assert retryable is False


def test_classify_ollama_error_invalid_format():
    msg, retryable = _classify_ollama_error(Exception("failed to process inputs: invalid format"))
    assert msg == "Erreur Ollama."
    assert retryable is False


def test_process_llm_request_web_failure(monkeypatch):
    async def fake_search_web(_query, on_event=None):
        return "Recherche web indisponible.", False, []

    monkeypatch.setattr("chatbot.llm.search_web", fake_search_web)

    result = asyncio.run(
        process_llm_request(
            input_message="actualités IA",
            interaction=[{"role": "system", "content": "test"}],
            ui_model_label="granite4:latest",
            web_search_enabled=True,
        )
    )

    assert result["error"] is True
    assert "indisponible" in result["message"]["content"].lower()


def test_process_llm_request_empty_pdf(monkeypatch, temp_dir):
    pdf_path = os.path.join(temp_dir, "scan.pdf")
    with open(pdf_path, "wb") as handle:
        handle.write(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n")

    async def fake_load(path, mime, name, flow_callback):
        return DocumentLoadResult(error="Erreur extraction: échec test")

    monkeypatch.setattr("chatbot.llm._load_document_text", fake_load)

    result = asyncio.run(
        process_llm_request(
            input_message="Résume le PDF",
            interaction=[{"role": "system", "content": "test"}],
            ui_model_label="granite4:latest",
            files=[(pdf_path, "application/pdf", "scan.pdf")],
        )
    )

    assert result["error"] is True
    assert "échec test" in result["message"]["content"].lower()


def test_read_document_text_file(sample_text_file):
    from chatbot.llm import _read_document as read_document

    result = asyncio.run(read_document(sample_text_file, "text/plain", "sample.txt"))
    assert result.ok
    assert "Contenu de test" in result.text


@pytest.fixture(autouse=True)
def reset_catalog():
    invalidate_catalog()
    yield
    invalidate_catalog()


def _sample_catalog() -> dict[str, list[str]]:
    return {
        "chat_local": ["granite4:latest"],
        "chat_cloud": ["nemotron-3-super:cloud"],
        "vision_local": [],
        "vision_cloud": [],
        "tools_local": [],
        "tools_cloud": [],
    }


def test_invalidate_catalog_clears_cache(monkeypatch):
    llm._catalog = _sample_catalog()
    llm._catalog_fetched_at = 1.0

    invalidate_catalog()

    assert llm._catalog is None
    assert llm._catalog_fetched_at == 0.0


def test_get_catalog_uses_cache_within_ttl(monkeypatch):
    llm._catalog = _sample_catalog()
    llm._catalog_fetched_at = time.monotonic()
    monkeypatch.setattr("chatbot.llm.config.OLLAMA_CATALOG_TTL", 300)

    def fail_list():
        raise AssertionError("ollama.list ne devrait pas être appelé")

    monkeypatch.setattr("chatbot.llm.ollama.list", fail_list)

    catalog = asyncio.run(get_catalog(refresh=False))

    assert catalog == _sample_catalog()


def test_get_catalog_refreshes_when_stale(monkeypatch):
    llm._catalog = {
        "chat_local": ["old:latest"],
        "chat_cloud": [],
        "vision_local": [],
        "vision_cloud": [],
        "tools_local": [],
        "tools_cloud": [],
    }
    llm._catalog_fetched_at = time.monotonic() - 400
    monkeypatch.setattr("chatbot.llm.config.OLLAMA_CATALOG_TTL", 300)

    listed = type("Listed", (), {"models": [type("Model", (), {"model": "granite4:latest"})()]})()

    monkeypatch.setattr("chatbot.llm.ollama.list", lambda: listed)

    async def fake_caps(_name: str):
        return ["completion"]

    monkeypatch.setattr("chatbot.llm._capabilities", fake_caps)

    catalog = asyncio.run(get_catalog(refresh=False))

    assert catalog["chat_local"] == ["granite4:latest"]
