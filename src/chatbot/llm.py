import asyncio
import base64
import os
from collections.abc import Callable
from typing import Any

import aiofiles
import ollama
from ollama import AsyncClient

from chatbot.config import DOCUMENT_EXTENSIONS, IMAGE_EXTENSIONS, config, logger
from chatbot.validators import validate_image_path
from chatbot.web import link_citations, search_web

try:
    from pypdf import PdfReader

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logger.warning("pypdf non installé, PDF désactivé")

_client: AsyncClient | None = None
_catalog: dict[str, list[str]] | None = None

_LABEL_PREFIXES = ("[local] ", "[cloud] ", "[vision local] ", "[vision cloud] ")


def model_from_label(label: str) -> str:
    for prefix in _LABEL_PREFIXES:
        if label.startswith(prefix):
            return label[len(prefix) :]
    return label


def _skip_model(name: str) -> bool:
    n = name.lower()
    return any(x in n for x in ("embed", "ocr", "rerank", "whisper"))


def _is_cloud(name: str) -> bool:
    return ":cloud" in name or name.endswith("-cloud")


def _ollama_error(error: Exception, model: str = "") -> str:
    msg = str(error).lower()
    raw = str(error)
    if "subscription" in msg or "403" in raw:
        return "Modèle cloud : abonnement Ollama requis."
    if "does not support image" in msg or "image input" in msg:
        return "Ce modèle ne lit pas les images. Choisis un modèle [vision] ou renvoie l'image."
    if "400" in raw or "bad request" in msg:
        return "Requête refusée (400). Essaie avec une autre image."
    if "404" in raw or "not found" in msg:
        return f"Modèle '{model}' introuvable."
    if "connection" in msg or "refused" in msg:
        return "Ollama ne répond pas. Lance `ollama serve`."
    if "timeout" in msg:
        return "Trop long. Réessaie."
    if "500" in raw or "internal server error" in msg:
        return "Erreur Ollama (500)."
    return f"Erreur Ollama : {raw}"


def _client_ollama() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(host=config.OLLAMA_URL)
    return _client


async def _read_document(path: str) -> str:
    try:
        if path.lower().endswith(".pdf"):
            if not PDF_SUPPORT:
                return "Erreur: pypdf non installé."

            def _pdf():
                with open(path, "rb") as f:
                    return "\n".join(p.extract_text() or "" for p in PdfReader(f).pages)

            return await asyncio.to_thread(_pdf)

        if path.lower().endswith(DOCUMENT_EXTENSIONS[1:]):
            async with aiofiles.open(path, encoding="utf-8") as f:
                return await f.read()
        return "Format non supporté"
    except Exception as e:
        return f"Erreur lecture: {e}"


def _parse_list_response(listed: Any) -> list[str]:
    if hasattr(listed, "models"):
        items = listed.models
    elif isinstance(listed, dict):
        items = listed.get("models", [])
    elif isinstance(listed, (list, tuple)):
        items = listed
    else:
        items = []

    names: list[str] = []
    for item in items:
        if hasattr(item, "model"):
            name = item.model
        elif isinstance(item, dict):
            name = item.get("name")
        elif isinstance(item, str):
            name = item
        else:
            continue
        if name and not _skip_model(name):
            names.append(name)
    return names


async def _capabilities(name: str) -> list[str]:
    try:
        info = await asyncio.to_thread(ollama.show, name)
        caps = getattr(info, "capabilities", None) or []
        return [str(c) for c in caps]
    except Exception:
        return []


async def get_catalog(refresh: bool = False) -> dict[str, list[str]]:
    global _catalog
    if _catalog is not None and not refresh:
        return _catalog

    chat_local: list[str] = []
    chat_cloud: list[str] = []
    vision_local: list[str] = []
    vision_cloud: list[str] = []
    tools_local: list[str] = []
    tools_cloud: list[str] = []

    try:
        names = _parse_list_response(await asyncio.to_thread(ollama.list))
        caps_map = dict(
            zip(names, await asyncio.gather(*(_capabilities(n) for n in names)), strict=True)
        )

        for name, caps in caps_map.items():
            if not caps:
                continue
            if "tools" in caps:
                if _is_cloud(name):
                    tools_cloud.append(name)
                else:
                    tools_local.append(name)
            if "vision" in caps:
                if _is_cloud(name):
                    vision_cloud.append(name)
                else:
                    vision_local.append(name)
            elif "completion" in caps:
                if _is_cloud(name):
                    chat_cloud.append(name)
                else:
                    chat_local.append(name)
    except Exception as e:
        logger.error(f"ollama list: {e}")
        fallback = config.DEFAULT_MODEL
        _catalog = {
            "chat_local": [] if _is_cloud(fallback) else [fallback],
            "chat_cloud": [fallback] if _is_cloud(fallback) else [],
            "vision_local": [],
            "vision_cloud": [],
            "tools_local": [],
            "tools_cloud": [fallback] if _is_cloud(fallback) else [],
        }
        return _catalog

    _catalog = {
        "chat_local": sorted(chat_local),
        "chat_cloud": sorted(chat_cloud),
        "vision_local": sorted(vision_local),
        "vision_cloud": sorted(vision_cloud),
        "tools_local": sorted(tools_local),
        "tools_cloud": sorted(tools_cloud),
    }
    return _catalog


