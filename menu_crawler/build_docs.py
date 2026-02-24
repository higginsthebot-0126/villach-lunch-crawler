from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from .crawl import crawl_source


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
