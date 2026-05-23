import asyncio
import re
from collections.abc import Awaitable, Callable
from typing import Any

from exa_py import AsyncExa

from chatbot.config import config, logger

_exa: AsyncExa | None = None
FlowEvent = Callable[[str, dict[str, Any]], Awaitable[None] | None]

SOURCE_STAGGER_S = 0.12
_CITATION_DAGGER = re.compile(r"\[(\d{1,2})[†][^\]]*\]", re.I)
_CITATION = re.compile(r"(?<!\[)\[(\d{1,2})\](?!\]|\()", re.I)
_CITATION_BARE = re.compile(r"\[\[(\d{1,2})\]\](?!\()")
_SOURCE = re.compile(r"\(source\s*(\d{1,2})\)", re.I)
_HTML_BREAK = re.compile(r"<br\s*/?>", re.I)
_HTML_BLOCK = re.compile(r"</?(?:p|div|li|tr|h[1-6])\s*>", re.I)
_HTML_TAG = re.compile(r"<[^>]+>")
_SOURCES_FOOTER = re.compile(
    r"\n+(?:#{1,3}\s*)?(?:\*{1,2})?\s*Sources\s*:?\s*(?:\*{1,2})?\s*\n",
    re.I,
)


def normalize_response(text: str) -> str:
    if not text:
        return text
    text = _HTML_BREAK.sub("\n", text)
    text = _HTML_BLOCK.sub("\n", text)
    text = _HTML_TAG.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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

    lines = [
        "Contexte web (interne). Cite uniquement avec [1], [2], etc. dans le corps du texte.",
        "Ne termine pas par une section Sources : les renvois [n] suffisent.",
        "Markdown uniquement, pas de HTML.",
        "",
    ]
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


def link_citations(text: str, sources: list[dict[str, str]]) -> str:
    if not text or not sources:
        return text

    by_index = {int(s["index"]): s["url"] for s in sources if s.get("url") and s.get("index")}

    def repl(match: re.Match[str]) -> str:
        n = int(match.group(1))
        url = by_index.get(n)
        if url:
            return f"[{n}]({url})"
        return match.group(0)

    for pattern in (_CITATION_DAGGER, _CITATION_BARE, _SOURCE, _CITATION):
        text = pattern.sub(repl, text)
    return text


def strip_sources_footer(text: str) -> str:
    if not text:
        return text
    match = _SOURCES_FOOTER.search(text)
    if match:
        return text[: match.start()].rstrip()
    return text


async def emit_flow(on_event: FlowEvent | None, kind: str, **data: Any) -> None:
    if not on_event:
        return
    result = on_event(kind, data)
    if asyncio.iscoroutine(result):
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
            await emit_flow(on_event, "empty")
            return "Aucun résultat web.", True, []

        sources = sources_from_items(items)
        total = len(items)
        for i, item in enumerate(items, 1):
            title = getattr(item, "title", "") or "Sans titre"
            url = getattr(item, "url", "") or ""
            await emit_flow(on_event, "source", index=i, total=total, title=title, url=url)
            if i < total:
                await asyncio.sleep(SOURCE_STAGGER_S)

        await emit_flow(on_event, "sources_done", count=total)
        return format_context(items), True, sources
    except Exception as e:
        logger.error(f"exa search: {e}")
        raw = str(e).lower()
        await emit_flow(on_event, "error", message=str(e))
        if "401" in raw or "api key" in raw or "unauthorized" in raw:
            return "Clé Exa invalide. Vérifie EXA_API_KEY dans .env.", False, []
        if "429" in raw or "rate limit" in raw:
            return "Quota Exa dépassé. Réessaie plus tard.", False, []
        return f"Recherche web impossible : {e}", False, []
