"""RSS collector — GeoNews-style fetch + classify + dedupe (merged)."""
from typing import List, Dict
from datetime import datetime, timezone
import feedparser
from core.config import USER_AGENT, REQUEST_TIMEOUT, RSS_MAX_ITEMS, load_sources
from core.tor_support import get_session_for, is_onion
from core.classifier import strip_html, classify, is_critical, is_brics_relevant, risk_score
from core.dedupe import dedupe_items


def _rss_feed_urls() -> List[str]:
    """Enabled RSS feed URLs from the single config/sources.yaml."""
    urls = []
    for s in load_sources(enabled_only=True):
        stype = (s.get("type") or "").lower()
        url = (s.get("url") or "").strip()
        if not url:
            continue
        if stype == "rss" or "rss" in url.lower() or "feed" in url.lower():
            urls.append(url)
    return urls


def fetch_rss(url: str, max_items: int = None) -> List[Dict]:
    max_items = max_items or RSS_MAX_ITEMS
    headers = {"User-Agent": USER_AGENT}
    try:
        session = get_session_for(url)
        resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT * (2 if is_onion(url) else 1))
        if resp.status_code >= 400:
            return []
        feed = feedparser.parse(resp.content)
        items = []
        for entry in feed.entries[:max_items]:
            title = strip_html(getattr(entry, "title", "") or "")
            summary = strip_html(
                getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            )
            link = getattr(entry, "link", "") or ""
            cat = classify(title, summary)
            items.append({
                "title": title,
                "url": link,
                "summary": summary,
                "published": getattr(entry, "published", "") or "",
                "source_feed": url,
                "category": cat,
                "critical": is_critical(title, summary),
                "brics": is_brics_relevant(title, summary),
                "score": risk_score(title, summary),
            })
        return dedupe_items(items, key="title")
    except Exception:
        return []


def collect_feeds(feed_urls: List[str] = None) -> List[Dict]:
    feeds = feed_urls or _rss_feed_urls()
    all_items = []
    for url in feeds:
        all_items.extend(fetch_rss(url))
    return dedupe_items(all_items, key="title")


def collect_all_merged_feeds() -> List[Dict]:
    """Collect from all enabled RSS feeds in config/sources.yaml."""
    return collect_feeds(_rss_feed_urls())
