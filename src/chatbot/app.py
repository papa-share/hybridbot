import os

os.environ["TRACELOOP_TRACING_ENABLED"] = "false"
os.environ["TRACELOOP_METRICS_ENABLED"] = "false"
os.environ["TRACELOOP_TRACE_CONTENT"] = "false"

import uuid
from typing import Any

import chainlit as cl
from chainlit.input_widget import Select, Slider

from chatbot.config import (
    DEFAULT_THREAD_NAME,
    DEFAULT_USER_ID,
    DEFAULT_USER_NAME,
    TEMPERATURE_STEP,
    TOP_P_STEP,
    config,
    logger,
)
from chatbot.llm import (
    build_model_labels,
    get_catalog,
    label_for_model,
    model_from_label,
    process_llm_request,
)
from chatbot.sqlite import SQLiteDataLayer
from chatbot.validators import validate_uploaded_files
from chatbot.web_flow import WebFlowUI

USE_DB = config.PERSISTENCE == "local"
cl.data_layer = SQLiteDataLayer(config.DB_PATH) if USE_DB else None

WEB_COMMAND = "Web"
WELCOME = "Salut. Qu'est-ce qu'on fait ?"

HELP = """Commandes :
- /model <nom> : changer de modèle
- /help : cette aide
- /clear : effacer la conversation
- /history : infos historique

Web : globe dans la barre (EXA_API_KEY requise)."""


if config.AUTH_MODE == "password":

    @cl.password_auth_callback
    async def auth_callback(username: str, password: str) -> cl.User | None:
        if config.AUTH_PASSWORD and password != config.AUTH_PASSWORD:
            return None

        user_id = username or DEFAULT_USER_ID
        user_name = username or DEFAULT_USER_NAME

        if not USE_DB:
            return cl.User(identifier=user_id, metadata={"role": "user", "name": user_name})

        user = await cl.data_layer.get_user(user_id)
        if not user:
            user = await cl.data_layer.create_user(
                {
                    "id": user_id,
                    "identifier": user_id,
                    "metadata": {"role": "user", "name": user_name},
                }
            )
        return cl.User(identifier=user_id, metadata=user.get("metadata", {}))


def _session_params() -> dict[str, Any]:
    raw = cl.user_session.get("model_name") or config.DEFAULT_MODEL
    return {
        "model_name": model_from_label(raw.strip()),
        "model_label": raw,
        "temperature": cl.user_session.get("temperature", config.DEFAULT_TEMPERATURE),
        "top_p": cl.user_session.get("top_p", config.DEFAULT_TOP_P),
        "max_tokens": cl.user_session.get("max_tokens", config.DEFAULT_MAX_TOKENS),
    }


def _init_interaction() -> None:
    cl.user_session.set("interaction", [{"role": "system", "content": config.SYSTEM_PROMPT}])


def _reset_chat() -> None:
    _init_interaction()
    cl.user_session.set("title_set", False)
    cl.user_session.set("welcome_message_sent", False)
    cl.user_session.set("vision_model_used", False)


async def _set_composer_commands() -> None:
    await cl.context.emitter.set_commands(
        [
            {
                "id": WEB_COMMAND,
                "icon": "globe",
                "description": "Recherche web",
                "button": True,
                "persistent": True,
            }
        ]
    )


async def _create_thread() -> None:
    if not USE_DB:
        return
    user = cl.user_session.get("user")
    if not user:
        return
    thread_id = str(uuid.uuid4())
    await cl.data_layer.create_thread(
        {
            "id": thread_id,
            "name": DEFAULT_THREAD_NAME,
            "userId": user.identifier,
            "metadata": {},
        }
    )
    cl.user_session.set("thread_id", thread_id)


async def _load_models(refresh: bool) -> tuple[list[str], str, int]:
    catalog = await get_catalog(refresh=refresh)
    models = build_model_labels(catalog)
    default_label = label_for_model(catalog, config.DEFAULT_MODEL)
    idx = models.index(default_label) if default_label in models else 0
    return models, default_label, idx