def build_model_labels(catalog: dict[str, list[str]]) -> list[str]:
    labels: list[str] = []
    for name in catalog["chat_local"]:
        labels.append(f"[local] {name}")
    for name in catalog["vision_local"]:
        labels.append(f"[vision local] {name}")
    for name in catalog["chat_cloud"]:
        labels.append(f"[cloud] {name}")
    for name in catalog["vision_cloud"]:
        labels.append(f"[vision cloud] {name}")
    return labels


def label_for_model(catalog: dict[str, list[str]], model_id: str) -> str:
    for key, prefix in (
        ("chat_local", "[local] "),
        ("vision_local", "[vision local] "),
        ("chat_cloud", "[cloud] "),
        ("vision_cloud", "[vision cloud] "),
    ):
        if model_id in catalog.get(key, []):
            return f"{prefix}{model_id}"
    return model_id


def _vision_pool(catalog: dict[str, list[str]]) -> list[str]:
    return catalog["vision_cloud"] + catalog["vision_local"]


async def vision_candidates() -> list[str]:
    catalog = await get_catalog()
    pool = _vision_pool(catalog)
    preferred = [n for n in config.VISION_MODELS if n in pool]
    return preferred + [n for n in pool if n not in preferred]


def _web_pool(catalog: dict[str, list[str]]) -> list[str]:
    tools_cloud = set(catalog.get("tools_cloud", []))
    tools_local = set(catalog.get("tools_local", []))
    pool: list[str] = []
    for name in catalog.get("chat_cloud", []):
        if name in tools_cloud:
            pool.append(name)
    for name in catalog.get("tools_cloud", []):
        if name not in pool:
            pool.append(name)
    for name in catalog.get("chat_local", []):
        if name in tools_local:
            pool.append(name)
    for name in catalog.get("tools_local", []):
        if name not in pool:
            pool.append(name)
    return pool


async def web_candidates() -> list[str]:
    catalog = await get_catalog()
    pool = _web_pool(catalog)
    preferred: list[str] = []
    for name in config.WEB_SEARCH_MODELS + [config.DEFAULT_WEB_MODEL]:
        if name in pool and name not in preferred:
            preferred.append(name)
    return preferred + [n for n in pool if n not in preferred]


def _retryable_model_error(error: Exception) -> bool:
    msg = str(error).lower()
    raw = str(error)
    if "image input" in msg or "does not support image" in msg:
        return True
    if "subscription" in msg or "403" in raw:
        return True
    if "failed to process inputs" in msg or "invalid format" in msg:
        return True
    return False


async def is_vision_model(model_id: str) -> bool:
    catalog = await get_catalog()
    return model_id in catalog["vision_cloud"] or model_id in catalog["vision_local"]


async def _flow(cb: Callable[[str, dict[str, Any]], Any] | None, kind: str, **data: Any) -> None:
    if not cb:
        return
    result = cb(kind, data)
    if asyncio.iscoroutine(result):
        await result


