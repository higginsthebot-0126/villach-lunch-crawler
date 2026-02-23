from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .fetch import fetch, guess_kind
from .extract_html import (
    extract_daily_menus,
    rule_hotel_seven_milo,
    rule_chickis,
)
from .extract_pdf import extract_menus_from_pdf


def crawl_source(src: Dict[str, Any], *, cache_dir: str | None = None) -> List[Dict[str, Any]]:
    url = src["url"]
    kind = src.get("kind")  # html|pdf|auto
    parser = src.get("parser")

    fr = fetch(url, cache_dir=cache_dir)
    detected = guess_kind(fr.content_type, url)
    kind = kind or "auto"
    if kind == "auto":
        kind = detected

    if kind == "html":
        if parser == "hotel_seven_milo":
            rule = rule_hotel_seven_milo(url)
        elif parser == "chickis":
            rule = rule_chickis(url)
        else:
            raise ValueError(f"unknown html parser: {parser}")

        menus = extract_daily_menus(fr.body, rule)
        return [asdict(m) for m in menus]

    if kind == "pdf":
        restaurant = src.get("restaurant", "(unknown)")
        menus = extract_menus_from_pdf(fr.body, restaurant=restaurant, url=url)
        return [asdict(m) for m in menus]

    raise ValueError(f"unsupported kind: {kind} (content-type={fr.content_type})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True, help="YAML file describing sources")
    ap.add_argument("--out", required=True, help="Output JSON path")
    ap.add_argument("--cache-dir", default=str(Path(".cache") / "menu-crawler"))
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text("utf-8"))
    sources = cfg.get("sources", [])

    all_rows: List[Dict[str, Any]] = []
    for src in sources:
        all_rows.extend(crawl_source(src, cache_dir=args.cache_dir))

    def default(o):
        # date -> ISO string
        try:
            import datetime

            if isinstance(o, (datetime.date, datetime.datetime)):
                return o.isoformat()
        except Exception:
            pass
        raise TypeError(f"Object of type {type(o).__name__} is not JSON serializable")

    Path(args.out).write_text(json.dumps(all_rows, ensure_ascii=False, indent=2, default=default), "utf-8")


if __name__ == "__main__":
    main()
