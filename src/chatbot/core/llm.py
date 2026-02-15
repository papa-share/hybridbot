"""Traitement LLM via Ollama."""

import asyncio
import base64
import os
import time
from collections.abc import Callable
from typing import Any

import aiofiles
import ollama
from ollama import AsyncClient

from chatbot.config import config
from chatbot.constants import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS
from chatbot.core.errors import get_ollama_error_message
from chatbot.logger import logger
from chatbot.messages import (
    ERROR_GENERAL,
    ERROR_PROCESSING,
    ERROR_TIMEOUT,
    NO_RESPONSE,
    TRUNCATION_WARNING,
)
from chatbot.utils.validators import validate_image_path

try:
    import PyPDF2

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("PyPDF2 non installé. Le support PDF est désactivé.")

_ollama_client: AsyncClient | None = None
_model_cache = {"models": [], "timestamp": 0}
MODEL_CACHE_TTL = 300


def get_ollama_client() -> AsyncClient:
    """
    Retourne le client Ollama singleton (pattern lazy initialization).

    Crée le client lors du premier appel avec l'URL et le timeout configurés,
    puis réutilise la même instance pour toutes les requêtes suivantes.

    Returns:
        Client Ollama asynchrone configuré
    """
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = AsyncClient(host=config.OLLAMA_URL)
    return _ollama_client


async def extract_document_content(file_path: str) -> str:
    """
    Extrait le contenu textuel d'un document de manière asynchrone.

    Supporte les formats PDF (via PyPDF2), Markdown (.md) et texte (.txt).
    En cas d'erreur, retourne un message d'erreur au lieu de lever une exception.

    Args:
        file_path: Chemin vers le fichier à extraire

    Returns:
        Contenu textuel extrait ou message d'erreur
    """
    try:
        file_lower = file_path.lower()
        if file_lower.endswith(".pdf"):
            if not PDF_SUPPORT:
                return "Erreur: PyPDF2 non installé. Impossible de lire le PDF."

            # Extraction PDF dans un thread pour éviter de bloquer l'event loop
            def _extract_pdf():
                with open(file_path, "rb") as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    text_parts = []
                    for page in pdf_reader.pages:
                        text_parts.append(page.extract_text())
                    return "\n".join(text_parts).strip()
            
            return await asyncio.to_thread(_extract_pdf)

        elif file_lower.endswith(DOCUMENT_EXTENSIONS[1:]):
            async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
                return await f.read()
        else:
            return "Format de fichier non supporté"

    except Exception as e:
        return f"Erreur lors de la lecture du fichier: {str(e)}"


async def encode_image_to_base64(image_path: str) -> str:
    """
    Encode une image en base64 pour l'API Ollama de manière asynchrone.

    Valide d'abord l'existence du fichier, puis lit et encode son contenu.

    Args:
        image_path: Chemin vers l'image à encoder

    Returns:
        Image encodée en base64 (string)

    Raises:
        Exception: Si le fichier n'existe pas ou si l'encodage échoue
    """
    abs_path = os.path.abspath(image_path)
    validate_image_path(abs_path)
    try:
        async with aiofiles.open(abs_path, mode="rb") as image_file:
            content = await image_file.read()
            return base64.b64encode(content).decode("utf-8")
    except Exception as e:
        raise Exception(f"Erreur lors de l'encodage de l'image {image_path}: {str(e)}") from e


