from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from .crawl import crawl_source


# --- Post-extraction QC / noise filtering ------------------------------------

_QC_STOPWORDS = [
    # consent / legal / nav
    "cookie",
    "cookies",
    "datenschutz",
    "privacy",
    "impressum",
    "kontakt",
    "contact",
    "newsletter",
    "agb",
    "jobs",
    "karriere",
    "reservierung",
    "reservation",
    "öffnungszeiten",
    "oeffnungszeiten",
    "adresse",
    "telefon",
    "phone",
    "facebook",
    "instagram",
    "tiktok",
    "youtube",
    "navigation",
    "home",
    "startseite",
    "standort",
    "gutschein",
]


def qc_item_text(text: str) -> Dict[str, Any]:
    """Heuristics to mark likely non-menu 'noise' items.

    Returns a dict meant to be embedded under item['qc'].
    """
    t = (text or "").strip()
    tl = t.lower()
    flags: List[str] = []

    if not t:
        return {"isNoise": True, "confidence": 0.0, "flags": ["empty"]}

    # Strong signals
    if "http://" in tl or "https://" in tl or "www." in tl:
        flags.append("has_url")
    if "@" in t and "." in t:
        flags.append("has_email")
    if "©" in t or "copyright" in tl:
        flags.append("copyright")

    # cookie / privacy / legal / nav words
    for w in _QC_STOPWORDS:
        if w in tl:
            flags.append(f"stopword:{w}")
            break

    # phone-like (very rough)
    import re

    if re.search(r"\b\+?\d{2,4}\s*\(?\d{1,4}\)?[\s\-/]*\d{2,}\b", t):
        flags.append("has_phone")

    # Very short generic UI fragments
    words = [p for p in re.split(r"\s+", tl) if p]
    if len(words) <= 2 and any(w in ("mehr", "weiter", "login", "menü", "menu") for w in words):
        flags.append("ui_fragment")

    # Determine noise + confidence
    strong = any(f in flags for f in ("has_url", "has_email", "copyright", "has_phone"))
    has_stopword = any(f.startswith("stopword:") for f in flags)

    is_noise = strong or has_stopword or ("ui_fragment" in flags)

    # Confidence expresses "looks like a real dish" (1.0) vs noise (0.0)
    if is_noise:
        conf = 0.05 if (strong or has_stopword) else 0.2
    else:
        conf = 0.9
        # slight downgrade if ultra-short and no food-ish punctuation
        if len(words) <= 2:
            conf = 0.7
            flags.append("short")

    return {"isNoise": bool(is_noise), "confidence": float(conf), "flags": flags}


def apply_qc(menus: List[Dict[str, Any]]) -> None:
    """Annotate each item with qc fields (in-place)."""
    for m in menus:
        items = m.get("items")
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            text = it.get("text") or it.get("name") or ""
            it["qc"] = qc_item_text(str(text))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_restaurants(path: Path) -> List[Dict[str, Any]]:
    doc = yaml.safe_load(path.read_text("utf-8")) or {}
    rows = doc.get("restaurants")
    if not isinstance(rows, list):
        raise ValueError("restaurants.yml must contain top-level key 'restaurants' as a list")
    out: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = r.get("name")
        zone = r.get("zone")
        url_menu = r.get("url_menu")
        source_type = r.get("source")
        if not name or not zone or not url_menu or not source_type:
            raise ValueError(f"invalid restaurant entry (need name, zone, url_menu, source): {r}")
        out.append(r)
    return out


def build_sources(restaurants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for r in restaurants:
        crawl = r.get("crawl")
        if not crawl:
            continue
        if not isinstance(crawl, dict):
            raise ValueError(f"crawl must be a mapping for restaurant {r.get('name')}")
        src: Dict[str, Any] = {
            "name": r["name"],
            "url": crawl.get("url") or r["url_menu"],
        }
        if crawl.get("kind"):
            src["kind"] = crawl["kind"]
        if crawl.get("parser"):
            src["parser"] = crawl["parser"]
        # for pdf extraction
        src["restaurant"] = r["name"]
        sources.append(src)
    return sources


def default_json(o: Any):
    # date -> ISO string
    try:
        import datetime as _dt

        if isinstance(o, (_dt.date, _dt.datetime)):
            return o.isoformat()
    except Exception:
        pass
    raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build docs/data.json from docs/restaurants.yml")
    ap.add_argument("--restaurants", required=True, help="Path to docs/restaurants.yml")
    ap.add_argument("--out", required=True, help="Output JSON path (typically docs/data.json)")
    ap.add_argument("--cache-dir", default=str(Path(".cache") / "menu-crawler"))
    args = ap.parse_args()

    restaurants_path = Path(args.restaurants)
    out_path = Path(args.out)

    restaurants = load_restaurants(restaurants_path)

    # crawl whatever we can (only entries with crawl config)
    sources = build_sources(restaurants)
    menus: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    # enrich menus with zone + menu url
    r_index: Dict[str, Dict[str, Any]] = {r["name"]: r for r in restaurants}

    for src in sources:
        try:
            rows = crawl_source(src, cache_dir=args.cache_dir)
            for m in rows:
                rn = m.get("restaurant") or src.get("name")
                meta = r_index.get(rn) or {}
                m["zone"] = meta.get("zone")
                m["url_menu"] = meta.get("url_menu")
                m["source"] = rn
                m["url"] = meta.get("url_menu")
                menus.append(m)
        except Exception as e:
            errors.append({"name": src.get("name"), "url": src.get("url"), "error": str(e)})

    # Post-extraction QC: mark likely noise items (cookies/legal/nav/etc.)
    apply_qc(menus)

    payload = {
        "generatedAt": _utc_now_iso(),
        "restaurants": [
            {
                "name": r["name"],
                "zone": r["zone"],
                "url_menu": r["url_menu"],
                "source": r["source"],
            }
            for r in restaurants
        ],
        "menus": menus,
        "errors": errors,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=default_json), "utf-8")


if __name__ == "__main__":
    main()
