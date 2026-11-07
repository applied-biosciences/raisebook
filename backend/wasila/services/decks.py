"""The deck editor (Wasila v1.0.0.0): read a PowerPoint deck from the Funding Room, change its
text, hide or reorder slides, and save the result as a **new version** of the same document.

Only text changes: layout, images, charts and fonts stay exactly as designed. A text edit
keeps the formatting of the first run of each paragraph. The original version is never
modified (versions are immutable), so every edit can be undone by downloading an earlier
version.
"""

from __future__ import annotations

import copy
import io
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.util import Emu

from wasila.core.errors import APIError, ValidationFailed

QN_P = "{http://schemas.openxmlformats.org/drawingml/2006/main}p"


def invalid(message: str, field: str = "body") -> ValidationFailed:
    return ValidationFailed(field, message)


class PdfUnavailable(APIError):
    status_code = 503
    code = "pdf_unavailable"
    default_message = (
        "PDF export needs LibreOffice on the server. Download the PowerPoint file and use "
        "File → Export → PDF instead."
    )


@dataclass
class Edit:
    slide: int
    shape: int
    text: str


def _open(data: bytes) -> Any:
    try:
        return Presentation(io.BytesIO(data))
    except Exception as exc:  # zip, xml and python-pptx errors alike
        raise invalid("This is not a readable PowerPoint (.pptx) file.", "file") from exc


def read(data: bytes) -> dict[str, Any]:
    """Slides with their text shapes: ``{slides: [{slide, hidden, title, shapes: [...]}]}``."""
    prs = _open(data)
    slides = []
    for n, slide in enumerate(prs.slides, start=1):
        shapes = []
        for shape in slide.shapes:
            if not shape.has_text_frame or not shape.text_frame.text.strip():
                continue
            shapes.append(
                {
                    "shape": shape.shape_id,
                    "name": shape.name,
                    "text": shape.text_frame.text,
                    "top": int(Emu(shape.top or 0)),
                }
            )
        shapes.sort(key=lambda s: s["top"])
        for s in shapes:
            s.pop("top")
        slides.append(
            {
                "slide": n,
                "hidden": slide._element.get("show") == "0",
                "title": shapes[0]["text"].split("\n")[0][:120] if shapes else f"Slide {n}",
                "shapes": shapes,
            }
        )
    return {
        "slides": slides,
        "width": int(prs.slide_width or 0),
        "height": int(prs.slide_height or 0),
    }


def _set_text(shape: Any, text: str) -> None:
    tf = shape.text_frame
    lines = text.replace("\r\n", "\n").split("\n")
    paras = list(tf.paragraphs)
    # Grow by cloning the last paragraph (keeps its bullet level and formatting).
    while len(paras) < len(lines):
        clone = copy.deepcopy(paras[-1]._p)
        paras[-1]._p.addnext(clone)
        paras = list(tf.paragraphs)
    for i, para in enumerate(paras):
        if i >= len(lines):
            para._p.getparent().remove(para._p)
            continue
        runs = list(para.runs)
        if runs:
            runs[0].text = lines[i]
            for r in runs[1:]:
                r._r.getparent().remove(r._r)
        else:
            para.text = lines[i]


def apply(
    data: bytes,
    *,
    edits: list[Edit],
    hidden: list[int] | None = None,
    order: list[int] | None = None,
) -> bytes:
    """A new .pptx: ``edits`` replace shape text, ``hidden`` lists the slides to hide (all
    others are shown), ``order`` is the new slide order (every slide number exactly once)."""
    prs = _open(data)
    slides = list(prs.slides)
    count = len(slides)
    for e in edits:
        if not 1 <= e.slide <= count:
            raise invalid(f"Slide {e.slide} does not exist (the deck has {count}).", "edits")
        target = next((s for s in slides[e.slide - 1].shapes if s.shape_id == e.shape), None)
        if target is None or not target.has_text_frame:
            raise invalid(f"Slide {e.slide} has no text shape {e.shape}.", "edits")
        if len(e.text) > 4000:
            raise invalid("Each text can be at most 4,000 characters.", "edits")
        _set_text(target, e.text)
    if hidden is not None:
        bad = [n for n in hidden if not 1 <= n <= count]
        if bad:
            raise invalid(f"Slides {bad} do not exist.", "hidden")
        if len(set(hidden)) >= count:
            raise invalid("At least one slide must stay visible.", "hidden")
        for n, slide in enumerate(slides, start=1):
            if n in hidden:
                slide._element.set("show", "0")
            elif "show" in slide._element.attrib:
                del slide._element.attrib["show"]
    if order is not None:
        if sorted(order) != list(range(1, count + 1)):
            raise invalid(f"order must list every slide 1 to {count} exactly once.", "order")
        lst = prs.slides._sldIdLst
        ids = list(lst)
        for el in ids:
            lst.remove(el)
        for n in order:
            lst.append(ids[n - 1])
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


def _mac_soffice() -> str | None:
    """LibreOffice installed as a macOS app (``brew install --cask libreoffice``) is not on PATH."""
    import os

    for app in (
        "/Applications/LibreOffice.app",
        os.path.expanduser("~/Applications/LibreOffice.app"),
    ):
        exe = os.path.join(app, "Contents", "MacOS", "soffice")
        if os.access(exe, os.X_OK):
            return exe
    return None


def to_pdf(data: bytes) -> bytes:
    soffice = shutil.which("soffice") or shutil.which("libreoffice") or _mac_soffice()
    if soffice is None:
        raise PdfUnavailable()
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "deck.pptx"
        src.write_bytes(data)
        try:
            subprocess.run(  # noqa: S603 - fixed argv, our own temp file
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, str(src)],
                check=True,
                timeout=120,
                capture_output=True,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            raise PdfUnavailable(
                "The PDF could not be made. Try again, or export it in PowerPoint."
            ) from exc
        pdf = Path(tmp) / "deck.pdf"
        if not pdf.exists():
            raise PdfUnavailable(
                "The PDF could not be made. Try again, or export it in PowerPoint."
            )
        return pdf.read_bytes()
