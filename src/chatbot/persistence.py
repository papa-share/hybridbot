import json
from typing import Any

import chainlit as cl
from chainlit.data import get_data_layer as get_active_data_layer
from chainlit.data.sql_alchemy import SQLAlchemyDataLayer
from chainlit.step import StepDict
from chainlit.user import User

from chatbot.config import config

CHAT_PREFS_KEY = "chat_prefs"
PREF_FIELDS = ("model", "temperature", "top_p", "max_tokens")
SESSION_UI_MODEL = "ui_model_label"
_LEGACY_SESSION_MODEL = "model_name"

# Chainlit utilise LIKE sur metadata (jsonb), invalide en PostgreSQL.
_FAVORITE_STEPS_SQL = """
SELECT
    s."id" AS step_id,
    s."name" AS step_name,
    s."type" AS step_type,
    s."threadId" AS step_threadid,
    s."parentId" AS step_parentid,
    s."streaming" AS step_streaming,
    s."waitForAnswer" AS step_waitforanswer,
    s."isError" AS step_iserror,
    s."metadata" AS step_metadata,
    s."tags" AS step_tags,
    s."input" AS step_input,
    s."output" AS step_output,
    s."createdAt" AS step_createdat,
    s."start" AS step_start,
    s."end" AS step_end,
    s."generation" AS step_generation,
    s."showInput" AS step_showinput,
    s."language" AS step_language
FROM steps s
JOIN threads t ON s."threadId" = t.id
WHERE t."userId" = :user_id
  AND s."metadata" @> CAST(:favorite_filter AS jsonb)
ORDER BY s."createdAt" DESC
"""


def _parse_json_dict(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _step_dict_from_row(row: dict[str, Any]) -> StepDict | None:
    meta_dict = _parse_json_dict(row.get("step_metadata"))
    if not meta_dict or not meta_dict.get("favorite"):
        return None

    show_input = row.get("step_showinput")
    return StepDict(
        id=row["step_id"],
        name=row["step_name"],
        type=row["step_type"],
        threadId=row["step_threadid"],
        parentId=row["step_parentid"],
        streaming=row.get("step_streaming", False),
        waitForAnswer=row.get("step_waitforanswer"),
        isError=row.get("step_iserror"),
        metadata=meta_dict,
        tags=row.get("step_tags"),
        input=row.get("step_input", "") if show_input not in (None, "false") else "",
        output=row.get("step_output", ""),
        createdAt=row.get("step_createdat"),
        start=row.get("step_start"),
        end=row.get("step_end"),
        generation=row.get("step_generation"),
        showInput=show_input,
        language=row.get("step_language"),
        feedback=None,
    )


class PostgresDataLayer(SQLAlchemyDataLayer):
    """Couche PostgreSQL avec correctif favoris (jsonb @> au lieu de LIKE Chainlit)."""

    async def get_favorite_steps(self, user_id: str) -> list[StepDict]:
        result = await self.execute_sql(
            _FAVORITE_STEPS_SQL,
            {"user_id": user_id, "favorite_filter": '{"favorite": true}'},
        )
        if not isinstance(result, list):
            return []
        steps: list[StepDict] = []
        for row in result:
            step = _step_dict_from_row(row)
            if step:
                steps.append(step)
        return steps


def thread_is_shared(thread: dict[str, Any]) -> bool:
    meta = _parse_json_dict(thread.get("metadata") or {})
    return bool(meta and meta.get("is_shared"))


if config.DATABASE_URL:

    @cl.data_layer
    def get_data_layer():
        return PostgresDataLayer(conninfo=config.DATABASE_URL)


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


def _overlay_prefs(prefs: dict[str, Any], mapping: dict[str, Any]) -> dict[str, Any]:
    merged = dict(prefs)
    for key in PREF_FIELDS:
        value = mapping.get(key)
        if value is not None:
            merged[key] = value
    return merged


def read_session_ui_model(fallback: str) -> str:
    ui_model = cl.user_session.get(SESSION_UI_MODEL)
    if ui_model:
        return str(ui_model).strip()
    legacy = cl.user_session.get(_LEGACY_SESSION_MODEL)
    if legacy:
        migrated = str(legacy).strip()
        cl.user_session.set(SESSION_UI_MODEL, migrated)
        cl.user_session.set(_LEGACY_SESSION_MODEL, None)
        return migrated
    return fallback


def _session_pref_mapping() -> dict[str, Any]:
    mapping = dict(_session_chat_settings())
    ui_model = read_session_ui_model("")
    if ui_model:
        mapping["model"] = ui_model
    for key in PREF_FIELDS[1:]:
        value = cl.user_session.get(key)
        if value is not None:
            mapping[key] = value
    return mapping


async def read_chat_prefs(default_model: str, *, use_user_store: bool) -> dict[str, Any]:
    prefs = _overlay_prefs(default_chat_prefs(default_model), _session_pref_mapping())
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

    return _overlay_prefs(prefs, stored)


def write_chat_prefs(prefs: dict[str, Any]) -> None:
    cl.user_session.set(SESSION_UI_MODEL, prefs["model"])
    cl.user_session.set("temperature", prefs["temperature"])
    cl.user_session.set("top_p", prefs["top_p"])
    cl.user_session.set("max_tokens", prefs["max_tokens"])

    session = getattr(cl.context, "session", None)
    if session is not None:
        session.chat_settings = {key: prefs[key] for key in PREF_FIELDS}


def prefs_from_settings(settings: dict[str, Any]) -> dict[str, Any]:
    mapping = _session_pref_mapping()
    for key in PREF_FIELDS:
        if settings.get(key) is not None:
            mapping[key] = settings[key]
    default_model = mapping.get("model") or config.DEFAULT_MODEL
    return _overlay_prefs(default_chat_prefs(default_model), mapping)


async def persist_chat_prefs(prefs: dict[str, Any]) -> None:
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
