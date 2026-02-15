"""Application Chainlit - Point d'entrée principal."""

import uuid
from typing import Any

import chainlit as cl
from chainlit.input_widget import Select, Slider

from chatbot.config import config
from chatbot.constants import (
    DEFAULT_THREAD_NAME,
    DEFAULT_USER_ID,
    DEFAULT_USER_NAME,
    TEMPERATURE_STEP,
    TOP_P_STEP,
)
from chatbot.core.llm import list_model_names, process_llm_request
from chatbot.data.sqlite_layer import SQLiteDataLayer
from chatbot.logger import logger
from chatbot.messages import (
    CONVERSATION_RESET,
    CONVERSATION_RESUMED,
    ERROR_INTERNAL,
    HELP,
    HISTORY,
    MODEL_CURRENT,
    MODEL_SET,
    RESUME_NOT_AVAILABLE,
    VISION_MODEL_USED,
    WELCOME,
)
from chatbot.utils.validators import validate_uploaded_files

# Configuration
DATA_LAYER_ENABLED = config.PERSISTENCE == "local"

# Initialisation du Data Layer
if DATA_LAYER_ENABLED:
    cl.data_layer = SQLiteDataLayer(config.DEFAULT_DB_PATH)
    if config.DEBUG:
        logger.debug("Data Layer initialisé")
else:
    cl.data_layer = None

if config.AUTH_MODE == "password":

    @cl.password_auth_callback
    async def auth_callback(username: str, _password: str) -> cl.User | None:
        """
        Callback d'authentification pour Chainlit.

        Accepte n'importe quel nom d'utilisateur sans vérification de mot de passe
        (authentification symbolique). Crée l'utilisateur dans la base de données
        si la persistance est activée.

        Args:
            username: Nom d'utilisateur fourni
            _password: Mot de passe (non vérifié dans cette implémentation)

        Returns:
            Objet User Chainlit ou None si l'authentification échoue
        """
        user_id = username or DEFAULT_USER_ID
        user_name = username or DEFAULT_USER_NAME

        if not DATA_LAYER_ENABLED:
            return cl.User(
                identifier=user_id,
                metadata={"role": "user", "name": user_name},
            )

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


def _get_session_params() -> dict[str, Any]:
    """
    Récupère les paramètres LLM de la session avec valeurs par défaut.

    Returns:
        Dictionnaire contenant model_name, temperature, top_p et max_tokens
    """
    return {
        "model_name": (cl.user_session.get("model_name") or config.DEFAULT_MODEL).strip(),
        "temperature": cl.user_session.get("temperature", config.DEFAULT_TEMPERATURE),
        "top_p": cl.user_session.get("top_p", config.DEFAULT_TOP_P),
        "max_tokens": cl.user_session.get("max_tokens", config.DEFAULT_MAX_TOKENS),
    }


async def _create_step_safe(thread_id: str, step_type: str, content: str, name: str) -> None:
    """
    Crée un step de conversation avec gestion d'erreurs robuste.

    Args:
        thread_id: Identifiant du thread de conversation
        step_type: Type de step ("user_message" ou "assistant_message")
        content: Contenu du message
        name: Nom descriptif du step
    """
    if not DATA_LAYER_ENABLED or not thread_id:
        return
    try:
        await cl.data_layer.create_step(
            {
                "id": str(uuid.uuid4()),
                "threadId": thread_id,
                "type": step_type,
                "name": name,
                "output": content,
            }
        )
    except LookupError:
        logger.warning("[DATA_LAYER] Impossible de créer le step (ContextVar non initialisé)")
    except Exception as e:
        logger.error(f"Sauvegarde step {step_type}: {type(e).__name__}: {e}")


