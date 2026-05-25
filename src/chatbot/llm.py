import asyncio
import base64
import os
import time
from collections.abc import Callable
from typing import Any

import aiofiles
import ollama
from ollama import AsyncClient

from chatbot.config import config, is_pdf_source, is_text_document_source, logger
from chatbot.flow_events import emit_flow
from chatbot.pdf_loader import extract_pdf_content
from chatbot.validators import validate_image_path
from chatbot.web import (
    link_citations,
    normalize_response,
    search_web,
    strip_sources_footer,
)

_client: AsyncClient | None = None
_catalog: dict[str, list[str]] | None = None
_catalog_fetched_at: float = 0.0

_CATALOG_PREFIXES = (
    ("chat_local", "[local] "),
    ("vision_local", "[vision local] "),
    ("chat_cloud", "[cloud] "),
    ("vision_cloud", "[vision cloud] "),
)


def _rank_preferred(pool: list[str], preferred: list[str]) -> list[str]:
    return preferred + [name for name in pool if name not in preferred]


def model_from_label(label: str) -> str:
    for _, prefix in _CATALOG_PREFIXES:
        if label.startswith(prefix):
            return label[len(prefix) :]
    return label


def _skip_model(name: str) -> bool:
    n = name.lower()
    return any(x in n for x in ("embed", "ocr", "rerank", "whisper"))


def _is_cloud(name: str) -> bool:
    return ":cloud" in name or name.endswith("-cloud")


def _fail(content: str) -> dict[str, Any]:
    return {"message": {"content": content}, "error": True}


def _classify_ollama_error(error: Exception, model: str = "") -> tuple[str, bool]:
    msg = str(error).lower()
    if "subscription" in msg or "403" in str(error):
        return "Modèle cloud : abonnement Ollama requis.", True
    if "does not support image" in msg or "image input" in msg:
        return "Modèle sans vision.", True
    if "404" in str(error) or "not found" in msg:
        return f"Modèle '{model}' introuvable.", False
    if "connection" in msg or "refused" in msg:
        return "Ollama ne répond pas.", False
    if isinstance(error, asyncio.TimeoutError) or "timed out" in msg:
        return "Trop long. Réessaie.", False
    return "Erreur Ollama.", False


def _client_ollama() -> AsyncClient:
    global _client
    if _client is None:
        _client = AsyncClient(host=config.OLLAMA_URL)
    return _client


async def _read_document(path: str, mime: str = "", name: str = "") -> str:
    try:
        if is_text_document_source(path=path, mime=mime, name=name):
            async with aiofiles.open(path, encoding="utf-8") as handle:
                return await handle.read()
        return "Format non supporté"
    except Exception as e:
        return f"Erreur lecture: {e}"


async def _load_document_text(
    path: str,
    mime: str,
    name: str,
    flow_callback: Callable[[str, dict[str, Any]], Any] | None,
) -> str:
    if is_pdf_source(path=path, mime=mime, name=name):
        return await extract_pdf_content(path, name, flow_callback)
    return await _read_document(path, mime, name)


def _file_spec(item: str | tuple[str, str, str]) -> tuple[str, str, str]:
    if isinstance(item, str):
        path = item
        return path, "", os.path.basename(path)
    path, mime, name = item
    return str(path), mime or "", name or os.path.basename(path)


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


def invalidate_catalog() -> None:
    global _catalog, _catalog_fetched_at
    _catalog = None
    _catalog_fetched_at = 0.0


def _catalog_is_stale() -> bool:
    if _catalog is None:
        return True
    age = time.monotonic() - _catalog_fetched_at
    return age >= float(config.OLLAMA_CATALOG_TTL)


async def get_catalog(refresh: bool = False) -> dict[str, list[str]]:
    global _catalog, _catalog_fetched_at
    if _catalog is not None and not refresh and not _catalog_is_stale():
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
        _catalog_fetched_at = time.monotonic()
        return _catalog

    _catalog = {
        "chat_local": sorted(chat_local),
        "chat_cloud": sorted(chat_cloud),
        "vision_local": sorted(vision_local),
        "vision_cloud": sorted(vision_cloud),
        "tools_local": sorted(tools_local),
        "tools_cloud": sorted(tools_cloud),
    }
    _catalog_fetched_at = time.monotonic()
    return _catalog


def build_model_labels(catalog: dict[str, list[str]]) -> list[str]:
    labels: list[str] = []
    for key, prefix in _CATALOG_PREFIXES:
        for name in catalog[key]:
            labels.append(f"{prefix}{name}")
    return labels


def label_for_model(catalog: dict[str, list[str]], model_id: str) -> str:
    for key, prefix in _CATALOG_PREFIXES:
        if model_id in catalog.get(key, []):
            return f"{prefix}{model_id}"
    return model_id


