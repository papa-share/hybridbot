import os

os.environ["TRACELOOP_TRACING_ENABLED"] = "false"
os.environ["TRACELOOP_METRICS_ENABLED"] = "false"
os.environ["TRACELOOP_TRACE_CONTENT"] = "false"

from typing import Any

import chainlit as cl
from chainlit.input_widget import Select, Slider

import chatbot.persistence  # noqa: F401
from chatbot.config import (
    TEMPERATURE_STEP,
    TOP_P_STEP,
    config,
    logger,
)
from chatbot.flow import make_flow_handler
from chatbot.llm import (
    build_model_labels,
    get_catalog,
    label_for_model,
    model_from_label,
    process_llm_request,
)
from chatbot.persistence import (
    SESSION_UI_MODEL,
    persist_chat_prefs,
    prefs_from_settings,
    read_chat_prefs,
    thread_is_shared,
    write_chat_prefs,
)
from chatbot.validators import validate_uploaded_files

WEB_COMMAND = "Web"
ERROR_MSG = "Erreur interne. Réessaie."
MISSING_DOC_MSG = "Jointe un PDF ou un fichier texte avant d'envoyer."


def _expects_attachment(text: str) -> bool:
    lower = text.lower()
    return "document joint" in lower or "pdf joint" in lower or "fichier joint" in lower


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
            message="Résume le document joint : points clés et structure. (Joindre le PDF avant d'envoyer.)",
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
        from chatbot.auth import authenticate

        return await authenticate(username, password)


@cl.on_shared_thread_view
async def on_shared_thread_view(thread: dict, viewer: cl.User | None):
    del viewer
    return thread_is_shared(thread)


def _session_params() -> dict[str, Any]:
    ui_label = (
        cl.user_session.get(SESSION_UI_MODEL)
        or cl.user_session.get("model_name")
        or config.DEFAULT_MODEL
    )
    return {
        "ollama_model_id": model_from_label(ui_label.strip()),
        "ui_model_label": ui_label,
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


async def _prepare_settings(
    *, refresh_models: bool, use_user_store: bool
) -> tuple[list[str], dict[str, Any], int]:
    models, default_label, default_idx = await _load_models(refresh=refresh_models)
    prefs = await read_chat_prefs(default_label, use_user_store=use_user_store)
    if prefs["model"] not in models:
        prefs["model"] = models[default_idx] if models else default_label
    write_chat_prefs(prefs)
    idx = models.index(prefs["model"]) if prefs["model"] in models else default_idx
    return models, prefs, idx


async def _bootstrap_ui(*, refresh_models: bool, use_user_store: bool) -> None:
    models, prefs, idx = await _prepare_settings(
        refresh_models=refresh_models,
        use_user_store=use_user_store,
    )
    await _set_composer_commands()
    await _send_settings(models, prefs, idx)


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
        model_used = result.get("model_used", params["ollama_model_id"])
        if model_used != params["ollama_model_id"] and not result.get("error"):
            await cl.Message(content=f"Image analysée avec : {model_used}").send()
            cl.user_session.set("vision_model_used", True)

    if result.get("error"):
        content = (result.get("message") or {}).get("content") or ERROR_MSG
        await cl.Message(content=content).send()
        return

    content = (result.get("message") or {}).get("content") or msg.content
    msg.content = content
    await msg.send()


@cl.on_chat_start
async def start_chat():
    _init_interaction()
    cl.user_session.set("vision_model_used", False)
    await _bootstrap_ui(refresh_models=True, use_user_store=True)


@cl.on_settings_update
async def on_settings_update(settings):
    prefs = prefs_from_settings(settings)
    write_chat_prefs(prefs)
    await persist_chat_prefs(prefs)


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    cl.user_session.set("interaction", _interaction_from_thread(thread))
    cl.user_session.set("vision_model_used", False)
    await _bootstrap_ui(refresh_models=False, use_user_store=False)


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

        if _expects_attachment(text) and not documents:
            await cl.Message(content=MISSING_DOC_MSG).send()
            return

        msg = cl.Message(content="")
        interaction = _interaction()
        params = _session_params()
        web_on = message.command == WEB_COMMAND

        flow_cb = make_flow_handler(has_documents=bool(documents), web_on=web_on)

        result = await process_llm_request(
            input_message=text,
            interaction=interaction,
            ui_model_label=params["ui_model_label"],
            temperature=params["temperature"],
            top_p=params["top_p"],
            max_tokens=params["max_tokens"],
            files=(
                [(str(f.path), f.mime or "", f.name or "") for f in documents]
                if documents
                else None
            ),
            image_paths=[f.path for f in images] if images else None,
            web_search_enabled=web_on,
            stream_callback=msg.stream_token,
            flow_callback=flow_cb,
        )

        await _reply(result, msg, params)

    except Exception as e:
        logger.error(f"main: {e}", exc_info=True)
        await cl.Message(content=ERROR_MSG).send()