@cl.on_chat_start
async def start_chat():
    """
    Initialise une nouvelle session de conversation.

    Configure l'historique, crée le thread dans la base de données si la persistance
    est activée, affiche le message de bienvenue, et configure les paramètres UI
    (sliders, sélection de modèle).
    """
    welcome_sent = cl.user_session.get("welcome_message_sent", False)

    cl.user_session.set(
        "interaction",
        [{"role": "system", "content": config.SYSTEM_PROMPT}],
    )

    logger.info("Nouvelle conversation démarrée")

    if DATA_LAYER_ENABLED:
        user = cl.user_session.get("user")
        if user:
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

    cl.user_session.set("title_set", False)

    if not welcome_sent:
        await cl.Message(content=WELCOME).send()
        cl.user_session.set("welcome_message_sent", True)

    models = await list_model_names()
    default_model_index = 0
    if models:
        try:
            default_model_index = models.index(config.DEFAULT_MODEL)
        except ValueError:
            default_model_index = 0

    params = _get_session_params()
    cl.user_session.set(
        "model_name", models[default_model_index] if models else params["model_name"]
    )
    cl.user_session.set("temperature", params["temperature"])
    cl.user_session.set("top_p", params["top_p"])
    cl.user_session.set("max_tokens", params["max_tokens"])

    await cl.ChatSettings(
        [
            Select(
                id="model",
                label="Modèle IA",
                values=models if models else [config.DEFAULT_MODEL],
                initial_index=default_model_index if models else 0,
            ),
            Slider(
                id="temperature",
                label="Température",
                initial=config.DEFAULT_TEMPERATURE,
                min=0,
                max=1,
                step=TEMPERATURE_STEP,
            ),
            Slider(
                id="top_p",
                label="Top P",
                initial=config.DEFAULT_TOP_P,
                min=0,
                max=1,
                step=TOP_P_STEP,
            ),
            Slider(
                id="max_tokens",
                label="Tokens max",
                initial=config.DEFAULT_MAX_TOKENS,
                min=config.MAX_TOKENS_MIN,
                max=config.MAX_TOKENS_MAX,
                step=config.MAX_TOKENS_STEP,
            ),
        ]
    ).send()


@cl.on_settings_update
async def on_settings_update(settings):
    """
    Met à jour les paramètres de la session utilisateur.

    Appelée automatiquement par Chainlit lorsque l'utilisateur modifie
    les réglages via le panneau de configuration (modèle, température, etc.).

    Args:
        settings: Dictionnaire des nouveaux paramètres
    """
    params = _get_session_params()
    model_name = settings.get("model")
    temperature = settings.get("temperature", params["temperature"])
    top_p = settings.get("top_p", params["top_p"])
    max_tokens = settings.get("max_tokens", params["max_tokens"])

    if model_name:
        previous = cl.user_session.get("model_name")
        if previous is not None and previous.strip() != model_name.strip():
            cl.user_session.set("model_just_changed", True)
        cl.user_session.set("model_name", model_name)

    cl.user_session.set("temperature", temperature)
    cl.user_session.set("top_p", top_p)
    cl.user_session.set("max_tokens", max_tokens)
    logger.debug("[SETTINGS] Paramètres mis à jour")


@cl.on_chat_resume
async def on_chat_resume(thread: dict):
    """Restaure une conversation passée."""
    thread_id = thread.get("id")
    cl.user_session.set("thread_id", thread_id)

    if not DATA_LAYER_ENABLED:
        await cl.Message(content=RESUME_NOT_AVAILABLE).send()
        return

    full_thread = await cl.data_layer.get_thread(thread_id)

    interaction = [{"role": "system", "content": config.SYSTEM_PROMPT}]

    if full_thread:
        steps = full_thread.get("steps", [])
        for step in steps:
            step_type = step.get("type", "")
            step_output = step.get("output", "")

            if step_type == "user_message" and step_output:
                interaction.append({"role": "user", "content": step_output})
            elif step_type == "assistant_message" and step_output:
                interaction.append({"role": "assistant", "content": step_output})

    cl.user_session.set("interaction", interaction)
    cl.user_session.set("title_set", True)

    metadata = full_thread.get("metadata", {}) if full_thread else {}
    if metadata.get("model"):
        cl.user_session.set("model_name", metadata["model"])
    if metadata.get("temperature"):
        cl.user_session.set("temperature", metadata["temperature"])
    if metadata.get("top_p"):
        cl.user_session.set("top_p", metadata["top_p"])
    if metadata.get("max_tokens"):
        cl.user_session.set("max_tokens", metadata["max_tokens"])

    messages_count = len(interaction) - 1
    await cl.Message(content=CONVERSATION_RESUMED.format(count=messages_count)).send()


