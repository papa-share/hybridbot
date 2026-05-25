from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from chatbot.document_flow import DocumentFlowUI
from chatbot.flow_ui import LLM_FLOW_EVENTS
from chatbot.web_flow import WebFlowUI


class _FlowUI(Protocol):
    async def handle(self, kind: str, data: dict) -> None: ...


async def dispatch_flow_event(
    kind: str,
    data: dict[str, Any],
    *,
    doc_flow: _FlowUI | None,
    web_flow: _FlowUI | None,
) -> None:
    if kind.startswith("doc:"):
        if doc_flow:
            await doc_flow.handle(kind[4:], data)
        return
    if kind in LLM_FLOW_EVENTS:
        target = web_flow or doc_flow
        if target:
            await target.handle(kind, data)
        return
    if web_flow:
        await web_flow.handle(kind, data)


def make_flow_handler(
    *, has_documents: bool, web_on: bool
) -> Callable[[str, dict[str, Any]], Awaitable[None]] | None:
    doc_flow: DocumentFlowUI | None = DocumentFlowUI() if has_documents else None
    web_flow: WebFlowUI | None = WebFlowUI() if web_on else None
    if not doc_flow and not web_flow:
        return None

    async def handle(kind: str, data: dict[str, Any]) -> None:
        await dispatch_flow_event(kind, data, doc_flow=doc_flow, web_flow=web_flow)

    return handle
