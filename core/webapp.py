"""Local dashboard backend. Serves your ACTUAL collected data from
core.storage as JSON, and the dashboard page itself. No AI calls, no
external API — everything here reads directly from data/geowatch.db
(or MongoDB, if that's your STORAGE_BACKEND).

Run with: python run.py
"""
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from core.storage import (
    init_db, get_session, get_all_sites_summary, get_recent_changes,
    get_content_items, count_content_items, weekly_top_articles, category_counts,
)
from core.video import load_streams, add_stream, remove_stream
from core.status import get_status
from core.config import (
    ENABLE_GNEWS, ENABLE_SANCTIONS_SCREEN, USE_TOR, ENABLE_ONION,
    STORAGE_BACKEND, DASHBOARD_HOST, DASHBOARD_PORT, mongo_targets,
)

STATIC_DIR = Path(__file__).parent.parent / "static"
app = Flask(__name__, static_folder=str(STATIC_DIR))


def _serialize(obj):
    """Make datetimes/ORM rows JSON-safe."""
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


@app.route("/")
def index():
    return send_from_directory(str(STATIC_DIR), "dashboard.html")


@app.route("/favicon.ico")
def favicon():
    # Tiny empty response — stops browser 404 spam in logs
    return ("", 204)


@app.route("/api/sites")
def api_sites():
    session = get_session()
    try:
        sites = get_all_sites_summary(session)
    finally:
        if hasattr(session, "close"):
            session.close()
    return jsonify(_serialize(sites))


@app.route("/api/content")
def api_content():
    """Paginated feed for large DBs (e.g. Mongo 500k docs).
    Query: ?limit=100&skip=0  (limit max 10000000)
    Returns: { items, total, limit, skip, has_more }
    """
    limit = int(request.args.get("limit", 10000000) or 10000000)
    skip = int(request.args.get("skip", 0) or 0)
    session = get_session()
    try:
        total = count_content_items(session)
        items = get_content_items(session, limit=limit, skip=skip)
    finally:
        if hasattr(session, "close"):
            session.close()
    return jsonify({
        "items": _serialize(items),
        "total": total,
        "limit": max(1, min(limit, 10_000_000)),
        "skip": max(0, skip),
        "has_more": (max(0, skip) + len(items)) < total,
    })


@app.route("/api/chokepoints")
def api_chokepoints():
    """The 13 fixed global trade chokepoints, each tagged with how many
    of your recent stories mention it -- a firmer map anchor than
    source pins since these never move."""
    from core.chokepoints import load_chokepoints, match_chokepoints
    limit = int(request.args.get("limit", 200) or 200)
    session = get_session()
    try:
        items = get_content_items(session, limit=limit)
    finally:
        if hasattr(session, "close"):
            session.close()
    counts = {cp["id"]: 0 for cp in load_chokepoints()}
    for it in items:
        title = it.get("title") or it.get("name") or ""
        for cp in match_chokepoints(title):
            counts[cp["id"]] += 1
    result = [{**cp, "recent_mentions": counts.get(cp["id"], 0)} for cp in load_chokepoints()]
    return jsonify(result)


@app.route("/api/threats")
def api_threats():
    """Tiered threat classification (critical/high/medium/low/info) of
    recent content, via core.threat_classifier (ported from
    worldmonitor's keyword classifier). Query: ?limit=100&level=critical
    to filter to one tier."""
    from core.threat_classifier import classify_by_keyword
    limit = int(request.args.get("limit", 200) or 200)
    level_filter = request.args.get("level")
    session = get_session()
    try:
        items = get_content_items(session, limit=limit)
    finally:
        if hasattr(session, "close"):
            session.close()
    results = []
    for it in items:
        title = it.get("title") or it.get("name") or ""
        r = classify_by_keyword(title)
        if level_filter and r["level"] != level_filter:
            continue
        results.append({**_serialize(it), "threat_level": r["level"],
                         "threat_category": r["category"], "confidence": r["confidence"]})
    return jsonify(results)


@app.route("/api/diplomacy")
def api_diplomacy():
    """Headlines pairing a flashpoint country/actor with diplomacy
    language (talks, ceasefire, treaty...) -- de-escalation signal,
    ported from worldmonitor's diplomacy-keywords.json."""
    from core.diplomacy_signals import is_diplomatic_signal
    limit = int(request.args.get("limit", 200) or 200)
    session = get_session()
    try:
        items = get_content_items(session, limit=limit)
    finally:
        if hasattr(session, "close"):
            session.close()
    signals = [_serialize(it) for it in items
               if is_diplomatic_signal(it.get("title") or it.get("name") or "")]
    return jsonify(signals)


@app.route("/api/changes")
def api_changes():
    session = get_session()
    try:
        changes = get_recent_changes(session, limit=60)
        if not isinstance(changes, list) or (changes and isinstance(changes[0], dict)):
            data = changes
        else:
            data = [{
                "url": c.url, "title": c.title,
                "detected_at": c.detected_at, "content_preview": c.content_preview,
            } for c in changes]
    finally:
        if hasattr(session, "close"):
            session.close()
    return jsonify(_serialize(data))


@app.route("/api/weekly")
def api_weekly():
    session = get_session()
    try:
        top = weekly_top_articles(session, days=7, limit=15)
        counts = category_counts(session, days=7)
    finally:
        if hasattr(session, "close"):
            session.close()
    return jsonify({"top": _serialize(top), "categories": counts})


