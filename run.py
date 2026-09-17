#!/usr/bin/env python3
"""
GeoWatch Pro — ONE COMMAND

  python run.py

Collects continuously + serves dashboard at http://127.0.0.1:8501
"""
import argparse, sys, time, signal
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from core.config import USE_TOR, ENABLE_ONION, STORAGE_BACKEND, SOURCES_FILE, load_sources
from core.storage import init_db, get_session, upsert_site, get_enabled_sites, update_site_after_check
from core.crawler import fetch_page, content_hash, polite_delay
from core.tor_support import is_onion
from core.trends import collect_trends

DEMO_CRAWL_URL = "https://www.bbc.com/news"
DEMO_RSS_URL = "https://feeds.bbci.co.uk/news/world/rss.xml"

# 24/7 settings
UPDATE_INTERVAL = 120  # seconds (full cycle often >30s)
_running = True


def _handle_signal(sig, frame):
    global _running
    print("\n⏹  Stopping...")
    _running = False
    # FIX #2: Clean up MongoDB connections on shutdown
    try:
        from core.storage import cleanup_mongo
        cleanup_mongo()
    except Exception:
        pass
    # sys.exit() here raises SystemExit wherever the main thread currently
    # is — inside do_24_7's own loop when running standalone (run.py 24),
    # or inside Flask's blocking app.run() when running do_serve (plain
    # run.py). Without this, Ctrl+C only ever flipped `_running`, which
    # do_24_7's own loop checks (fine on its own) but Flask's dev server
    # never does — so in serve mode the dashboard process would never
    # actually stop on Ctrl+C, only the background collector thread would.
    # SystemExit exits cleanly (no traceback) unlike an uncaught
    # KeyboardInterrupt, so this is a strictly cleaner shutdown too.
    sys.exit(0)


