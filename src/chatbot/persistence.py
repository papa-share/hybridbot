from typing import Any

import chainlit as cl
from chainlit.data import get_data_layer as get_active_data_layer
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.user import User

from chatbot.config import config

CHAT_PREFS_KEY = "chat_prefs"
PREF_FIELDS = ("model", "temperature", "top_p", "max_tokens")

if config.DATABASE_URL:

    @cl.data_layer
    def get_data_layer():
        return SQLAlchemyDataLayer(conninfo=config.DATABASE_URL)


def default_chat_prefs(default_model: str) -> dict[str, Any]:
    return {
        "model": default_model,
        "temperature": config.DEFAULT_TEMPERATURE,
        "top_p": config.DEFAULT_TOP_P,
        "max_tokens": config.DEFAULT_MAX_TOKENS,
    }


def _session_chat_settings() -> dict[str, Any]:
    session = getattr(cl.context, "session", None)
    if not session:
        return {}
    settings = getattr(session, "chat_settings", None)
    return dict(settings) if isinstance(settings, dict) else {}


def chat_prefs_from_session(default_model: str) -> dict[str, Any]:
    prefs = default_chat_prefs(default_model)
    for key, value in _session_chat_settings().items():
        if key in PREF_FIELDS and value is not None:
            prefs[key] = value

    model = cl.user_session.get("model_name")
    if model:
        prefs["model"] = model
    for key in ("temperature", "top_p", "max_tokens"):
        value = cl.user_session.get(key)
        if value is not None:
            prefs[key] = value
    return prefs


async def load_chat_prefs(default_model: str, *, use_user_store: bool) -> dict[str, Any]:
    prefs = chat_prefs_from_session(default_model)
    if not use_user_store or not config.DATABASE_URL:
        return prefs

    user = cl.user_session.get("user")
    if not user:
        return prefs

    data_layer = get_active_data_layer()
    if not data_layer:
        return prefs

    persisted = await data_layer.get_user(user.identifier)
    if not persisted or not persisted.metadata:
        return prefs

    stored = persisted.metadata.get(CHAT_PREFS_KEY)
    if not isinstance(stored, dict):
        return prefs

    for key in PREF_FIELDS:
        if key in stored and stored[key] is not None:
            prefs[key] = stored[key]
    return prefs


def apply_chat_prefs(prefs: dict[str, Any]) -> None:
    cl.user_session.set("model_name", prefs["model"])
    cl.user_session.set("temperature", prefs["temperature"])
    cl.user_session.set("top_p", prefs["top_p"])
    cl.user_session.set("max_tokens", prefs["max_tokens"])

    session = getattr(cl.context, "session", None)
    if session is not None:
        session.chat_settings = {key: prefs[key] for key in PREF_FIELDS}


async def save_chat_prefs(prefs: dict[str, Any]) -> None:
    if not config.DATABASE_URL:
        return

    user = cl.user_session.get("user")
    if not user:
        return

    data_layer = get_active_data_layer()
    if not data_layer:
        return

    stored = {key: prefs[key] for key in PREF_FIELDS}
    metadata: dict[str, Any] = dict(user.metadata or {})
    existing = await data_layer.get_user(user.identifier)
    if existing and existing.metadata:
        metadata = dict(existing.metadata)

    metadata[CHAT_PREFS_KEY] = stored
    await data_layer.create_user(User(identifier=user.identifier, metadata=metadata))


def model_index(models: list[str], model: str, fallback: int) -> int:
    if model in models:
        return models.index(model)
    return fallback
