import asyncio

from chatbot.flow import dispatch_flow_event, make_flow_handler


class _FakeFlow:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def handle(self, kind: str, data: dict) -> None:
        self.events.append((kind, data))


def test_make_flow_handler_none_when_idle():
    assert make_flow_handler(has_documents=False, web_on=False) is None


def test_doc_events_only_on_document_flow():
    doc = _FakeFlow()
    web = _FakeFlow()

    asyncio.run(
        dispatch_flow_event("doc:extract_start", {"name": "x.pdf"}, doc_flow=doc, web_flow=web)
    )

    assert doc.events == [("extract_start", {"name": "x.pdf"})]
    assert web.events == []


def test_llm_events_prefer_web_when_both_flows():
    doc = _FakeFlow()
    web = _FakeFlow()

    asyncio.run(dispatch_flow_event("generating", {}, doc_flow=doc, web_flow=web))

    assert doc.events == []
    assert web.events == [("generating", {})]


def test_llm_events_on_document_when_no_web():
    doc = _FakeFlow()

    asyncio.run(dispatch_flow_event("done", {}, doc_flow=doc, web_flow=None))

    assert doc.events == [("done", {})]


def test_web_search_events_only_on_web_flow():
    doc = _FakeFlow()
    web = _FakeFlow()

    asyncio.run(dispatch_flow_event("searching", {"query": "test"}, doc_flow=doc, web_flow=web))

    assert doc.events == []
    assert web.events == [("searching", {"query": "test"})]