async def _send_settings(models: list[str], default_label: str, idx: int) -> None:
    await cl.ChatSettings(
        [
            Select(
                id="model",
                label="Modèle",
                values=models or [default_label],
                initial_index=idx,
            ),
            Slider(
                id="temperature",
                label="Température",
                initial=cl.user_session.get("temperature", config.DEFAULT_TEMPERATURE),
                min=0,
                max=1,
                step=TEMPERATURE_STEP,
            ),
            Slider(
                id="top_p",
                label="Top P",
                initial=cl.user_session.get("top_p", config.DEFAULT_TOP_P),
                min=0,
                max=1,
                step=TOP_P_STEP,
            ),
            Slider(
                id="max_tokens",
                label="Tokens max",
                initial=cl.user_session.get("max_tokens", config.DEFAULT_MAX_TOKENS),
                min=config.MAX_TOKENS_MIN,
                max=config.MAX_TOKENS_MAX,
                step=config.MAX_TOKENS_STEP,
            ),
        ]
    ).send()


async def _save_step(thread_id: str, step_type: str, content: str) -> None:
    if not USE_DB or not thread_id:
        return
    try:
        await cl.data_layer.create_step(
            {
                "id": str(uuid.uuid4()),
                "threadId": thread_id,
                "type": step_type,
                "name": step_type,
                "output": content,
            }
        )
    except Exception as e:
        logger.warning(f"Step non sauvegardé: {e}")


async def _handle_command(text: str) -> bool:
    if text.startswith("/model"):
        parts = text.split(" ", 1)
        if len(parts) == 1 or not parts[1].strip():
            current = cl.user_session.get("model_name") or config.DEFAULT_MODEL
            await cl.Message(content=f"Modèle actuel : {current}\nUsage : /model <nom>").send()
            return True
        name = parts[1].strip()
        cl.user_session.set("model_name", name)
        await cl.Message(content=f"Modèle : {name}").send()
        return True

    if text.startswith("/help"):
        await cl.Message(content=HELP).send()
        return True

    if text.startswith("/history"):
        await cl.Message(
            content=(
                "Historique : menu en haut à gauche. "
                "Requis : PERSISTENCE=local et AUTH_MODE=password."
            )
        ).send()
        return True

    if text.startswith("/clear"):
        _reset_chat()
        await cl.Message(content="Conversation effacée.").send()
        await cl.Message(content=WELCOME).send()
        cl.user_session.set("welcome_message_sent", True)
        return True

    return False


async def _maybe_set_thread_title(text: str) -> None:
    if cl.user_session.get("title_set"):
        return

    title = text[: config.MAX_TITLE_LENGTH] + ("..." if len(text) > config.MAX_TITLE_LENGTH else "")
    tid = cl.user_session.get("thread_id")
    if tid and USE_DB:
        try:
            p = _session_params()
            await cl.data_layer.update_thread(
                tid,
                name=title,
                metadata={
                    "model": p["model_name"],
                    "temperature": p["temperature"],
                    "top_p": p["top_p"],
                    "max_tokens": p["max_tokens"],
                },
            )
        except Exception as e:
            logger.warning(f"Titre thread: {e}")
    cl.user_session.set("title_set", True)


def _interaction() -> list[dict[str, Any]]:
    interaction = cl.user_session.get("interaction")
    if isinstance(interaction, list):
        return interaction
    _init_interaction()
    return cl.user_session.get("interaction")


async def _reply(result: dict[str, Any], msg: cl.Message, tid: str | None, params: dict) -> None:
    if result.get("has_images") and not cl.user_session.get("vision_model_used"):
        model_used = result.get("model_used", params["model_name"])
        if model_used != params["model_name"] and not result.get("error"):
            await cl.Message(content=f"Image analysée avec : {model_used}").send()
            cl.user_session.set("vision_model_used", True)

    if result.get("error"):
        content = (result.get("message") or {}).get("content") or "Erreur interne. Réessaie."
        await cl.Message(content=content).send()
        await _save_step(tid, "assistant_message", content)
        return

    content = (result.get("message") or {}).get("content") or msg.content
    msg.content = content
    await msg.send()
    await _save_step(tid, "assistant_message", content)


