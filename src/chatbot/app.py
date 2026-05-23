import os

os.environ["TRACELOOP_TRACING_ENABLED"] = "false"
os.environ["TRACELOOP_METRICS_ENABLED"] = "false"
os.environ["TRACELOOP_TRACE_CONTENT"] = "false"

from typing import Any

import chainlit as cl
from chainlit.input_widget import Select, Slider

import chatbot.persistence  # noqa: F401
from chatbot.persistence import (
    apply_chat_prefs,
    load_chat_prefs,
    prefs_from_settings,
    save_chat_prefs,
)
from chatbot.config import (
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
from chatbot.validators import validate_uploaded_files
from chatbot.web_flow import WebFlowUI

WEB_COMMAND = "Web"
ERROR_MSG = "Erreur interne. Réessaie."


@cl.set_starters
async def set_chat_starters(_user, _language):
    return [
        cl.Starter(
            label="Actualités IA",
            message="Quelles sont les actualités IA de cette semaine ?",
            command=WEB_COMMAND,
        ),
        cl.Starter(
            label="Résumer un PDF",
            message="Résume le document joint : points clés et structure.",
        ),
        cl.Starter(
            label="Expliquer du code",
            message="Explique ce code étape par étape.",
        ),
        cl.Starter(
            label="Analyser une image",
            message="Décris le contenu de l'image jointe.",
        ),
    ]


if config.AUTH_MODE == "password":

    @cl.password_auth_callback
    async def auth_callback(username: str, password: str) -> cl.User | None:
        if config.AUTH_PASSWORD and password != config.AUTH_PASSWORD:
            return None

        user_id = username or DEFAULT_USER_ID
        user_name = username or DEFAULT_USER_NAME
        return cl.User(identifier=user_id, metadata={"role": "user", "name": user_name})


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


async def _load_models(refresh: bool) -> tuple[list[str], str, int]:
    catalog = await get_catalog(refresh=refresh)
    models = build_model_labels(catalog)
    default_label = label_for_model(catalog, config.DEFAULT_MODEL)
    idx = models.index(default_label) if default_label in models else 0
    return models, default_label, idx


async def _send_settings(models: list[str], prefs: dict[str, Any], idx: int) -> None:
    await cl.ChatSettings(
        [
            Select(
                id="model",
                label="Modèle",
                values=models or [prefs["model"]],
                initial_index=idx,
            ),
            Slider(
                id="temperature",
                label="Température",
                initial=prefs["temperature"],
                min=0,
                max=1,
                step=TEMPERATURE_STEP,
            ),
            Slider(
                id="top_p",
                label="Top P",
                initial=prefs["top_p"],
                min=0,
                max=1,
                step=TOP_P_STEP,
            ),
            Slider(
                id="max_tokens",
                label="Tokens max",
                initial=prefs["max_tokens"],
                min=config.MAX_TOKENS_MIN,
                max=config.MAX_TOKENS_MAX,
                step=config.MAX_TOKENS_STEP,
            ),
        ]
    ).send()


async def _prepare_settings(*, refresh_models: bool, use_user_store: bool) -> tuple[list[str], dict[str, Any], int]:
    models, default_label, default_idx = await _load_models(refresh=refresh_models)
    prefs = await load_chat_prefs(default_label, use_user_store=use_user_store)
    if prefs["model"] not in models:
        prefs["model"] = models[default_idx] if models else default_label
    apply_chat_prefs(prefs)
    idx = models.index(prefs["model"]) if prefs["model"] in models else default_idx
    return models, prefs, idx


def _interaction() -> list[dict[str, Any]]:
    interaction = cl.user_session.get("interaction")
    if isinstance(interaction, list):
        return interaction
    _init_interaction()
    return cl.user_session.get("interaction")


def _interaction_from_thread(thread: dict) -> list[dict[str, Any]]:
    interaction = [{"role": "system", "content": config.SYSTEM_PROMPT}]
    for step in thread.get("steps", []):
        out = step.get("output", "")
        if step.get("type") == "user_message" and out:
            interaction.append({"role": "user", "content": out})
        elif step.get("type") == "assistant_message" and out:
            interaction.append({"role": "assistant", "content": out})
    return interaction


async def _reply(result: dict[str, Any], msg: cl.Message, params: dict) -> None:
    if result.get("has_images") and not cl.user_session.get("vision_model_used"):
        model_used = result.get("model_used", params["model_name"])
        if model_used != params["model_name"] and not result.get("error"):
            await cl.Message(content=f"Image analysée avec : {model_used}").send()
            cl.user_session.set("vision_model_used", True)

    if result.get("error"):
        content = (result.get("message") or {}).get("content") or ERROR_MSG
        await cl.Message(content=content).send()
        return

    content = (result.get("message") or {}).get("content") or msg.content
    msg.content = content
    if getattr(msg, "streaming", False):
        await msg.stream_token(content, is_sequence=True)
    await msg.send()


@cl.on_chat_start
async def start_chat():
    _init_interaction()
    cl.user_session.set("vision_model_used", False)

    models, prefs, idx = await _prepare_settings(refresh_models=True, use_user_store=True)
    await _set_composer_commands()
    await _send_settings(models, prefs, idx)


@cl.on_settings_update
async def on_settings_update(settings):
    prefs = prefs_from_settings(settings)
    apply_chat_prefs(prefs)
    await save_chat_prefs(prefs)


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    cl.user_session.set("interaction", _interaction_from_thread(thread))
    cl.user_session.set("vision_model_used", False)

    models, prefs, idx = await _prepare_settings(refresh_models=False, use_user_store=False)
    await _set_composer_commands()
    await _send_settings(models, prefs, idx)


@cl.on_message
async def main(message: cl.Message):
    try:
        text = message.content or ""

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

        await _reply(result, msg, params)

    except Exception as e:
        logger.error(f"main: {e}", exc_info=True)
        await cl.Message(content=ERROR_MSG).send()