def do_import(path: str = None):
    """Import sources from the single config/sources.yaml (or optional path)."""
    if path:
        import yaml
        p = Path(path)
        if not p.exists():
            print(f"⚠️  Sources file not found: {path}")
            return 0
        try:
            with open(p, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            sources = data.get("sources") or []
        # FIX #9: Handle YAML parsing errors explicitly
        except yaml.YAMLError as e:
            print(f"❌ Invalid YAML in {p}: {e}")
            return 0
        except Exception as e:
            print(f"❌ Error reading {p}: {e}")
            return 0
    else:
        if not SOURCES_FILE.exists():
            print(f"⚠️  Sources file not found: {SOURCES_FILE}")
            return 0
        sources = load_sources(enabled_only=False)

    init_db()
    session = get_session()
    count = 0
    for row in sources:
        if not isinstance(row, dict):
            continue
        url = (row.get("url") or "").strip()
        if not url:
            continue
        name = (row.get("name") or "").strip()
        cat = (row.get("category") or "general").strip()
        enabled = row.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() in ("true", "1", "yes")
        stype = (row.get("type") or "").strip().lower()
        if not stype:
            stype = "onion" if is_onion(url) else ("rss" if ("rss" in url or "feed" in url) else "page")
        upsert_site(session, url, name=name, category=cat, enabled=bool(enabled), source_type=stype)
        count += 1
    if hasattr(session, "close"):
        session.close()
    # FIX #11: Use conditional emoji based on actual result
    symbol = "✅" if count > 0 else "⚠️"
    print(f"{symbol} Imported {count} sources from {path or SOURCES_FILE.name}")
    return count


def do_check(limit: int = 0, quiet: bool = False):
    """Page-change monitor. Skips RSS feeds (handled by do_rss) and onion
    when Tor is off — those used to flood the dashboard with red errors."""
    from tqdm import tqdm
    init_db()
    session = get_session()
    sites = get_enabled_sites(session)
    if not sites:
        if not quiet:
            print("⚠️  No sources. Import first.")
        return 0, 0

    # Only check real page sources — skip RSS, feeds, and video pages
    # (YouTube watch/shorts waste time and only produce truncated junk HTML)
    SKIP_URL_PARTS = (
        "/rss", "/feed", ".xml", "youtube.com/watch", "youtube.com/shorts",
        "youtu.be/", "vimeo.com/", "twitter.com/", "x.com/", "facebook.com/",
        "instagram.com/",
    )
    filtered = []
    for site in sites:
        try:
            stype = (site.get("source_type") if isinstance(site, dict) else getattr(site, "source_type", "")) or ""
            stype = str(stype).lower()
            url = site["url"] if isinstance(site, dict) else site.url
        except Exception:
            continue
        if not url:
            continue
        ul = url.lower()
        if stype == "rss" or stype == "trend":
            continue
        if any(p in ul for p in SKIP_URL_PARTS):
            continue
        filtered.append(site)

    if limit:
        filtered = filtered[:limit]
    if not quiet:
        print(f"🔍 Checking {len(filtered)} page sources (RSS skipped — collected separately)...")
    changed = errors = 0
    iterator = filtered if quiet else tqdm(filtered, desc="Monitor")
    for site in iterator:
        try:
            url = site["url"] if isinstance(site, dict) else site.url
            if not url or not isinstance(url, str):
                errors += 1
                continue
        except (AttributeError, KeyError, TypeError) as e:
            if not quiet:
                print(f"   ⚠️  Invalid site object: {e}")
            errors += 1
            continue

        if is_onion(url) and not USE_TOR:
            # Soft-skip: do not stamp a permanent red error on the dashboard
            continue

        text, status, error = fetch_page(url)
        if error or text is None:
            update_site_after_check(session, site, status_code=status, error=error)
            errors += 1
            polite_delay()
            continue
        title = ""
        for line in (text or "").splitlines():
            if line.strip() and len(line.strip()) > 10:
                title = line.strip()[:200]
                break
        new_hash = content_hash(text)
        try:
            last_hash = site.get("last_hash") if isinstance(site, dict) else site.last_hash
        except (AttributeError, KeyError, TypeError):
            last_hash = None
        is_changed = last_hash is not None and last_hash != new_hash
        if is_changed:
            changed += 1
        # Clear previous error on success
        update_site_after_check(
            session, site,
            content_hash=new_hash, status_code=status,
            content=text, title=title, changed=is_changed, error=None,
        )
        polite_delay()
    if hasattr(session, "close"):
        session.close()
    if not quiet:
        print(f"✅ Check — Changed: {changed} | Errors: {errors}")
    return changed, errors


def do_crawl(url: str, pages: int = 15, depth: int = 2, name: str = ""):
    from core.site_crawler import crawl_and_store
    print(f"🕷  Crawl: {url} (pages={pages}, depth={depth})")
    crawl_and_store(url, site_name=name, max_pages=pages, max_depth=depth)
    print("✅ Crawl done")


def do_rss(feed_url: str = None, from_sources: bool = False, quiet: bool = False, all_merged: bool = False):
    from core.rss import fetch_rss, collect_all_merged_feeds
    from core.classifier import classify, strip_html
    init_db()
    session = get_session()
    items = []
    if all_merged or (not feed_url and not from_sources):
        if not quiet:
            print("📡 Collecting ALL GeoNews+BRICS RSS feeds...")
        items = collect_all_merged_feeds()
    elif feed_url:
        if not quiet:
            print(f"📡 RSS: {feed_url}")
        items = fetch_rss(feed_url)
    elif from_sources:
        sites = get_enabled_sites(session)
        feeds = []
        for s in sites:
            u = s["url"] if isinstance(s, dict) else s.url
            if "rss" in u.lower() or "feed" in u.lower():
                feeds.append(u)
        if not quiet:
            print(f"📡 RSS from {len(feeds)} imported feeds...")
        for f in feeds:
            items.extend(fetch_rss(f))
    total = 0
    for it in items:
        if not it.get("url"):
            continue
        title = it.get("title") or ""
        content = it.get("summary") or ""
        cat = it.get("category") or classify(title, content)
        score = int(it.get("score") or 0)
        upsert_site(
            session, it["url"],
            name=title[:200],
            title=title[:200],
            content=content,
            category=cat,
            source_type="rss",
            platform="RSS",
            score=score,
        )
        total += 1
    if hasattr(session, "close"):
        session.close()
    if not quiet:
        # FIX #11: Use conditional emoji based on actual result
        symbol = "✅" if total > 0 else "⚠️"
        print(f"{symbol} RSS stored: {total} articles (classified)")
    return total


def do_trends(quiet: bool = False):
    if not quiet:
        print("📈 Social trends (Reddit, HN, YouTube, Mastodon, Telegram, Twitter/X, Facebook, Instagram)...")
    items = collect_trends()
    init_db()
    session = get_session()
    count = 0
    for it in items:
        url = it.get("url") or ""
        if not url:
            continue
        upsert_site(
            session, url,
            name=(it.get("title") or "")[:200],
            title=(it.get("title") or "")[:200],
            content=f"Score: {it.get('score', 0)} | Comments: {it.get('comments', 0)} | {it.get('source', '')}",
            category=f"trend-{(it.get('platform') or 'social').lower()}",
            source_type="trend",
            platform=it.get("platform") or "",
            score=int(it.get("score") or 0),
        )
        count += 1
    if hasattr(session, "close"):
        session.close()
    if not quiet:
        print(f"✅ Trends stored: {count}")
    return count



def do_gnews(quiet: bool = False):
    """Google News keyword collector, ported from geonews-main. No-op
    unless ENABLE_GNEWS=true and `gnews` is installed."""
    from core.config import ENABLE_GNEWS
    if not ENABLE_GNEWS:
        if not quiet:
            print("⏭  GNews collector disabled (ENABLE_GNEWS=false)")
        return 0
    from core.gnews_search import collect
    if not quiet:
        print("🔎 Google News keyword search...")
    n = collect(quiet=quiet)
    if not quiet:
        print(f"✅ GNews stored: {n} articles")
    return n


def do_streams():
    """List configured live-video streams, ported from BRICS-- (config/streams.yaml)."""
    from core.video import load_streams
    streams = load_streams()
    if not streams:
        print("No streams configured — edit config/streams.yaml")
    for s in streams:
        print(f"  {s.get('name','?')} [{s.get('country','')}] {s.get('watch_url','')}")
    return streams



def do_sanctions(quiet: bool = False):
    """Download OFAC SDN list and screen recent content for name hits."""
    from core.config import ENABLE_SANCTIONS_SCREEN
    if not ENABLE_SANCTIONS_SCREEN:
        if not quiet:
            print("⏭  Sanctions screen disabled (ENABLE_SANCTIONS_SCREEN=false)")
        return 0
    from core.sanctions import update_ofac_names, screen_text
    from core.storage import get_content_items, get_session, init_db
    if not quiet:
        print("🛂 OFAC sanctions screen...")
    names = update_ofac_names()
    if not names:
        if not quiet:
            print("   No OFAC names loaded")
        return 0
    init_db()
    session = get_session()
    items = get_content_items(session, limit=100)
    hits_total = 0
    for it in items:
        text = " ".join([
            str(it.get("title") or it.get("name") or ""),
            str(it.get("content") or it.get("content_preview") or ""),
        ])
        hits = screen_text(text, names)
        if hits:
            hits_total += 1
            if not quiet:
                title = (it.get("title") or it.get("name") or it.get("url") or "")[:60]
                print(f"   HIT: {title} → {', '.join(hits[:3])}")
    if hasattr(session, "close"):
        session.close()
    if not quiet:
        print(f"✅ Sanctions: {hits_total} items with name hits (of {len(items)} screened)")
    return hits_total


def do_cycle(quiet: bool = False):
    """One update cycle: trends + RSS + GNews + sanctions + check."""
    import time
    from core.status import record_cycle, set_running
    set_running(True)
    t0 = time.time()
    
    # FIX #4: Add explicit error tracking for each collection function
    errors_detail = []
    
    try:
        do_trends(quiet=quiet)
    except Exception as e:
        if not quiet:
            print(f"   ⚠️  Trends error: {e}")
        errors_detail.append(f"trends: {str(e)[:50]}")
    
    try:
        do_rss(all_merged=True, quiet=quiet)
    except Exception as e:
        if not quiet:
            print(f"   ⚠️  RSS error: {e}")
        errors_detail.append(f"rss: {str(e)[:50]}")
    
    try:
        do_gnews(quiet=quiet)
    except Exception as e:
        if not quiet:
            print(f"   ⚠️  GNews error: {e}")
        errors_detail.append(f"gnews: {str(e)[:50]}")
    
    try:
        do_sanctions(quiet=quiet)
    except Exception as e:
        if not quiet:
            print(f"   ⚠️  Sanctions error: {e}")
        errors_detail.append(f"sanctions: {str(e)[:50]}")
    
    try:
        changed, errors = do_check(quiet=quiet)
    except Exception as e:
        if not quiet:
            print(f"   ⚠️  Check error: {e}")
        errors_detail.append(f"check: {str(e)[:50]}")
        changed, errors = 0, 1
    
    duration = time.time() - t0
    msg = "ok" if not errors_detail else f"partial: {'; '.join(errors_detail[:3])}"
    record_cycle(changed=changed, errors=errors, duration_sec=duration, message=msg)
    
    return changed, errors


def do_serve(interval: int = UPDATE_INTERVAL, host: str = None, port: int = None):
    """ONE command: runs the 24/7 collector loop in a background thread
    and the dashboard in the foreground, in the same process. This is
    what you want if you just want to type one thing and have both
    collection and the dashboard running.

    Signal handlers (Ctrl+C) MUST be registered here, on the main
    thread — signal.signal() raises ValueError if called from a
    background thread, which is what do_24_7() used to do when this
    function started it as one. Register once, here, then tell
    do_24_7() not to register its own.
    """
    import threading
    from core.config import DASHBOARD_HOST, DASHBOARD_PORT
    from core.webapp import run_dashboard

    global _running
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    t = threading.Thread(target=do_24_7, args=(interval,), kwargs={"register_signals": False}, daemon=True)
    t.start()

    time.sleep(1)  # let the initial import/cycle start printing before the dashboard banner
    run_dashboard(host=host or DASHBOARD_HOST, port=port or DASHBOARD_PORT)


def do_24_7(interval: int = UPDATE_INTERVAL, register_signals: bool = True):
    """Run 24/7 — update every N seconds.

    register_signals=False when called from do_serve()'s background
    thread — signal.signal() only works on the main thread, so calling
    it here would raise ValueError and silently kill this thread before
    any collection happened. Only register when this function itself
    is the main-thread entrypoint (i.e. `python run.py 24` directly).
    """
    global _running
    if register_signals:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)

    print("=" * 54)
    print("  GeoWatch Pro — 24/7 MODE")
    print(f"  Update every {interval} seconds")
    print("  Press Ctrl+C to stop")
    print("=" * 54)
    print()

    # First-time setup
    print("① Initial import...")
    do_import()
    print()
    print("② First full cycle...")
    do_cycle(quiet=False)
    print()
    print(f"③ Entering 24/7 loop (every {interval}s)...")
    print("   Dashboard: http://127.0.0.1:8501")
    print()

    cycle_num = 1
    while _running:
        cycle_num += 1
        start = time.time()
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"── Cycle #{cycle_num} @ {ts} ──")
        try:
            changed, errors = do_cycle(quiet=True)
            from core.status import record_cycle
            record_cycle(cycle_num=cycle_num, changed=changed, errors=errors, message="ok")
            print(f"   ✓ Updated | changed={changed} errors={errors}")
        except Exception as e:
            from core.status import record_cycle
            record_cycle(cycle_num=cycle_num, message=f"error: {e}")
            print(f"   ✗ Cycle error: {e}")
        elapsed = time.time() - start
        sleep_for = max(1, interval - elapsed)
        # Sleep in small steps so Ctrl+C is responsive
        for _ in range(int(sleep_for)):
            if not _running:
                break
            time.sleep(1)
        if not _running:
            break
        if sleep_for - int(sleep_for) > 0 and _running:
            time.sleep(sleep_for - int(sleep_for))

    print("24/7 mode stopped.")


