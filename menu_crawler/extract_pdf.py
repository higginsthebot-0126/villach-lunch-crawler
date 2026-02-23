from __future__ import annotations

import io
from typing import List

from .models import DailyMenu


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract text from a PDF.

    Notes:
    - For *scanned* PDFs (images), this will return little/no text.
      In that case you need OCR (tesseract) on rendered pages.
    """
    import pdfplumber  # optional dependency, declared in requirements.txt

    buf = io.BytesIO(pdf_bytes)
    out_lines: List[str] = []
    with pdfplumber.open(buf) as pdf:
        for page in pdf.pages:
            txt = page.extract_text() or ""
            out_lines.append(txt)

    return "\n".join(out_lines).strip()


def extract_menus_from_pdf(pdf_bytes: bytes, *, restaurant: str, url: str) -> List[DailyMenu]:
    """Placeholder: PDF parsing is highly template-specific.

    Current behavior:
    - extracts raw text and returns a single DailyMenu with one item (raw text snippet)
    - meant to be replaced by per-restaurant parsers
    """
    from .models import MenuItem
    from .normalize import detect_allergens, detect_tags

    txt = extract_text_from_pdf(pdf_bytes)
    snippet = txt[:1200].strip() if txt else ""
    item_txt = snippet if snippet else "(no text extracted: likely scanned PDF; need OCR)"

    mi = MenuItem(text=item_txt, allergens=detect_allergens(item_txt), tags=detect_tags(item_txt))
    return [DailyMenu(restaurant=restaurant, source_url=url, items=[mi], meta={"note": "pdf parser placeholder"})]
