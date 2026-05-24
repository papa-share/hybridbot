import asyncio

from chatbot.pdf_loader import _find_markdown, extract_pdf_content


def test_find_markdown_by_stem(tmp_path):
    pdf = tmp_path / "doc.pdf"
    md = tmp_path / "doc.md"
    md.write_text("# Hello", encoding="utf-8")
    assert _find_markdown(tmp_path, str(pdf)) == md


def test_extract_pdf_content(monkeypatch, tmp_path):
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")

    async def fake_emit(_cb, kind, **data):
        return None

    monkeypatch.setattr("chatbot.pdf_loader.emit_flow", fake_emit)
    monkeypatch.setattr("chatbot.pdf_loader.PDF_LOADER_SUPPORT", True)
    monkeypatch.setattr(
        "chatbot.pdf_loader._convert_pdf",
        lambda _path, _out: "# Rapport\n\nContenu extrait du PDF.",
    )

    text = asyncio.run(extract_pdf_content(str(pdf), "doc.pdf", None))
    assert "Contenu extrait" in text
