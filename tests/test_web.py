from chatbot.llm import _web_pool
from chatbot.web import format_context, format_results, link_citations, sources_from_items


class _Item:
    def __init__(self, title, url, highlights=None, text=""):
        self.title = title
        self.url = url
        self.highlights = highlights
        self.text = text


def test_format_results():
    out = format_results(
        [
            _Item("Titre", "https://exa.ai", highlights=["extrait utile"]),
        ]
    )
    assert "[1]" in out
    assert "https://exa.ai" in out
    assert "extrait utile" in out
    assert "cite" in out.lower() or "Cite" in out


def test_format_context_numbered():
    out = format_context([_Item("Le Monde", "https://lemonde.fr")])
    assert out.startswith("Sources web")
    assert "[1] Le Monde" in out


def test_sources_from_items():
    sources = sources_from_items([_Item("A", "https://a.com"), _Item("B", "https://b.com")])
    assert sources == [
        {"index": "1", "title": "A", "url": "https://a.com"},
        {"index": "2", "title": "B", "url": "https://b.com"},
    ]


def test_link_citations():
    sources = [
        {"index": "1", "title": "A", "url": "https://a.com"},
        {"index": "2", "title": "B", "url": "https://b.com"},
    ]
    out = link_citations("D'après [1], confirmé par [2].", sources)
    assert out == "D'après [[1]](https://a.com), confirmé par [[2]](https://b.com)."


def test_link_citations_skips_linked():
    sources = [{"index": "1", "title": "A", "url": "https://a.com"}]
    text = "Voir [[1]](https://a.com) déjà lié."
    assert link_citations(text, sources) == text


def test_web_pool_cloud_chat_first():
    catalog = {
        "chat_cloud": ["gpt-oss:120b-cloud", "nemotron-3-super:cloud"],
        "chat_local": ["llama3.2:latest"],
        "tools_cloud": ["nemotron-3-super:cloud", "gpt-oss:120b-cloud", "gemma4:31b-cloud"],
        "tools_local": ["llama3.2:latest"],
    }
    assert _web_pool(catalog) == [
        "gpt-oss:120b-cloud",
        "nemotron-3-super:cloud",
        "gemma4:31b-cloud",
        "llama3.2:latest",
    ]
