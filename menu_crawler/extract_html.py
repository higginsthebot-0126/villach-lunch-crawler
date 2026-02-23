from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from bs4 import BeautifulSoup
from dateutil import parser as dateparser

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


def _parse_date(s: str) -> Optional[date]:
    try:
        # Handles 23.02.2026, 23.02., etc.
        # dateutil may return datetime *or* date depending on the default passed.
        dt = dateparser.parse(s, dayfirst=True, fuzzy=True, default=date.today())
        if isinstance(dt, date) and not hasattr(dt, "date"):
            return dt
        return dt.date()  # type: ignore[union-attr]
    except Exception:
        return None


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
