import asyncio
import re

from exa_py import AsyncExa

from chatbot.config import config, logger
from chatbot.flow_events import FlowEvent, emit_flow, safe_emit

_exa: AsyncExa | None = None
SOURCE_STAGGER_S = 0.12
_CITATION_DAGGER = re.compile(r"\[(\d{1,2})[†][^\]]*\]", re.I)
_CITATION_FULLWIDTH = re.compile(r"【(\d{1,2})(?:†[^】]*)?】")
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


def _exa_attr(item, name: str, default: str = "") -> str:
    return getattr(item, name, None) or default


def _source_rows(items) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for i, item in enumerate(items, 1):
        rows.append(
            {
                "index": str(i),
                "title": _exa_attr(item, "title", "Sans titre"),
                "url": _exa_attr(item, "url"),
                "body": _snippet(item),
            }
        )
    return rows


def sources_from_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{"index": row["index"], "title": row["title"], "url": row["url"]} for row in rows]


def sources_from_items(items) -> list[dict[str, str]]:
    return sources_from_rows(_source_rows(items))


def _format_context_rows(rows: list[dict[str, str]]) -> str:
    lines = [
        "Contexte web (interne). Cite uniquement avec [1], [2], etc. (crochets ASCII) dans le corps du texte.",
        "Ne termine pas par une section Sources : les renvois [n] suffisent.",
        "Markdown uniquement, pas de HTML.",
        "",
    ]
    for row in rows:
        lines.append(f"[{row['index']}] {row['title']}")
        if row["url"]:
            lines.append(row["url"])
        if row["body"]:
            lines.append(row["body"])
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

    for pattern in (_CITATION_DAGGER, _CITATION_FULLWIDTH, _CITATION_BARE, _SOURCE, _CITATION):
        text = pattern.sub(repl, text)
    return text


def strip_sources_footer(text: str) -> str:
    if not text:
        return text
    match = _SOURCES_FOOTER.search(text)
    if match:
        return text[: match.start()].rstrip()
    return text


def _error_detail(exc: Exception) -> str:
    msg = str(exc).strip()
    if msg:
        return msg
    return f"{type(exc).__name__}"


def _exa_user_message(exc: Exception) -> str:
    detail = _error_detail(exc).lower()
    if isinstance(exc, TimeoutError):
        return "Exa ne répond pas. Réessaie."
    if isinstance(exc, OSError):
        return "Connexion Exa impossible."
    if "401" in detail or "api key" in detail or "unauthorized" in detail:
        return "Clé Exa invalide."
    if "429" in detail or "rate limit" in detail:
        return "Quota Exa dépassé."
    return "Recherche web impossible."


async def _emit_source_rows(rows: list[dict[str, str]], on_event: FlowEvent | None) -> None:
    total = len(rows)
    for row in rows:
        index = int(row["index"])
        title = row["title"]
        url = row["url"]
        await safe_emit(
            on_event,
            "source",
            log_label="exa ui source",
            index=index,
            total=total,
            title=title,
            url=url,
        )
        if index < total:
            await asyncio.sleep(SOURCE_STAGGER_S)
    await safe_emit(on_event, "sources_done", log_label="exa ui done", count=total)


async def search_web(
    query: str, on_event: FlowEvent | None = None
) -> tuple[str, bool, list[dict[str, str]]]:
    q = query.strip()
    if not q:
        return "", False, []

    if not config.EXA_API_KEY:
        return "Recherche web indisponible.", False, []

    preview = q if len(q) <= 120 else f"{q[:117]}..."
    await safe_emit(on_event, "searching", log_label="exa ui search", query=preview)

    try:
        response = await _client().search(
            q,
            num_results=config.WEB_SEARCH_MAX_RESULTS,
            type="auto",
            contents={"highlights": True},
        )
    except Exception as exc:
        logger.error(f"exa search: {_error_detail(exc)}")
        message = _exa_user_message(exc)
        await safe_emit(on_event, "error", log_label="exa ui error", message=message)
        return message, False, []

    items = getattr(response, "results", None) or []
    if not items:
        await emit_flow(on_event, "empty")
        return "Aucun résultat web.", True, []

    rows = _source_rows(items)
    sources = sources_from_rows(rows)
    await _emit_source_rows(rows, on_event)
    return _format_context_rows(rows), True, sources
