"""GeoWatch cross-module intelligence pipeline.

Connects collection -> cleaning -> category -> threat -> diplomacy -> dedupe
metadata -> storage fields.  The goal is one predictable path for RSS, GNews,
trends and crawled content instead of each collector inventing its own logic.
"""
from urllib.parse import urlparse
from core.classifier import classify, strip_html, risk_score, is_critical, is_brics_relevant
from core.dedupe import normalize_title, title_hash, dedupe_near_duplicates
from core.threat_classifier import classify_by_keyword
from core.diplomacy_signals import is_diplomatic_signal

CATEGORY_MAP = {
    "GEOPOLITICS": "Geopolitics", "TRADE": "Trade & Economy", "SANCTIONS": "Sanctions",
    "RISK": "Security", "CONFERENCE": "Diplomacy", "RESEARCH": "Research",
    "GENERAL": "Other", "TECH": "Technology", "ENERGY": "Energy",
}


def canonical_category(value, title="", summary=""):
    raw = (value or "").strip().upper().replace(" ", "_")
    if raw in CATEGORY_MAP:
        return CATEGORY_MAP[raw]
    low = (value or "").strip().lower()
    aliases = {
        "trade": "Trade & Economy", "economy": "Trade & Economy", "economic": "Trade & Economy",
        "security": "Security", "military": "Security", "conflict": "Security",
        "diplomatic": "Diplomacy", "diplomacy": "Diplomacy", "conference": "Diplomacy",
        "sanctions": "Sanctions", "research": "Research", "technology": "Technology",
        "tech": "Technology", "energy": "Energy", "trends": "Trends",
        "india": "India & South Asia", "south asia": "India & South Asia",
        "humanitarian": "Humanitarian", "rights": "Humanitarian",
    }
    if low in aliases:
        return aliases[low]
    if not value or low in ("general", "other", "unknown"):
        base = classify(title, summary)
        return CATEGORY_MAP.get(base, "Other")
    return value.strip().title()


def enrich_item(item: dict) -> dict:
    """Normalize and cross-classify one collector item."""
    item = dict(item or {})
    title = strip_html(str(item.get("title") or item.get("name") or "")).strip()[:512]
    summary = strip_html(str(item.get("summary") or item.get("description") or item.get("content") or ""))
    url = str(item.get("url") or item.get("link") or "").strip()
    threat = classify_by_keyword(f"{title} {summary}")
    base = classify(title, summary)
    item.update({
        "title": title,
        "url": url,
        "summary": summary[:50000],
        "category": canonical_category(item.get("category") or base, title, summary),
        "base_category": base,
        "threat_level": threat["level"],
        "threat_category": threat["category"],
        "confidence": threat["confidence"],
        "diplomatic_signal": is_diplomatic_signal(title),
        "critical": bool(item.get("critical")) or is_critical(title, summary),
        "brics": bool(item.get("brics")) or is_brics_relevant(title, summary),
        "score": max(int(item.get("score") or 0), risk_score(title, summary)),
        "fingerprint": title_hash(title),
        "source_host": (urlparse(url).netloc or "").lower(),
    })
    return item


def process_batch(items: list, threshold: float = 0.88) -> list:
    enriched = [enrich_item(i) for i in (items or []) if isinstance(i, dict)]
    enriched = [i for i in enriched if i.get("url") and i.get("title")]
    return dedupe_near_duplicates(enriched, key="title", threshold=threshold, score_key="score")
