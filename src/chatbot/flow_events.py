import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

FlowEvent = Callable[[str, dict[str, Any]], Awaitable[None] | None]


async def emit_flow(on_event: FlowEvent | None, kind: str, **data: Any) -> None:
    if not on_event:
        return
    result = on_event(kind, data)
    if asyncio.iscoroutine(result):
        await result