async def list_model_names() -> list[str]:
    """
    Récupère les modèles disponibles depuis Ollama avec cache TTL.

    Priorise les modèles cloud (gratuits, à jour) avant les modèles locaux.
    Cache les résultats pendant 5 minutes pour éviter des appels répétés.
    En cas d'erreur, retourne une liste de modèles cloud connus.

    Returns:
        Liste de noms de modèles, cloud en premier
    """
    global _model_cache
    
    # Vérifier le cache
    now = time.time()
    if now - _model_cache["timestamp"] < MODEL_CACHE_TTL and _model_cache["models"]:
        logger.debug(f"Utilisation du cache de modèles ({len(_model_cache['models'])} modèles)")
        return _model_cache["models"]
    
    try:
        # Appel asynchrone pour ne pas bloquer l'event loop
        listed = await asyncio.to_thread(ollama.list)

        if hasattr(listed, "models"):
            items = listed.models
        elif isinstance(listed, dict):
            items = listed.get("models", [])
        elif isinstance(listed, (list, tuple)):
            items = listed
        else:
            items = []

        all_models = []
        for item in items:
            if hasattr(item, "model"):
                name = item.model
            elif isinstance(item, dict):
                name = item.get("name")
            elif isinstance(item, str):
                name = item
            else:
                continue
            if name:
                all_models.append(name)

        cloud_models = [m for m in all_models if ":cloud" in m or m.endswith("-cloud")]
        local_models = [m for m in all_models if m not in cloud_models]

        result = cloud_models + local_models
        
        # Mettre à jour le cache
        _model_cache["models"] = result
        _model_cache["timestamp"] = now
        
        logger.debug(
            f"Modèles détectés: {len(all_models)} total "
            f"({len(cloud_models)} cloud, {len(local_models)} local)"
        )
        return result
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des modèles Ollama: {e}")
        logger.info("Utilisation des modèles cloud connus en fallback")
        return config.KNOWN_CLOUD_MODELS