def _vision_pool(catalog: dict[str, list[str]]) -> list[str]:
    return catalog["vision_cloud"] + catalog["vision_local"]


def _vision_candidates(catalog: dict[str, list[str]]) -> list[str]:
    pool = _vision_pool(catalog)
    preferred = [name for name in config.VISION_MODELS if name in pool]
    return _rank_preferred(pool, preferred)


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


def _web_candidates(catalog: dict[str, list[str]]) -> list[str]:
    pool = _web_pool(catalog)
    preferred: list[str] = []
    for name in config.WEB_SEARCH_MODELS + [config.DEFAULT_WEB_MODEL]:
        if name in pool and name not in preferred:
            preferred.append(name)
    return _rank_preferred(pool, preferred)


def _is_vision_model(model_id: str, catalog: dict[str, list[str]]) -> bool:
    return model_id in catalog["vision_cloud"] or model_id in catalog["vision_local"]


async def process_llm_request(
    input_message: str,
    interaction: list[dict[str, Any]],
    ui_model_label: str,
    temperature: float = config.DEFAULT_TEMPERATURE,
    top_p: float = config.DEFAULT_TOP_P,
    max_tokens: int = config.DEFAULT_MAX_TOKENS,
    files: list[str | tuple[str, str, str]] | None = None,
    image_paths: list[str] | None = None,
    web_search_enabled: bool = False,
    stream_callback: Callable[[str], Any] | None = None,
    flow_callback: Callable[[str, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    selected = model_from_label(ui_model_label)
    images = list(image_paths or [])
    documents = list(files or [])

    content = input_message
    catalog = await get_catalog()

    if documents:
        specs = [_file_spec(item) for item in documents]
        parts = await asyncio.gather(
            *(_load_document_text(path, mime, name, flow_callback) for path, mime, name in specs)
        )
        failures = [
            f"{name or os.path.basename(path)}: {text}"
            for (path, _, name), text in zip(specs, parts, strict=True)
            if text.startswith("Erreur")
            or "sans contenu extractible" in text
            or text == "Format non supporté"
        ]
        if failures:
            await emit_flow(flow_callback, "error", message=failures[0])
            return _fail("\n".join(failures))

        content += "\n\nFichiers joints :\n"
        for (path, _, name), text in zip(specs, parts, strict=True):
            content += f"\n--- {name or os.path.basename(path)} ---\n{text}\n"

    web_used = False
    web_sources: list[dict[str, str]] = []
    if web_search_enabled and input_message.strip():
        search_block, ok, web_sources = await search_web(input_message, on_event=flow_callback)
        if not ok:
            return _fail(search_block)
        if search_block:
            content += f"\n\n{search_block}"
            web_used = True

    interaction.append({"role": "user", "content": content})

    auto_vision = bool(images) and not _is_vision_model(selected, catalog)
    auto_web = web_search_enabled and bool(input_message.strip())

    if auto_vision:
        vision = _vision_candidates(catalog)
        if not vision:
            return _fail("Aucun modèle vision disponible dans Ollama.")
        if auto_web:
            web = set(_web_candidates(catalog))
            both = [n for n in vision if n in web]
            models_to_try = both or vision
        else:
            models_to_try = vision
    elif auto_web:
        candidates = _web_candidates(catalog)
        if not candidates:
            return _fail("Aucun modèle compatible recherche web (tools).")
        models_to_try = candidates
    else:
        models_to_try = [selected]

    if auto_web:
        await emit_flow(flow_callback, "model", name=models_to_try[0])

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
            return _fail(f"Erreur images: {e}")

    await emit_flow(flow_callback, "generating")

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
            return _fail("Trop long. Réessaie.")
        except Exception as e:
            last_error = e
            message, retryable = _classify_ollama_error(e, model)
            if auto_switch and retryable and i < len(models_to_try) - 1:
                logger.info(f"{model} indisponible, essai suivant")
                await emit_flow(flow_callback, "retry", name=models_to_try[i + 1])
                continue
            logger.error(f"Ollama: {e}")
            return _fail(message)
    else:
        if last_error:
            message, _ = _classify_ollama_error(last_error, selected)
            logger.error(f"Ollama: {last_error}")
            return _fail(message)

    text = normalize_response(full_content or "")
    if not text:
        return _fail("Pas de réponse.")

    if web_sources:
        text = strip_sources_footer(text)
        text = link_citations(text, web_sources)

    truncated = (last_chunk or {}).get("done_reason") == "length"
    if truncated:
        suffix = '\n\nRéponse coupée. Tape "continue".'
        text += suffix
        if stream_callback:
            await stream_callback(suffix)

    interaction.append({"role": "assistant", "content": text})
    await emit_flow(flow_callback, "done")
    return {
        "message": {"content": text},
        "model_used": selected,
        "has_images": bool(images),
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
