"""Optional Google News keyword collector (ported from geonews-main).
OFF unless ENABLE_GNEWS=true. Requires: pip install gnews

Google News search treats commas as plain text, not boolean OR, so each
keyword group in GNEWS_QUERY_GROUPS is joined with " OR " so the search
matches any term in the group, e.g.:
    ["sanctions", "trade order", "FTA"] -> "sanctions OR trade order OR FTA"

Rewritten from geonews's Mongo-only `database.save_articles_bulk()` to
GeoWatch-Pro's `core.storage.upsert_site()` so it works on both the
sqlite and mongo backends this project already supports.
"""
from core.config import (
    GNEWS_LANGUAGE, GNEWS_COUNTRY, GNEWS_PERIOD, GNEWS_MAX_RESULTS,
    GNEWS_QUERY_GROUPS,
)
from core.classifier import classify, strip_html
from core.integration import process_batch
from core.storage import get_session, upsert_site

try:
    from gnews import GNews
    HAS_GNEWS = True
except ImportError:
    HAS_GNEWS = False


def _build_queries():
    return [" OR ".join(group) for group in GNEWS_QUERY_GROUPS]


def collect(quiet=False):
    if not HAS_GNEWS:
        if not quiet:
            print("[GNEWS] Skipped: run 'pip install gnews' to enable this collector.")
        return 0

    client = GNews(language=GNEWS_LANGUAGE, country=GNEWS_COUNTRY,
                    max_results=GNEWS_MAX_RESULTS, period=GNEWS_PERIOD)
    raw = []
    for query in _build_queries():
        try:
            results = client.get_news(query)
        except Exception as exc:
            if not quiet:
                print(f"[GNEWS] '{query}': {exc}")
            continue
        for art in results:
            title = (art.get("title") or "").strip()
            link = (art.get("url") or "").strip()
            if not title or not link:
                continue
            summary = strip_html(art.get("description") or "")
            source = (art.get("publisher") or {}).get("title", "Google News")
            raw.append({"title": title, "url": link, "summary": summary,
                        "source_feed": "Google News", "platform": source,
                        "source_type": "gnews", "category": classify(title, summary)})

    items = process_batch(raw)
    session = get_session()
    count = 0
    try:
        for it in items:
            upsert_site(session, it["url"], name=it["title"][:200], title=it["title"][:200],
                        content=it.get("summary", ""), category=it["category"],
                        source_type="gnews", platform=it.get("platform", "Google News"),
                        score=int(it.get("score") or 0), fingerprint=it.get("fingerprint", ""),
                        corroboration=int(it.get("corroboration") or 1))
            count += 1
    finally:
        if hasattr(session, "close"):
            session.close()
    if not quiet:
        print(f"[GNEWS] stored {count} articles")
    return count
