"""Fast exact + near-duplicate filtering for GeoWatch.

Inspired by GeoNews' fuzzy headline dedupe. Exact hashes remain the cheap
first pass; an optional similarity pass collapses slightly different
headlines from multiple outlets while retaining the strongest item.
"""
import hashlib
import re
from difflib import SequenceMatcher

_WORD_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def normalize_title(title: str) -> str:
    t = (title or "").lower().strip()
    t = _WORD_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def title_hash(title: str) -> str:
    return hashlib.sha256(normalize_title(title).encode("utf-8")).hexdigest()[:32]


def is_duplicate(title: str, seen: set) -> bool:
    h = title_hash(title)
    if h in seen:
        return True
    seen.add(h)
    return False


def dedupe_items(items: list, key: str = "title") -> list:
    """Cheap exact-title dedupe while retaining corroboration count."""
    seen = {}
    out = []
    for it in items:
        title = it.get(key) or it.get("name") or ""
        if not title:
            out.append(it)
            continue
        h = title_hash(title)
        if h in seen:
            idx = seen[h]
            out[idx]["corroboration"] = int(out[idx].get("corroboration", 1) or 1) + 1
            if (it.get("score") or 0) > (out[idx].get("score") or 0):
                old_corr = out[idx]["corroboration"]
                replacement = dict(it)
                replacement["corroboration"] = old_corr
                out[idx] = replacement
            continue
        seen[h] = len(out)
        it = dict(it)
        it["corroboration"] = max(1, int(it.get("corroboration", 1) or 1))
        out.append(it)
    return out


def _similar(a: str, b: str, threshold: float) -> bool:
    sm = SequenceMatcher(None, a, b)
    if sm.quick_ratio() < threshold:
        return False
    return sm.ratio() >= threshold


def dedupe_near_duplicates(items: list, key: str = "title", threshold: float = 0.88,
                           score_key: str = "score") -> list:
    """Collapse near-identical headlines within one collection batch.

    The list is first exact-deduped. For fuzzy matches, the item with the
    higher score is retained when a numeric score is available. A
    ``corroboration`` counter records how many matching items were observed.
    """
    exact = dedupe_items(items, key=key)
    kept = []
    for item in exact:
        title = normalize_title(item.get(key) or item.get("name") or "")
        if not title:
            kept.append(item)
            continue
        match = None
        for idx, existing in enumerate(kept):
            other = normalize_title(existing.get(key) or existing.get("name") or "")
            if other and _similar(title, other, threshold):
                match = idx
                break
        if match is None:
            item["corroboration"] = max(1, int(item.get("corroboration", 1) or 1))
            kept.append(item)
            continue
        existing = kept[match]
        count = int(existing.get("corroboration", 1) or 1) + 1
        old_score = existing.get(score_key, 0) or 0
        new_score = item.get(score_key, 0) or 0
        if new_score > old_score:
            item["corroboration"] = count
            kept[match] = item
        else:
            existing["corroboration"] = count
    return kept
