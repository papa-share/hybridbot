import asyncio
import os
import tempfile
from pathlib import Path

from chatbot.flow_events import emit_flow

try:
    import opendataloader_pdf

    PDF_LOADER_SUPPORT = True
except ImportError:
    PDF_LOADER_SUPPORT = False


def _find_markdown(out_dir: Path, pdf_path: str) -> Path:
    stem = Path(pdf_path).stem
    direct = out_dir / f"{stem}.md"
    if direct.is_file():
        return direct
    matches = sorted(out_dir.glob("*.md"))
    if matches:
        return matches[0]
    raise FileNotFoundError("Markdown introuvable après conversion")


def _convert_pdf(path: str, out_dir: str) -> str:
    opendataloader_pdf.convert(
        input_path=[path],
        output_dir=out_dir,
        format="markdown",
        quiet=True,
    )
    return _find_markdown(Path(out_dir), path).read_text(encoding="utf-8")


async def extract_pdf_content(
    path: str,
    name: str,
    flow_callback,
) -> str:
    if not PDF_LOADER_SUPPORT:
        return "Erreur: opendataloader-pdf non installé."

    label = name or os.path.basename(path)
    await emit_flow(flow_callback, "doc:extract_start", name=label)
    await emit_flow(flow_callback, "doc:extracting", message="Extraction en cours")

    try:
        with tempfile.TemporaryDirectory(prefix="odl_") as tmp:
            text = await asyncio.to_thread(_convert_pdf, path, tmp)
    except Exception as e:
        await emit_flow(flow_callback, "doc:error", message="Échec extraction")
        return f"Erreur extraction PDF: {e}"

    text = text.strip()
    if not text:
        await emit_flow(flow_callback, "doc:error", message="Document vide")
        return "PDF sans texte extractible (couche texte absente)."

    await emit_flow(flow_callback, "doc:extract_done")
    return text
