import asyncio

from chatbot.flow_events import emit_flow


def test_emit_flow_no_callback():
    asyncio.run(emit_flow(None, "done"))


def test_emit_flow_sync_callback():
    events: list[tuple[str, dict]] = []

    def on_event(kind: str, data: dict) -> None:
        events.append((kind, data))

    asyncio.run(emit_flow(on_event, "source", index=1, total=2, title="Test", url="https://x"))

    assert events == [("source", {"index": 1, "total": 2, "title": "Test", "url": "https://x"})]


def test_emit_flow_async_callback():
    events: list[str] = []

    async def on_event(kind: str, _data: dict) -> None:
        events.append(kind)

    asyncio.run(emit_flow(on_event, "done"))

    assert events == ["done"]