@cl.on_chat_start
async def start_chat():
    _init_interaction()
    cl.user_session.set("vision_model_used", False)
    cl.user_session.set("title_set", False)

    await _create_thread()

    models, default_label, idx = await _load_models(refresh=True)
    active_label = models[idx] if models else default_label
    cl.user_session.set("model_name", active_label)
    cl.user_session.set("temperature", config.DEFAULT_TEMPERATURE)
    cl.user_session.set("top_p", config.DEFAULT_TOP_P)
    cl.user_session.set("max_tokens", config.DEFAULT_MAX_TOKENS)

    if not cl.user_session.get("welcome_message_sent"):
        await cl.Message(content=WELCOME).send()
        cl.user_session.set("welcome_message_sent", True)

    await _set_composer_commands()
    await _send_settings(models, default_label, idx)


@cl.on_settings_update
async def on_settings_update(settings):
    if settings.get("model"):
        cl.user_session.set("model_name", settings["model"])
    if settings.get("temperature") is not None:
        cl.user_session.set("temperature", settings["temperature"])
    if settings.get("top_p") is not None:
        cl.user_session.set("top_p", settings["top_p"])
    if settings.get("max_tokens") is not None:
        cl.user_session.set("max_tokens", settings["max_tokens"])


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    thread_id = thread.get("id")
    cl.user_session.set("thread_id", thread_id)

    if not USE_DB:
        await cl.Message(content="Reprise impossible sans PERSISTENCE=local.").send()
        return

    full = await cl.data_layer.get_thread(thread_id)
    interaction = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    for step in (full or {}).get("steps", []):
        out = step.get("output", "")
        if step.get("type") == "user_message" and out:
            interaction.append({"role": "user", "content": out})
        elif step.get("type") == "assistant_message" and out:
            interaction.append({"role": "assistant", "content": out})

    cl.user_session.set("interaction", interaction)
    cl.user_session.set("title_set", True)
    cl.user_session.set("vision_model_used", False)

    meta = (full or {}).get("metadata", {})
    if meta.get("model"):
        cl.user_session.set("model_name", meta["model"])
    if meta.get("temperature") is not None:
        cl.user_session.set("temperature", meta["temperature"])
    if meta.get("top_p") is not None:
        cl.user_session.set("top_p", meta["top_p"])
    if meta.get("max_tokens") is not None:
        cl.user_session.set("max_tokens", meta["max_tokens"])

    models, default_label, idx = await _load_models(refresh=False)
    saved = cl.user_session.get("model_name")
    if saved in models:
        idx = models.index(saved)

    await _set_composer_commands()
    await _send_settings(models, default_label, idx)
    await cl.Message(content=f"Conversation reprise ({len(interaction) - 1} messages).").send()


@cl.on_message
async def main(message: cl.Message):
    try:
        text = message.content or ""

        if await _handle_command(text):
            return

        await _maybe_set_thread_title(text)

        tid = cl.user_session.get("thread_id")
        await _save_step(tid, "user_message", text)

        images, documents, errors = [], [], []
        if message.elements:
            images, documents, errors = validate_uploaded_files(message.elements)
            if errors:
                await cl.Message(content="Erreurs :\n" + "\n".join(f"- {e}" for e in errors)).send()
                if not images and not documents:
                    return

        msg = cl.Message(content="")
        interaction = _interaction()
        params = _session_params()
        web_on = message.command == WEB_COMMAND

        async def run_llm(flow_cb):
            return await process_llm_request(
                input_message=text,
                interaction=interaction,
                model_name=params["model_label"],
                temperature=params["temperature"],
                top_p=params["top_p"],
                max_tokens=params["max_tokens"],
                files=[f.path for f in documents] if documents else None,
                image_paths=[f.path for f in images] if images else None,
                web_search_enabled=web_on,
                stream_callback=msg.stream_token,
                flow_callback=flow_cb,
            )

        if web_on:
            result = await run_llm(WebFlowUI().handle)
        else:
            result = await run_llm(None)

        await _reply(result, msg, tid, params)

    except Exception as e:
        logger.error(f"main: {e}", exc_info=True)
        await cl.Message(content="Erreur interne. Réessaie.").send()
