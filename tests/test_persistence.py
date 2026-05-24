import asyncio

import pytest

from chatbot.persistence import (
    _LEGACY_SESSION_MODEL,
    SESSION_UI_MODEL,
    _step_dict_from_row,
    default_chat_prefs,
    prefs_from_settings,
    read_chat_prefs,
    thread_is_shared,
    write_chat_prefs,
)


def test_default_chat_prefs():
    prefs = default_chat_prefs("[cloud] gpt-oss:120b-cloud")
    assert prefs["model"] == "[cloud] gpt-oss:120b-cloud"
    assert prefs["temperature"] == 0.4
    assert prefs["max_tokens"] == 1024


def test_step_dict_from_row_favorite():
    row = {
        "step_id": "id-1",
        "step_name": "User",
        "step_type": "user_message",
        "step_threadid": "thread-1",
        "step_parentid": None,
        "step_streaming": False,
        "step_metadata": {"favorite": True},
        "step_showinput": "false",
        "step_output": "Bonjour",
    }
    step = _step_dict_from_row(row)
    assert step is not None
    assert step["output"] == "Bonjour"


def test_step_dict_from_row_not_favorite():
    row = {
        "step_id": "id-1",
        "step_name": "User",
        "step_type": "user_message",
        "step_threadid": "thread-1",
        "step_parentid": None,
        "step_metadata": {"favorite": False},
        "step_showinput": "false",
        "step_output": "Bonjour",
    }
    assert _step_dict_from_row(row) is None


def test_thread_is_shared():
    assert thread_is_shared({"metadata": {"is_shared": True}})
    assert not thread_is_shared({"metadata": {"is_shared": False}})
    assert not thread_is_shared({"metadata": "{}"})
    assert thread_is_shared({"metadata": '{"is_shared": true}'})


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
def mock_chainlit(monkeypatch):
    user_session = _MockUserSession()
    context = _MockContext()
    monkeypatch.setattr("chatbot.persistence.cl.user_session", user_session)
    monkeypatch.setattr("chatbot.persistence.cl.context", context)
    return user_session, context


def test_write_chat_prefs(mock_chainlit):
    user_session, context = mock_chainlit
    prefs = default_chat_prefs("[cloud] gpt-oss:120b-cloud")
    prefs["temperature"] = 0.6

    write_chat_prefs(prefs)

    assert user_session.get(SESSION_UI_MODEL) == "[cloud] gpt-oss:120b-cloud"
    assert user_session.get("temperature") == 0.6
    assert context.session.chat_settings["model"] == "[cloud] gpt-oss:120b-cloud"


def test_read_chat_prefs_legacy_model_name(mock_chainlit, monkeypatch):
    user_session, _ = mock_chainlit
    user_session.set(_LEGACY_SESSION_MODEL, "[local] granite4:latest")
    user_session.set("max_tokens", 2048)
    monkeypatch.setattr("chatbot.persistence.config.DATABASE_URL", "")

    prefs = asyncio.run(read_chat_prefs("default-model", use_user_store=False))

    assert prefs["model"] == "[local] granite4:latest"
    assert prefs["max_tokens"] == 2048


def test_prefs_from_settings(mock_chainlit):
    user_session, _ = mock_chainlit
    user_session.set(SESSION_UI_MODEL, "[cloud] old-model")

    prefs = prefs_from_settings({"model": "[cloud] new-model", "temperature": 0.2})

    assert prefs["model"] == "[cloud] new-model"
    assert prefs["temperature"] == 0.2
