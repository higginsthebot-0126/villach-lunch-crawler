from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List, Dict


@dataclass
class MenuItem:
    text: str
    course: Optional[str] = None  # e.g. starter/main/dessert/unknown
    allergens: List[str] = field(default_factory=list)  # e.g. ["G"]
    tags: List[str] = field(default_factory=list)  # e.g. ["curry", "lactose"]


@dataclass
class DailyMenu:
    restaurant: str
    source_url: str
    day: Optional[date] = None
    day_label: Optional[str] = None  # e.g. "Montag" when date missing
    items: List[MenuItem] = field(default_factory=list)
    meta: Dict[str, str] = field(default_factory=dict)