async def process_llm_request(
    input_message: str,
    interaction: list[dict[str, Any]],
    model_name: str,
    temperature: float = config.DEFAULT_TEMPERATURE,
    top_p: float = config.DEFAULT_TOP_P,
    max_tokens: int = config.DEFAULT_MAX_TOKENS,
    files: list[str] | None = None,
    stream_callback: Callable[[str], Any] | None = None,
    model_just_changed: bool = False,
) -> dict[str, Any]:
    """
    Traite une requête LLM via Ollama avec support multimodal et streaming.

    Gère automatiquement :
    - L'extraction de contenu des documents (PDF, Markdown, texte)
    - L'encodage des images en base64
    - La sélection automatique d'un modèle vision si nécessaire
    - Le streaming des tokens de réponse
    - La détection de troncature (réponse incomplète)

    Args:
        input_message: Message de l'utilisateur
        interaction: Historique de conversation (format OpenAI)
        model_name: Nom du modèle à utiliser
        temperature: Température de génération (0-1)
        top_p: Probabilité cumulative pour nucleus sampling
        max_tokens: Nombre maximum de tokens à générer
        files: Liste optionnelle de chemins vers fichiers (images/documents)
        stream_callback: Fonction async à appeler pour chaque token généré

    Returns:
        Dictionnaire avec clés :
        - message: {"content": str, "truncated": bool}
        - model_used: str (modèle effectivement utilisé)
        - has_images: bool
        - error: bool (présent uniquement en cas d'erreur)
    """
    start_time = time.time()
    try:
        images = []
        documents = []

        if files:
            for file_path in files:
                ext = file_path.lower()
                if ext.endswith(IMAGE_EXTENSIONS):
                    images.append(file_path)
                elif ext.endswith(DOCUMENT_EXTENSIONS):
                    documents.append(file_path)

        content = input_message
        if documents:
            doc_start = time.time()
            content += "\n\nFichiers joints :\n"
            # Extraire les documents en parallèle
            doc_tasks = [extract_document_content(doc) for doc in documents]
            doc_contents = await asyncio.gather(*doc_tasks)
            for doc, doc_content in zip(documents, doc_contents):
                doc_name = os.path.basename(doc)
                content += f"\n--- Contenu de {doc_name} ---\n{doc_content}\n"
            doc_time = (time.time() - doc_start) * 1000
            logger.debug(f"[perf] Extraction documents: {doc_time:.1f}ms ({len(documents)} fichiers)")

        interaction.append({"role": "user", "content": content})

        try:
            has_images = bool(images)

            if has_images:
                logger.debug(f"Traitement de {len(images)} image(s)")
                available_models = await list_model_names()
                # Sélection du premier modèle vision disponible
                selected_model = next(
                    (vm for vm in config.VISION_MODELS if vm in available_models),
                    model_name,  # Fallback sur le modèle demandé si aucun modèle vision dispo
                )
            else:
                selected_model = model_name

            messages_for_ollama = interaction.copy()
            if model_just_changed and messages_for_ollama and messages_for_ollama[0].get("role") == "system":
                instruction = (
                    "\n\nL'utilisateur vient de changer de modèle. Tu es maintenant le modèle "
                    "sélectionné. Réponds en ton propre nom, pas en reprenant l'identité des "
                    "réponses précédentes."
                )
                messages_for_ollama[0] = {
                    **messages_for_ollama[0],
                    "content": messages_for_ollama[0]["content"] + instruction,
                }

            max_context = config.MAX_CONTEXT_MESSAGES
            if len(messages_for_ollama) > max_context + 1:
                messages_for_ollama = [messages_for_ollama[0]] + messages_for_ollama[-(max_context):]
                logger.debug(
                    f"Contexte tronqué: {len(interaction)} → {len(messages_for_ollama)} messages"
                )

            if has_images:
                try:
                    img_start = time.time()
                    # Encoder les images en parallèle
                    image_tasks = [encode_image_to_base64(p) for p in images]
                    encoded_images = await asyncio.gather(*image_tasks)
                    messages_for_ollama[-1]["images"] = encoded_images  # type: ignore
                    img_time = (time.time() - img_start) * 1000
                    logger.debug(f"[perf] Encodage images: {img_time:.1f}ms ({len(images)} images)")
                except Exception as e:
                    logger.error(f"Erreur encodage images: {type(e).__name__}: {e}")
                    err = f"Erreur lors du traitement des images: {str(e)}"
                    return {"message": {"content": err}, "error": True}

            logger.debug(
                f"Contexte: {len(messages_for_ollama)} messages, modèle={selected_model}"
            )

            client = get_ollama_client()
            num_ctx = (
                4096
                if any(
                    s in selected_model.lower() for s in (":1b", ":2b", "tiny")
                )
                else config.DEFAULT_NUM_CTX
            )
            opts = {
                "temperature": temperature,
                "top_p": top_p,
                "num_ctx": num_ctx,
                "num_predict": max_tokens,
            }

            async def _stream_and_aggregate():
                """Agrège les chunks de streaming Ollama."""
                content_parts = []
                last_chunk = None
                stream = await client.chat(
                    model=selected_model,
                    messages=messages_for_ollama,
                    options=opts,
                    stream=True,
                )
                async for chunk in stream:
                    last_chunk = chunk
                    part = (chunk.get("message") or {}).get("content") or ""
                    content_parts.append(part)
                    if stream_callback and part:
                        await stream_callback(part)
                return "".join(content_parts), last_chunk

            llm_start = time.time()
            full_content, last_chunk = await asyncio.wait_for(
                _stream_and_aggregate(),
                timeout=float(config.OLLAMA_TIMEOUT),
            )
            llm_time = (time.time() - llm_start) * 1000
            logger.debug(f"[perf] Réponse LLM: {llm_time:.1f}ms")
        except asyncio.TimeoutError:
            logger.error("Timeout Ollama")
            return {"message": {"content": ERROR_TIMEOUT}, "error": True}
        except Exception as e:
            logger.error(f"Ollama {type(e).__name__}: {e}")
            user_msg = get_ollama_error_message(e, selected_model)
            return {"message": {"content": user_msg}, "error": True}

        try:
            response_content = full_content.strip() if full_content else ""
            done_reason = (last_chunk or {}).get("done_reason", "unknown")
            eval_count = (last_chunk or {}).get("eval_count", 0)
            is_truncated = done_reason == "length" or (
                eval_count > 0 and eval_count >= max_tokens - config.TRUNCATION_THRESHOLD_OFFSET
            )

            if is_truncated:
                logger.warning(
                    f"[TRONCATURE] done_reason={done_reason} "
                    f"eval_count={eval_count}/{max_tokens}"
                )

            if response_content:
                if is_truncated:
                    response_content += TRUNCATION_WARNING
                    if stream_callback:
                        await stream_callback(TRUNCATION_WARNING)
                interaction.append({"role": "assistant", "content": response_content})
                
                total_time = (time.time() - start_time) * 1000
                logger.info(f"[perf] Requête complète: {total_time:.1f}ms (modèle={selected_model})")
                
                return {
                    "message": {"content": response_content, "truncated": is_truncated},
                    "model_used": selected_model,
                    "has_images": has_images,
                }

            return {"message": {"content": NO_RESPONSE}, "error": True}
        except Exception as e:
            logger.error(f"Traitement réponse: {type(e).__name__}: {e}")
            return {"message": {"content": ERROR_PROCESSING}, "error": True}
    except Exception as e:
        logger.error(f"process_llm_request() {type(e).__name__}: {e}", exc_info=True)
        return {"message": {"content": ERROR_GENERAL}, "error": True}
