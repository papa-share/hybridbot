import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any

from exa_py import AsyncExa

from chatbot.config import config, logger

_exa: AsyncExa | None = None
FlowEvent = Callable[[str, dict[str, Any]], Awaitable[None] | None]

SOURCE_STAGGER_S = 0.12
_CITATION = re.compile(r"(?<!\[)\[(\d{1,2})\](?!\]|\()")


def _client() -> AsyncExa:
    global _exa
    if _exa is None:
        _exa = AsyncExa(api_key=config.EXA_API_KEY)
    return _exa


def _snippet(item) -> str:
    highlights = getattr(item, "highlights", None)
    if highlights:
        parts = highlights if isinstance(highlights, list) else [highlights]
        return " ".join(str(h) for h in parts[:3])
    text = getattr(item, "text", None) or ""
    return text[:500] if text else ""


def sources_from_items(items) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for i, item in enumerate(items, 1):
        out.append(
            {
                "index": str(i),
                "title": getattr(item, "title", "") or "Sans titre",
                "url": getattr(item, "url", "") or "",
            }
        )
    return out


def format_context(items) -> str:
    if not items:
        return "Aucun résultat web."

    lines = ["Sources web. Cite les sources avec [1], [2], etc.", ""]
    for i, item in enumerate(items, 1):
        title = getattr(item, "title", "") or "Sans titre"
        url = getattr(item, "url", "") or ""
        body = _snippet(item)
        lines.append(f"[{i}] {title}")
        if url:
            lines.append(url)
        if body:
            lines.append(body)
        lines.append("")
    return "\n".join(lines).strip()


def format_results(items) -> str:
    return format_context(items)


def link_citations(text: str, sources: list[dict[str, str]]) -> str:
    if not text or not sources:
        return text

    by_index = {int(s["index"]): s["url"] for s in sources if s.get("url") and s.get("index")}

    def repl(match: re.Match[str]) -> str:
        n = int(match.group(1))
        url = by_index.get(n)
        if url:
            return f"[[{n}]]({url})"
        return match.group(0)

    return _CITATION.sub(repl, text)


async def _emit(on_event: FlowEvent | None, kind: str, **data: Any) -> None:
    if not on_event:
        return
    result = on_event(kind, data)
    if result is not None:
        await result


async def search_web(
    query: str, on_event: FlowEvent | None = None
) -> tuple[str, bool, list[dict[str, str]]]:
    q = query.strip()
    if not q:
        return "", False, []

    if not config.EXA_API_KEY:
        return "Clé Exa manquante : ajoute EXA_API_KEY dans .env.", False, []

    preview = q if len(q) <= 120 else f"{q[:117]}..."
    await _emit(on_event, "searching", query=preview)

    try:
        response = await _client().search(
            q,
            num_results=config.WEB_SEARCH_MAX_RESULTS,
            type="auto",
            contents={"highlights": True},
        )
        items = getattr(response, "results", None) or []
        if not items:
            await _emit(on_event, "empty")
            return "Aucun résultat web.", True, []

        sources = sources_from_items(items)
        total = len(items)
        for i, item in enumerate(items, 1):
            title = getattr(item, "title", "") or "Sans titre"
            url = getattr(item, "url", "") or ""
            await _emit(on_event, "source", index=i, total=total, title=title, url=url)
            if i < total:
                await asyncio.sleep(SOURCE_STAGGER_S)

        await _emit(on_event, "sources_done", count=total)
        return format_context(items), True, sources
    except Exception as e:
        logger.error(f"exa search: {e}")
        raw = str(e).lower()
        await _emit(on_event, "error", message=str(e))
        if "401" in raw or "api key" in raw or "unauthorized" in raw:
            return "Clé Exa invalide. Vérifie EXA_API_KEY dans .env.", False, []
        if "429" in raw or "rate limit" in raw:
            return "Quota Exa dépassé. Réessaie plus tard.", False, []
        return f"Recherche web impossible : {e}", False, []