async def process_llm_request(
    input_message: str,
    interaction: list[dict[str, Any]],
    model_name: str,
    temperature: float = config.DEFAULT_TEMPERATURE,
    top_p: float = config.DEFAULT_TOP_P,
    max_tokens: int = config.DEFAULT_MAX_TOKENS,
    files: list[str] | None = None,
    image_paths: list[str] | None = None,
    web_search_enabled: bool = False,
    stream_callback: Callable[[str], Any] | None = None,
    flow_callback: Callable[[str, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    selected = model_from_label(model_name)
    images = list(image_paths or [])
    documents: list[str] = []

    if files:
        for path in files:
            low = path.lower()
            if not images and low.endswith(IMAGE_EXTENSIONS):
                images.append(path)
            elif low.endswith(DOCUMENT_EXTENSIONS):
                documents.append(path)

    content = input_message
    if documents:
        content += "\n\nFichiers joints :\n"
        parts = await asyncio.gather(*(_read_document(d) for d in documents))
        for path, text in zip(documents, parts, strict=True):
            content += f"\n--- {os.path.basename(path)} ---\n{text}\n"

    web_used = False
    web_sources: list[dict[str, str]] = []
    if web_search_enabled and input_message.strip():
        search_block, ok, web_sources = await search_web(input_message, on_event=flow_callback)
        if not ok:
            return {"message": {"content": search_block}, "error": True}
        if search_block:
            content += f"\n\n{search_block}"
            web_used = True

    interaction.append({"role": "user", "content": content})

    auto_vision = bool(images) and not await is_vision_model(selected)
    auto_web = web_search_enabled and bool(input_message.strip())

    if auto_vision:
        vision = await vision_candidates()
        if not vision:
            return {
                "message": {"content": "Aucun modèle vision disponible dans Ollama."},
                "error": True,
            }
        if auto_web:
            web = set(await web_candidates())
            both = [n for n in vision if n in web]
            models_to_try = both or vision
        else:
            models_to_try = vision
    elif auto_web:
        candidates = await web_candidates()
        if not candidates:
            return {
                "message": {"content": "Aucun modèle compatible recherche web (tools)."},
                "error": True,
            }
        models_to_try = candidates
    else:
        models_to_try = [selected]

    if auto_web:
        await _flow(flow_callback, "model", name=models_to_try[0])

    num_ctx = config.WEB_SEARCH_NUM_CTX if web_used else config.DEFAULT_NUM_CTX

    messages = interaction.copy()
    limit = config.MAX_CONTEXT_MESSAGES
    if len(messages) > limit + 1:
        messages = [messages[0]] + messages[-limit:]

    if images:
        try:
            encoded = await asyncio.gather(*(_encode_image(p) for p in images))
            messages[-1]["images"] = encoded  # type: ignore[index]
        except Exception as e:
            return {"message": {"content": f"Erreur images: {e}"}, "error": True}

    await _flow(flow_callback, "generating")

    full_content = ""
    last_chunk = None
    last_error: Exception | None = None
    auto_switch = auto_vision or auto_web
    for i, model in enumerate(models_to_try):
        try:
            full_content, last_chunk = await asyncio.wait_for(
                _chat_stream(
                    model,
                    messages,
                    temperature,
                    top_p,
                    max_tokens,
                    num_ctx,
                    stream_callback,
                ),
                timeout=float(config.OLLAMA_TIMEOUT),
            )
            selected = model
            break
        except asyncio.TimeoutError:
            return {"message": {"content": "Trop long. Réessaie."}, "error": True}
        except Exception as e:
            last_error = e
            if auto_switch and _retryable_model_error(e) and i < len(models_to_try) - 1:
                logger.info(f"{model} indisponible, essai suivant")
                await _flow(flow_callback, "retry", name=models_to_try[i + 1])
                continue
            logger.error(f"Ollama: {e}")
            return {"message": {"content": _ollama_error(e, model)}, "error": True}
    else:
        if last_error:
            logger.error(f"Ollama: {last_error}")
            return {"message": {"content": _ollama_error(last_error, selected)}, "error": True}

    text = (full_content or "").strip()
    if not text:
        return {"message": {"content": "Pas de réponse."}, "error": True}

    if web_sources:
        text = link_citations(text, web_sources)

    truncated = (last_chunk or {}).get("done_reason") == "length"
    if truncated:
        suffix = '\n\nRéponse coupée. Tape "continue".'
        text += suffix
        if stream_callback:
            await stream_callback(suffix)

    interaction.append({"role": "assistant", "content": text})
    await _flow(flow_callback, "done")
    return {
        "message": {"content": text},
        "model_used": selected,
        "has_images": bool(images),
        "web_used": web_used,
        "web_sources": web_sources if web_used else None,
    }


async def _encode_image(path: str) -> str:
    abs_path = os.path.abspath(path)
    validate_image_path(abs_path)
    async with aiofiles.open(abs_path, "rb") as f:
        return base64.b64encode(await f.read()).decode("utf-8")


async def _chat_stream(model, messages, temperature, top_p, max_tokens, num_ctx, stream_callback):
    parts: list[str] = []
    last = None
    stream = await _client_ollama().chat(
        model=model,
        messages=messages,
        options={
            "temperature": temperature,
            "top_p": top_p,
            "num_ctx": num_ctx,
            "num_predict": max_tokens,
        },
        stream=True,
    )
    async for chunk in stream:
        last = chunk
        part = (chunk.get("message") or {}).get("content") or ""
        parts.append(part)
        if stream_callback and part:
            await stream_callback(part)
    return "".join(parts), last
