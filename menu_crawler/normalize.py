from __future__ import annotations

import re
from typing import Iterable, List

LACTOSE_KEYWORDS = [
    r"\bmilch\b",
    r"\bka?e?se\b",  # käse/kaese
    r"\bparmesan\b",
    r"\brahm\b",
    r"\bsauerrahm\b",
    r"\bfrischk(a|ä)se\b",
    r"\bbutter\b",
]

CURRY_KEYWORDS = [r"\bcurry\b"]

ALLERGEN_CODE_RE = re.compile(r"\((?P<codes>[A-N](?:\s*,\s*[A-N])*)\)")


def detect_allergens(text: str) -> List[str]:
    """Return list of detected allergen codes (A-N). Currently focuses on G (milk).

    If explicit codes like "(A, G)" are present, we return them.
    Otherwise we apply heuristics for milk/lactose -> G.
    """
    t = text.strip()
    codes: List[str] = []

    m = ALLERGEN_CODE_RE.search(t)
    if m:
        raw = m.group("codes")
        for c in re.split(r"\s*,\s*", raw.strip()):
            c = c.strip().upper()
            if c and c not in codes:
                codes.append(c)

    # heuristic lactose
    low = t.lower()
    if any(re.search(p, low) for p in LACTOSE_KEYWORDS):
        if "G" not in codes:
            codes.append("G")

    return codes


def detect_tags(text: str) -> List[str]:
    low = text.lower()
    tags: List[str] = []
    if any(re.search(p, low) for p in CURRY_KEYWORDS):
        tags.append("curry")
    # lactose tag if milk allergen detected
    if "G" in detect_allergens(text):
        tags.append("lactose")
    return tags


def clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    return line


def nonempty(lines: Iterable[str]) -> List[str]:
    out: List[str] = []
    for ln in lines:
        ln = clean_line(ln)
        if ln:
            out.append(ln)
    return out