@app.route("/api/streams", methods=["GET", "POST"])
def api_streams():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        name = data.get("name") or ""
        country = data.get("country") or "Custom"
        link = data.get("link") or data.get("url") or data.get("video_id") or ""
        try:
            stream = add_stream(name, country, link)
            return jsonify({"ok": True, "stream": stream}), 201
        except ValueError as e:
            return jsonify({"ok": False, "error": str(e)}), 400
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify(load_streams())


@app.route("/api/streams/<path:name>", methods=["DELETE"])
def api_streams_delete(name):
    ok = remove_stream(name)
    if not ok:
        return jsonify({"ok": False, "error": "Stream not found"}), 404
    return jsonify({"ok": True})


@app.route("/api/summary")
def api_summary():
    """One-call overview for the top-of-dashboard stat cards."""
    session = get_session()
    try:
        sites = get_all_sites_summary(session)
        changes = get_recent_changes(session, limit=1000)
    finally:
        if hasattr(session, "close"):
            session.close()
    by_platform = {}
    by_category = {}
    for s in sites:
        plat = (s.get("platform") or s.get("source_type") or "unknown") if isinstance(s, dict) else "unknown"
        cat = s.get("category") if isinstance(s, dict) else "general"
        by_platform[plat] = by_platform.get(plat, 0) + 1
        by_category[cat] = by_category.get(cat, 0) + 1
    return jsonify({
        "total_sources": len(sites),
        "total_changes_logged": len(changes) if isinstance(changes, list) else 0,
        "by_platform": by_platform,
        "by_category": by_category,
    })



@app.route("/api/status")
def api_status():
    st = get_status()
    st["features"] = {
        "gnews": ENABLE_GNEWS,
        "sanctions": ENABLE_SANCTIONS_SCREEN,
        "tor": USE_TOR,
        "onion": ENABLE_ONION,
        "storage": STORAGE_BACKEND,
        "mongo_targets": len(mongo_targets()) if STORAGE_BACKEND == "mongodb" else 0,
    }
    return jsonify(st)



@app.route("/api/geo")
def api_geo():
    """Country/region counts for map panel (from sources + content categories)."""
    from core.config import load_sources
    # rough centroids for map pins (lon, lat)
    COORDS = {
        "india": (78.96, 20.59), "china": (104.2, 35.9), "russia": (105.3, 61.5),
        "brazil": (-51.9, -14.2), "southafrica": (25.1, -29.0), "egypt": (30.8, 26.8),
        "iran": (53.7, 32.4), "saudiarabia": (45.1, 23.9), "saudi": (45.1, 23.9),
        "indonesia": (113.9, -0.8), "ethiopia": (40.5, 9.1), "uae": (53.8, 23.4),
        "unitedstates": (-98.5, 39.8), "us": (-98.5, 39.8), "uk": (-3.4, 55.4),
        "global": (0, 20), "geopolitics": (0, 20), "international": (0, 25),
        "trade": (10, 30), "sanctions": (15, 35), "research": (5, 45),
        "news": (0, 15), "rights": (12, 48), "onion": (0, 0),
    }
    counts = {}
    for s in load_sources(enabled_only=False):
        key = (s.get("country") or s.get("category") or "global").strip()
        if not key:
            key = "global"
        norm = key.lower().replace(" ", "")
        entry = counts.setdefault(norm, {"name": key, "sources": 0, "enabled": 0, "lon": None, "lat": None})
        entry["sources"] += 1
        if s.get("enabled", True):
            entry["enabled"] += 1
        if norm in COORDS:
            entry["lon"], entry["lat"] = COORDS[norm]
        elif entry["lon"] is None and "global" in COORDS:
            pass
    # fill coords
    for k, v in counts.items():
        if v["lon"] is None:
            v["lon"], v["lat"] = COORDS.get(k, COORDS.get("global", (0, 20)))
    session = get_session()
    try:
        sites = get_all_sites_summary(session)
    finally:
        if hasattr(session, "close"):
            session.close()
    for s in sites:
        cat = (s.get("category") or "general").strip().lower().replace(" ", "")
        if cat in counts:
            counts[cat]["items"] = counts[cat].get("items", 0) + 1
        else:
            lon, lat = COORDS.get(cat, (0, 20))
            counts[cat] = {"name": s.get("category") or cat, "sources": 0, "enabled": 0,
                           "items": 1, "lon": lon, "lat": lat}
    points = sorted(counts.values(), key=lambda x: -(x.get("enabled") or 0) - (x.get("items") or 0))
    return jsonify({"points": points, "total_regions": len(points)})


@app.route("/api/export")
def api_export():
    """JSON export of recent content (capped for safety)."""
    limit = min(int(request.args.get("limit", 5000) or 5000), 50000)
    session = get_session()
    try:
        items = get_content_items(session, limit=limit, skip=0)
        total = count_content_items(session)
    finally:
        if hasattr(session, "close"):
            session.close()
    return jsonify({"exported": len(items), "total_in_db": total, "items": _serialize(items)})


def run_dashboard(host="127.0.0.1", port=8501, debug=False):
    init_db()
    print(f"🖥  GeoWatch dashboard — http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard()