@cl.on_message
async def main(message: cl.Message):
    """
    Point d'entrée principal pour traiter les messages utilisateur.

    Gère les commandes slash (/model, /help, /clear, /history),
    valide les fichiers uploadés (images, documents), appelle le LLM
    via Ollama et sauvegarde les interactions dans la base de données.

    Args:
        message: Message reçu de l'utilisateur
    """
    try:
        if message.content and message.content.startswith("/model"):
            parts = message.content.split(" ", 1)
            if len(parts) == 1 or not parts[1].strip():
                current = cl.user_session.get("model_name") or config.DEFAULT_MODEL
                await cl.Message(content=MODEL_CURRENT.format(model=current)).send()
                return
            name = parts[1].strip()
            cl.user_session.set("model_name", name)
            await cl.Message(content=MODEL_SET.format(model=name)).send()
            return

        if message.content and message.content.startswith("/help"):
            await cl.Message(content=HELP).send()
            return

        if message.content and message.content.startswith("/history"):
            await cl.Message(content=HISTORY).send()
            return

        if message.content and message.content.startswith("/clear"):
            cl.user_session.set(
                "interaction", [{"role": "system", "content": config.SYSTEM_PROMPT}]
            )
            cl.user_session.set("title_set", False)
            cl.user_session.set("welcome_message_sent", False)
            await cl.Message(content=CONVERSATION_RESET).send()
            return

        if not cl.user_session.get("title_set"):
            try:
                title = message.content[: config.MAX_TITLE_LENGTH] + (
                    "..." if len(message.content) > config.MAX_TITLE_LENGTH else ""
                )
                thread_id = cl.user_session.get("thread_id")

                if thread_id and DATA_LAYER_ENABLED:
                    await cl.data_layer.update_thread(
                        thread_id,
                        name=title,
                        metadata={
                            "model": cl.user_session.get("model_name"),
                            "temperature": cl.user_session.get("temperature"),
                            "top_p": cl.user_session.get("top_p"),
                            "max_tokens": cl.user_session.get("max_tokens"),
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"Impossible de mettre à jour le titre du thread: {type(e).__name__}: {e}"
                )
            cl.user_session.set("title_set", True)

        thread_id = cl.user_session.get("thread_id")
        await _create_step_safe(thread_id, "user_message", message.content, "Message utilisateur")

        images, documents = [], []
        if message.elements:
            images, documents, errors = validate_uploaded_files(message.elements)

            if config.DEBUG:
                logger.debug(
                    f"Fichiers: {len(images)} img, {len(documents)} doc, {len(errors)} err"
                )
            if errors:
                for error in errors:
                    logger.warning(f"Erreur de validation: {error}")

                error_msg = cl.Message(
                    content="Erreurs de validation :\n" + "\n".join(f"- {e}" for e in errors)
                )
                await error_msg.send()

                if not images and not documents:
                    return

        if config.DEBUG:
            mode = (
                f"{len(images)} img"
                if images
                else f"{len(documents)} doc"
                if documents
                else "texte"
            )
            logger.debug(f"Traitement: {mode}")

        msg = cl.Message(content="")
        file_paths = [f.path for f in images] + [f.path for f in documents]

        interaction = cl.user_session.get("interaction")
        if not interaction or not isinstance(interaction, list):
            logger.error("[SESSION] Interaction invalide, réinitialisation")
            interaction = [{"role": "system", "content": config.SYSTEM_PROMPT}]
            cl.user_session.set("interaction", interaction)

        params = _get_session_params()
        model_name = params["model_name"]
        temperature = params["temperature"]
        top_p = params["top_p"]
        max_tokens = params["max_tokens"]
        model_just_changed = cl.user_session.get("model_just_changed", False)

        async def stream_callback(token: str):
            await msg.stream_token(token)

        result = await process_llm_request(
            input_message=message.content,
            interaction=interaction,
            model_name=model_name,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            files=file_paths if file_paths else None,
            stream_callback=stream_callback,
            model_just_changed=model_just_changed,
        )

        if model_just_changed:
            cl.user_session.set("model_just_changed", False)

        if result.get("has_images") and not cl.user_session.get("vision_model_used"):
            model_used = result.get("model_used", model_name)
            await cl.Message(content=VISION_MODEL_USED.format(model=model_used)).send()
            cl.user_session.set("vision_model_used", True)

        thread_id = cl.user_session.get("thread_id")
        if result.get("error"):
            error_content = (result.get("message") or {}).get("content") or ""
            await cl.Message(content=error_content).send()
            await _create_step_safe(
                thread_id, "assistant_message", error_content, "Réponse assistant"
            )
        else:
            await msg.send()
            output = (result.get("message") or {}).get("content") or msg.content
            await _create_step_safe(thread_id, "assistant_message", output, "Réponse assistant")

    except Exception as e:
        error_type = type(e).__name__
        logger.error(f"Erreur dans main(): {error_type}: {e}", exc_info=True)
        error_msg = cl.Message(content=ERROR_INTERNAL.format(error_type=error_type))
        await error_msg.send()
