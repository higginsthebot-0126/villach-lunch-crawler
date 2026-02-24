from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

from urllib.parse import urljoin

from .models import DailyMenu, MenuItem
from .normalize import nonempty, detect_allergens, detect_tags, clean_line


WEEKDAY_DE = [
    "montag",
    "dienstag",
    "mittwoch",
    "donnerstag",
    "freitag",
    "samstag",
    "sonntag",
]


@dataclass
class HtmlRule:
    restaurant: str
    url: str
    # A regex that identifies a header line for a day block.
    # Must contain named group 'date' OR 'weekday'.
    header_re: re.Pattern


def _html_to_lines(html: bytes) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    # remove script/style
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n")
    lines = nonempty(text.splitlines())
    return lines


def find_pdf_link(html: bytes, *, base_url: str, href_re: re.Pattern) -> Optional[str]:
    """Find a PDF link matching href_re and return an absolute URL.

    Some sites embed PDF.js viewer links (viewer.php?file=...). We prefer *direct* .pdf URLs.
    """
    soup = BeautifulSoup(html, "html.parser")
    candidates: List[str] = []
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        if href_re.search(href):
            candidates.append(urljoin(base_url, href))

    if not candidates:
        return None

    def score(u: str) -> tuple[int, int]:
        # lower is better
        direct = 0 if re.search(r"\.pdf(\?|#|$)", u, re.I) else 1
        viewer = 1 if "viewer.php" in u else 0
        return (direct + viewer, len(u))

    candidates.sort(key=score)
    return candidates[0]


def _parse_date(s: str) -> Optional[date]:
    try:
        # Handles 23.02.2026, 23.02, etc.
        # dateutil cannot parse trailing dots like "23.02." → strip them.
        ss = (s or "").strip()
        ss = re.sub(r"\.(\s*)$", r"\1", ss)
        ss = re.sub(r"\.(\s+)(\d{4})$", r" \2", ss)  # "23.02. 2026" -> "23.02 2026"

        # dateutil may return datetime *or* date depending on the default passed.
        dt = dateparser.parse(ss, dayfirst=True, fuzzy=True, default=date.today())
        if isinstance(dt, date) and not hasattr(dt, "date"):
            return dt
        return dt.date()  # type: ignore[union-attr]
    except Exception:
        return None


def _weekday_label_to_date(day_label: str, *, tz: str = "Europe/Vienna") -> Optional[date]:
    if not day_label:
        return None
    wl = clean_line(day_label).strip().lower()
    # allow e.g. "MONTAG" or "Montag" etc.
    if wl not in WEEKDAY_DE:
        return None

    now_vie = datetime.now(ZoneInfo(tz)).date()
    monday = now_vie - timedelta(days=now_vie.weekday())  # weekday(): Mon=0..Sun=6
    return monday + timedelta(days=WEEKDAY_DE.index(wl))


def extract_daily_menus(html: bytes, rule: HtmlRule) -> List[DailyMenu]:
    lines = _html_to_lines(html)

    menus: List[DailyMenu] = []
    cur: Optional[DailyMenu] = None

    def flush():
        nonlocal cur
        if cur and cur.items:
            menus.append(cur)
        cur = None

    for ln in lines:
        m = rule.header_re.search(ln)
        if m:
            flush()
            d: Optional[date] = None
            day_label: Optional[str] = None
            if "date" in m.groupdict() and m.group("date"):
                d = _parse_date(m.group("date"))
            if "weekday" in m.groupdict() and m.group("weekday"):
                day_label = clean_line(m.group("weekday"))
            # Some sources give weekday labels but unusable/ambiguous dates.
            # If date parsing fails, map weekday -> concrete date for *current* week (Europe/Vienna).
            if d is None and day_label:
                d = _weekday_label_to_date(day_label)
            cur = DailyMenu(restaurant=rule.restaurant, source_url=rule.url, day=d, day_label=day_label)
            continue

        if not cur:
            continue

        # skip separators
        if ln.strip("*") == "":
            continue
        if ln.strip() == "***":
            continue

        item_text = clean_line(ln)
        # ignore obvious navigation noise
        if item_text.lower().startswith("http"):
            continue
        if len(item_text) < 3:
            continue

        allergens = detect_allergens(item_text)
        tags = detect_tags(item_text)
        cur.items.append(MenuItem(text=item_text, allergens=allergens, tags=tags))

    flush()
    return menus


def rule_hotel_seven_milo(url: str) -> HtmlRule:
    # e.g. "Montag 23.02.2026"
    header_re = re.compile(r"^(?P<weekday>Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag)\s+(?P<date>\d{1,2}\.\d{1,2}\.\d{4})$", re.I)
    return HtmlRule(restaurant="Restaurant Milo (Hotel Seven)", url=url, header_re=header_re)


def rule_chickis(url: str, year: Optional[int] = None) -> HtmlRule:
    # e.g. "MONTAG, 23.02."
    header_re = re.compile(r"^(?P<weekday>MONTAG|DIENSTAG|MITTWOCH|DONNERSTAG|FREITAG|SAMSTAG|SONNTAG)\s*,\s*(?P<date>\d{1,2}\.\d{1,2}\.)(?:\s*(?P<year>\d{4}))?$", re.I)
    return HtmlRule(restaurant="Chickis Villach", url=url, header_re=header_re)
