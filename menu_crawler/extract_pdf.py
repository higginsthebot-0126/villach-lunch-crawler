from __future__ import annotations

import io
import re
from datetime import date, timedelta
from typing import List, Optional

from .models import DailyMenu, MenuItem


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


_WEEKDAY_DE_UP = ["MONTAG", "DIENSTAG", "MITTWOCH", "DONNERSTAG", "FREITAG", "SAMSTAG", "SONNTAG"]


def _parse_ddmmyyyy(s: str) -> Optional[date]:
    try:
        d, m, y = [int(x) for x in s.split(".")]
        return date(y, m, d)
    except Exception:
        return None


def _extract_date_range(text: str) -> Optional[tuple[date, date]]:
    m = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})\s*[-–]\s*(\d{1,2}\.\d{1,2}\.\d{4})", text)
    if not m:
        return None
    a = _parse_ddmmyyyy(m.group(1))
    b = _parse_ddmmyyyy(m.group(2))
    if not a or not b:
        return None
    return a, b


def _extract_brauhof_weekly_lunch(text: str, *, restaurant: str, url: str) -> List[DailyMenu]:
    """Parse Villacher Brauhof weekly lunch PDF text into DailyMenu blocks."""
    from .normalize import nonempty, clean_line, detect_allergens, detect_tags

    lines = nonempty(text.splitlines())

    # Identify weekday block boundaries
    idxs: List[tuple[int, str]] = []
    for i, ln in enumerate(lines):
        u = clean_line(ln).strip().upper()
        if u in _WEEKDAY_DE_UP:
            idxs.append((i, u))

    if not idxs:
        return []

    dr = _extract_date_range(text)
    start = dr[0] if dr else None

    menus: List[DailyMenu] = []

    for j, (i, w) in enumerate(idxs):
        end = idxs[j + 1][0] if j + 1 < len(idxs) else len(lines)
        block = lines[i + 1 : end]

        # Compute date from start+offset if we have a range and weekday is Mon..Fri.
        d: Optional[date] = None
        if start and w in _WEEKDAY_DE_UP:
            d = start + timedelta(days=_WEEKDAY_DE_UP.index(w))

        items: List[MenuItem] = []
        for ln in block:
            t = clean_line(ln)
            tl = t.lower()
            if not t:
                continue
            if t == "***" or t.strip("*") == "":
                continue
            if tl in {"oder", "und"}:
                continue
            # Skip typical footer blurbs inside the PDF
            if any(k in tl for k in ["allergen", "newsletter", "postfach", "anmelden", "vorrat", "uhr"]):
                continue
            if re.fullmatch(r"€\s*\d{1,3}([\.,]\d{1,2})?", t):
                continue

            allergens = detect_allergens(t)
            tags = detect_tags(t)
            items.append(MenuItem(text=t, allergens=allergens, tags=tags))

        if items:
            menus.append(DailyMenu(restaurant=restaurant, source_url=url, day=d, day_label=w.title(), items=items))

    return menus


def extract_menus_from_pdf(pdf_bytes: bytes, *, restaurant: str, url: str) -> List[DailyMenu]:
    """Extract menus from PDFs.

    Implemented:
    - Villacher Brauhof weekly lunch PDF (splits by weekday)

    Fallback:
    - extracts raw text and returns a single DailyMenu with one item (snippet)
    """
    from .normalize import detect_allergens, detect_tags

    txt = extract_text_from_pdf(pdf_bytes)

    # Restaurant-specific parsers
    rn = (restaurant or "").lower()
    if "brauhof" in rn:
        out = _extract_brauhof_weekly_lunch(txt, restaurant=restaurant, url=url)
        if out:
            return out

    snippet = txt[:1200].strip() if txt else ""
    item_txt = snippet if snippet else "(no text extracted: likely scanned PDF; need OCR)"

    tags = detect_tags(item_txt)
    meta = {"note": "pdf parser fallback"}

    # Cotidiano PDFs are usually a fixed menu (not a day-by-day lunch menu).
    if "cotidiano" in rn:
        meta["permanent"] = "true"
        tags = list(dict.fromkeys([*tags, "permanent"]))

    mi = MenuItem(text=item_txt, allergens=detect_allergens(item_txt), tags=tags)
    return [DailyMenu(restaurant=restaurant, source_url=url, items=[mi], meta=meta)]
