"""Local dashboard backend. Serves your ACTUAL collected data from
core.storage as JSON, and the dashboard page itself. No AI calls, no
external API — everything here reads directly from data/geowatch.db
(or MongoDB, if that's your STORAGE_BACKEND).

Run with: python run.py
"""
from pathlib import Path
from flask import Flask, jsonify, send_from_directory
from core.storage import (
    init_db, get_session, get_all_sites_summary, get_recent_changes,
    get_content_items, weekly_top_articles, category_counts,
)
from core.video import load_streams

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
    session = get_session()
    try:
        items = get_content_items(session, limit=200)
    finally:
        if hasattr(session, "close"):
            session.close()
    return jsonify(_serialize(items))


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


@app.route("/api/streams")
def api_streams():
    return jsonify(load_streams())


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


def run_dashboard(host="127.0.0.1", port=8501, debug=False):
    init_db()
    print(f"🖥  GeoWatch dashboard — http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    run_dashboard()
