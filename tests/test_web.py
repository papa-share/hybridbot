from chatbot.llm import _web_pool
from chatbot.web import format_context, link_citations, normalize_response, sources_from_items, strip_sources_footer


class _Item:
    def __init__(self, title, url, highlights=None, text=""):
        self.title = title
        self.url = url
        self.highlights = highlights
        self.text = text


def test_format_context_numbered():
    out = format_context([_Item("Le Monde", "https://lemonde.fr")])
    assert out.startswith("Contexte web")
    assert "[1] Le Monde" in out


def test_format_context_highlights():
    out = format_context([_Item("Titre", "https://exa.ai", highlights=["extrait utile"])])
    assert "[1]" in out
    assert "https://exa.ai" in out
    assert "extrait utile" in out


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
    assert out == "D'après [1](https://a.com), confirmé par [2](https://b.com)."


def test_link_citations_bare_and_source():
    sources = [{"index": "1", "title": "A", "url": "https://a.com"}]
    assert link_citations("Voir [[1]] et (source 1).", sources) == (
        "Voir [1](https://a.com) et [1](https://a.com)."
    )


def test_link_citations_dagger():
    sources = [{"index": "1", "title": "A", "url": "https://a.com"}]
    text = "Info [1†L-Iran-accuse-les-Etats-Unis] fin."
    assert link_citations(text, sources) == "Info [1](https://a.com) fin."


def test_link_citations_skips_linked():
    sources = [{"index": "1", "title": "A", "url": "https://a.com"}]
    text = "Voir [1](https://a.com) déjà lié."
    assert link_citations(text, sources) == text


def test_normalize_response():
    assert normalize_response("Ligne<br/>suite<p>fin</p>") == "Ligne\nsuite\nfin"


def test_strip_sources_footer():
    body = "Point [1] et [2].\n\n**Sources :**\n1. A — lien\n2. B — lien"
    assert strip_sources_footer(body) == "Point [1] et [2]."


def test_strip_sources_footer_keeps_body():
    text = "Réponse sans liste."
    assert strip_sources_footer(text) == text


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