def do_all():
    """One-shot: everything once + dashboard."""
    print("=" * 54)
    print("  GeoWatch Pro — FULL PIPELINE (once)")
    print("=" * 54)
    print()
    print("① Import sources...")
    do_import()
    print()
    print("② Trends + RSS + sample crawl + check...")
    do_trends()
    do_rss(all_merged=True)
    try:
        do_crawl(DEMO_CRAWL_URL, pages=10, depth=1, name="BBC News")
    except Exception as e:
        print(f"   Crawl partial: {e}")
    do_check()
    print()
    print("③ Done")


def main():
    p = argparse.ArgumentParser(
        description="GeoWatch Pro — one command",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ONE CORRECT WAY:
  python run.py

Collects continuously + serves dashboard at http://127.0.0.1:8501
        """,
    )
    p.add_argument("--host", default=None, help="Dashboard host (default 127.0.0.1)")
    p.add_argument("--port", type=int, default=None, help="Dashboard port (default 8501)")
    p.add_argument("--interval", type=int, default=UPDATE_INTERVAL, help="Seconds between collection cycles")
    # Keep serve as optional alias so Procfile / old docs still work
    p.add_argument("cmd", nargs="?", default="serve", help=argparse.SUPPRESS)
    args = p.parse_args()
    # FIX #1: Use 'is not None' instead of 'or' to allow explicit 0 (even if unlikely)
    interval = args.interval if args.interval is not None else UPDATE_INTERVAL
    # Always run the one correct mode
    do_serve(interval=interval, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
