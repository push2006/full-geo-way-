"""Deduplication logic merged from GeoNews + BRICS."""
import hashlib
import re

def normalize_title(title: str) -> str:
    t = (title or "").lower().strip()
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def title_hash(title: str) -> str:
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()[:32]

def is_duplicate(title: str, seen: set) -> bool:
    h = title_hash(title)
    if h in seen:
        return True
    seen.add(h)
    return False

def dedupe_items(items: list, key: str = "title") -> list:
    seen = set()
    out = []
    for it in items:
        title = it.get(key) or it.get("name") or ""
        if not title:
            out.append(it)
            continue
        if is_duplicate(title, seen):
            continue
        out.append(it)
    return out
