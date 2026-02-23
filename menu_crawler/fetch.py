from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import requests


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes


def _cache_path(cache_dir: Path, url: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return cache_dir / f"{h}.bin"


def fetch(url: str, *, timeout_s: int = 20, cache_dir: Optional[str] = None) -> FetchResult:
    cache_p: Optional[Path] = None
    if cache_dir:
        cache_p = Path(cache_dir)
        cache_p.mkdir(parents=True, exist_ok=True)
        fp = _cache_path(cache_p, url)
        if fp.exists():
            body = fp.read_bytes()
            # no headers stored; caller can infer from url/usage
            return FetchResult(url=url, final_url=url, status_code=200, content_type="application/octet-stream", body=body)

    headers = {
        "User-Agent": "menu-crawler-prototype/0.1 (+https://localhost)"
    }
    r = requests.get(url, headers=headers, timeout=timeout_s)
    r.raise_for_status()

    body = r.content
    ct = r.headers.get("content-type", "application/octet-stream").split(";")[0].strip().lower()

    if cache_p:
        fp = _cache_path(cache_p, url)
        fp.write_bytes(body)

    return FetchResult(url=url, final_url=str(r.url), status_code=r.status_code, content_type=ct, body=body)


def guess_kind(content_type: str, url: str) -> str:
    ct = (content_type or "").lower()
    if "pdf" in ct or url.lower().endswith(".pdf"):
        return "pdf"
    if "html" in ct or url.lower().endswith((".html", ".htm")):
        return "html"
    return "binary"
