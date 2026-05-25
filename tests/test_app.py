import asyncio

import pytest

from chatbot import llm
from chatbot.app import (
    MISSING_DOC_MSG,
    _expects_attachment,
    _interaction_from_thread,
    _prepare_settings,
    _session_params,
    on_settings_update,
)


class _MockUserSession:
    def __init__(self):
        self._store: dict[str, object] = {}

    def get(self, key: str, default=None):
        return self._store.get(key, default)

    def set(self, key: str, value) -> None:
        self._store[key] = value


class _MockContext:
    def __init__(self):
        self.session = type("Session", (), {"chat_settings": {}})()


@pytest.fixture
def mock_app_chainlit(monkeypatch):
    user_session = _MockUserSession()
    context = _MockContext()
    monkeypatch.setattr("chatbot.app.cl.user_session", user_session)
    monkeypatch.setattr("chatbot.app.cl.context", context)
    monkeypatch.setattr("chatbot.persistence.cl.user_session", user_session)
    monkeypatch.setattr("chatbot.persistence.cl.context", context)
    return user_session, context


@pytest.fixture(autouse=True)
def reset_catalog():
    llm.invalidate_catalog()
    yield
    llm.invalidate_catalog()


def test_expects_attachment():
    assert _expects_attachment("Résume le document joint")
    assert _expects_attachment("Voici mon PDF joint")
    assert _expects_attachment("Le fichier joint contient")
    assert not _expects_attachment("Bonjour")
    assert not _expects_attachment("")


def test_interaction_from_thread_rebuilds_history():
    thread = {
        "steps": [
            {"type": "user_message", "output": "Question"},
            {"type": "assistant_message", "output": "Réponse"},
            {"type": "tool", "output": "ignored"},
            {"type": "user_message", "output": ""},
        ]
    }
    interaction = _interaction_from_thread(thread)
    assert interaction[0]["role"] == "system"
    assert interaction[1] == {"role": "user", "content": "Question"}
    assert interaction[2] == {"role": "assistant", "content": "Réponse"}
    assert len(interaction) == 3


def test_session_params(mock_app_chainlit):
    user_session, _ = mock_app_chainlit
    user_session.set("ui_model_label", "[cloud] nemotron-3-super:cloud")
    user_session.set("temperature", 0.7)
    user_session.set("top_p", 0.8)
    user_session.set("max_tokens", 512)

    params = _session_params()

    assert params["ui_model_label"] == "[cloud] nemotron-3-super:cloud"
    assert params["temperature"] == 0.7
    assert params["top_p"] == 0.8
    assert params["max_tokens"] == 512


def test_session_params_migrates_legacy_model_name(mock_app_chainlit):
    user_session, _ = mock_app_chainlit
    user_session.set("model_name", "[local] granite4:latest")

    params = _session_params()

    assert params["ui_model_label"] == "[local] granite4:latest"
    assert user_session.get("ui_model_label") == "[local] granite4:latest"
    assert user_session.get("model_name") is None


@pytest.mark.parametrize(
    ("text", "expects_doc"),
    [
        ("Résume le document joint", True),
        ("Salut", False),
    ],
)
def test_missing_doc_message_constant(text, expects_doc):
    assert _expects_attachment(text) is expects_doc
    assert MISSING_DOC_MSG.startswith("Jointe")


async def _fake_catalog(*_args, **_kwargs):
    return {
        "chat_local": ["granite4:latest"],
        "chat_cloud": [],
        "vision_local": [],
        "vision_cloud": [],
        "tools_local": [],
        "tools_cloud": [],
    }


def test_prepare_settings_falls_back_when_model_missing(mock_app_chainlit, monkeypatch):
    user_session, _ = mock_app_chainlit
    user_session.set("ui_model_label", "[cloud] removed-model")
    monkeypatch.setattr("chatbot.app.get_catalog", _fake_catalog)
    monkeypatch.setattr("chatbot.app.config.DEFAULT_MODEL", "granite4:latest")

    models, prefs, idx = asyncio.run(_prepare_settings(refresh_models=True, use_user_store=False))

    assert models == ["[local] granite4:latest"]
    assert prefs["model"] == "[local] granite4:latest"
    assert idx == 0


def test_on_settings_update_reconciles_removed_model(mock_app_chainlit, monkeypatch):
    user_session, _ = mock_app_chainlit
    user_session.set("ui_model_label", "[cloud] ghost:latest")
    monkeypatch.setattr("chatbot.app.get_catalog", _fake_catalog)
    monkeypatch.setattr("chatbot.app.config.DEFAULT_MODEL", "granite4:latest")

    async def noop_persist(_prefs):
        return None

    monkeypatch.setattr("chatbot.app.persist_chat_prefs", noop_persist)

    asyncio.run(
        on_settings_update(
            {
                "model": "[cloud] ghost:latest",
                "temperature": 0.4,
                "top_p": 0.9,
                "max_tokens": 1024,
            }
        )
    )

    assert user_session.get("ui_model_label") == "[local] granite4:latest"
