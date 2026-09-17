"""Storage — SQLite (default) or MongoDB. Stores real content, not just metadata."""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from core.config import STORAGE_BACKEND, SQLITE_PATH, MONGODB_URI, MONGODB_DB, mongo_targets

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
_engine = None
_Session = None

class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True)
    url = Column(String(2048), unique=True, nullable=False, index=True)
    name = Column(String(512), default="")
    category = Column(String(128), default="general")
    enabled = Column(Boolean, default=True)
    last_hash = Column(String(64), nullable=True)
    last_checked = Column(DateTime, nullable=True)
    last_changed = Column(DateTime, nullable=True)
    last_status = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    # Real content fields
    title = Column(String(512), default="")
    content = Column(Text, nullable=True)          # main text / article body
    content_preview = Column(Text, nullable=True)  # short preview
    source_type = Column(String(32), default="page")  # page|rss|onion|trend
    platform = Column(String(64), default="")
    score = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ChangeLog(Base):
    __tablename__ = "change_logs"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, index=True)
    url = Column(String(2048))
    title = Column(String(512), default="")
    old_hash = Column(String(64), nullable=True)
    new_hash = Column(String(64))
    content_preview = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def _init_sqlite():
    global _engine, _Session
    _engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False)
    Base.metadata.create_all(bind=_engine)
    _Session = sessionmaker(bind=_engine)

_mongo_clients = {}


def _init_mongo(uri: str = None, db: str = None):
    """Open one Mongo database. Defaults to primary target."""
    from pymongo import MongoClient
    targets = mongo_targets()
    if not targets and not uri:
        uri = MONGODB_URI
        db = MONGODB_DB
    if uri is None:
        uri = targets[0]["uri"]
        db = targets[0]["db"]
    key = f"{uri}|{db}"
    if key not in _mongo_clients:
        _mongo_clients[key] = MongoClient(uri, serverSelectionTimeoutMS=6000)
    return _mongo_clients[key][db]


# FIX #2: Add explicit cleanup for MongoDB connections to prevent leaks
def cleanup_mongo():
    """Close all open MongoDB connections. Call this on shutdown."""
    global _mongo_clients
    for key, client in list(_mongo_clients.items()):
        try:
            client.close()
        except Exception as e:
            print(f"[mongo] cleanup error for {key}: {e}")
    _mongo_clients.clear()


def get_all_mongo_sessions():
    """All configured Mongo DBs (primary + optional second full URL)."""
    sessions = []
    for t in mongo_targets():
        try:
            sessions.append((_init_mongo(t["uri"], t["db"]), t["label"]))
        except Exception as e:
            print(f"[mongo] skip {t['label']}: {e}")
    return sessions


def init_db():
    if STORAGE_BACKEND == "mongodb":
        # touch primary (and secondary if set) so connection errors show early
        for t in mongo_targets():
            _init_mongo(t["uri"], t["db"])
    else:
        _init_sqlite()


def get_session():
    """Primary session (writes always go here)."""
    if STORAGE_BACKEND == "mongodb":
        targets = mongo_targets()
        if not targets:
            return _init_mongo(MONGODB_URI, MONGODB_DB)
        return _init_mongo(targets[0]["uri"], targets[0]["db"])
    if _Session is None:
        _init_sqlite()
    return _Session()

def upsert_site(session, url: str, name: str = "", category: str = "general",
                enabled: bool = True, source_type: str = "page",
                title: str = "", content: str = "", platform: str = "", score: int = 0):
    if STORAGE_BACKEND == "mongodb":
        col = session["sites"]
        col.update_one(
            {"url": url},
            {"$set": {
                "name": name or title, "title": title or name, "category": category,
                "enabled": enabled, "source_type": source_type, "platform": platform,
                "score": score, "content": (content or "")[:50000],
                "content_preview": (content or "")[:800],
                "updated_at": datetime.now(timezone.utc)
            }, "$setOnInsert": {"created_at": datetime.now(timezone.utc)}},
            upsert=True
        )
        return col.find_one({"url": url})
    else:
        site = session.query(Site).filter(Site.url == url).first()
        if site:
            site.name = name or title or site.name
            site.title = title or name or site.title
            site.category = category or site.category
            site.enabled = enabled
            site.source_type = source_type
            site.platform = platform or site.platform
            site.score = score or site.score
            if content:
                site.content = content[:50000]
                site.content_preview = content[:800]
            site.updated_at = datetime.now(timezone.utc)
        else:
            site = Site(
                url=url, name=name or title, title=title or name, category=category,
                enabled=enabled, source_type=source_type, platform=platform, score=score,
                content=(content or "")[:50000], content_preview=(content or "")[:800]
            )
            session.add(site)
        session.commit()
        session.refresh(site)
        return site

def get_enabled_sites(session) -> List:
    if STORAGE_BACKEND == "mongodb":
        return list(session["sites"].find({"enabled": True}))
    return session.query(Site).filter(Site.enabled == True).all()

def update_site_after_check(session, site, content_hash=None, status_code=None,
                            content=None, title=None, error=None, changed=False):
    now = datetime.now(timezone.utc)
    preview = (content or "")[:800] if content else None
    full = (content or "")[:50000] if content else None

    if STORAGE_BACKEND == "mongodb":
        url = site.get("url") if isinstance(site, dict) else site.url
        update = {"last_checked": now, "last_status": status_code,
                  "error_message": error, "updated_at": now}
        if title:
            update["title"] = title
            update["name"] = title
        if full:
            update["content"] = full
            update["content_preview"] = preview
        if content_hash and (changed or not site.get("last_hash")):
            update["last_hash"] = content_hash
            if changed or not site.get("last_hash"):
                update["last_changed"] = now
            if changed:
                session["change_logs"].insert_one({
                    "url": url, "title": title or site.get("title", ""),
                    "old_hash": site.get("last_hash"), "new_hash": content_hash,
                    "content_preview": preview, "detected_at": now
                })
        session["sites"].update_one({"url": url}, {"$set": update})
    else:
        site.last_checked = now
        site.last_status = status_code
        site.error_message = error
        site.updated_at = now
        if title:
            site.title = title
            site.name = title
        if full:
            site.content = full
            site.content_preview = preview
        if content_hash and changed:
            old = site.last_hash
            site.last_hash = content_hash
            site.last_changed = now
            session.add(ChangeLog(
                site_id=site.id, url=site.url, title=title or site.title,
                old_hash=old, new_hash=content_hash, content_preview=preview
            ))
        elif content_hash and not site.last_hash:
            site.last_hash = content_hash
            site.last_changed = now
        session.commit()

def get_all_sites_summary(session) -> List[Dict[str, Any]]:
    if STORAGE_BACKEND == "mongodb":
        return list(session["sites"].find().sort([("score", -1), ("last_changed", -1)]))
    sites = session.query(Site).order_by(Site.score.desc(), Site.last_changed.desc().nullslast()).all()
    return [{
        "id": s.id, "url": s.url, "name": s.name, "title": s.title,
        "category": s.category, "enabled": s.enabled,
        "last_checked": s.last_checked, "last_changed": s.last_changed,
        "last_status": s.last_status, "error": s.error_message,
        "content_preview": s.content_preview, "content": s.content,
        "source_type": s.source_type, "platform": s.platform, "score": s.score
    } for s in sites]

def get_recent_changes(session, limit: int = 40) -> List:
    if STORAGE_BACKEND == "mongodb":
        return list(session["change_logs"].find().sort("detected_at", -1).limit(limit))
    return session.query(ChangeLog).order_by(ChangeLog.detected_at.desc()).limit(limit).all()

_CONTENT_FILTER_MONGO = {
    "$or": [
        {"content_preview": {"$exists": True, "$nin": [None, ""]}},
        {"content": {"$exists": True, "$nin": [None, ""]}},
        {"title": {"$exists": True, "$nin": [None, ""]}},
    ]
}


def count_content_items(session) -> int:
    """Total items with content (safe for large Mongo collections).
    With two Mongo URLs, counts are summed (may double-count same URL if present in both)."""
    if STORAGE_BACKEND == "mongodb":
        total = 0
        sessions = get_all_mongo_sessions() or [(session, "primary")]
        for sess, _label in sessions:
            try:
                total += sess["sites"].count_documents(_CONTENT_FILTER_MONGO)
            except Exception:
                pass
        return total
    return (session.query(Site)
            .filter(
                (Site.content_preview.isnot(None) & (Site.content_preview != ""))
                | (Site.content.isnot(None) & (Site.content != ""))
                | (Site.title.isnot(None) & (Site.title != ""))
            ).count())


def get_content_items(session, limit: int = 100, skip: int = 0) -> List[Dict]:
    """Return items that actually have content (for the info feed).
    Supports skip/limit pagination for large MongoDB collections (100k–500k+)."""
    limit = max(1, min(int(limit or 100), 10_000_000))  # hard cap per request
    skip = max(0, int(skip or 0))
    if STORAGE_BACKEND == "mongodb":
        # Merge from primary + optional second full Mongo URL, dedupe by url
        sessions = get_all_mongo_sessions() or [(session, "primary")]
        merged = {}
        # Pull a window from each DB then sort/paginate in memory for stable merge
        per = max(limit + skip, limit)
        for sess, label in sessions:
            try:
                cursor = (sess["sites"].find(_CONTENT_FILTER_MONGO)
                          .sort([("score", -1), ("updated_at", -1), ("last_changed", -1)])
                          .limit(per))
                for d in cursor:
                    d = dict(d)
                    url = d.get("url") or str(d.get("_id"))
                    if "_id" in d:
                        d["id"] = str(d.pop("_id"))
                    if d.get("content"):
                        d["content"] = str(d["content"])[:2000]
                    d["_mongo"] = label
                    prev = merged.get(url)
                    if not prev or (d.get("score") or 0) >= (prev.get("score") or 0):
                        merged[url] = d
            except Exception as e:
                print(f"[mongo] read {label}: {e}")
        items = list(merged.values())
        items.sort(key=lambda x: (-(x.get("score") or 0), str(x.get("updated_at") or "")), reverse=False)
        items.sort(key=lambda x: (-(x.get("score") or 0)))
        return items[skip:skip + limit]
    sites = (session.query(Site)
             .filter(
                 (Site.content_preview.isnot(None) & (Site.content_preview != ""))
                 | (Site.content.isnot(None) & (Site.content != ""))
                 | (Site.title.isnot(None) & (Site.title != ""))
             )
             .order_by(Site.score.desc(), Site.updated_at.desc().nullslast(),
                       Site.last_changed.desc().nullslast())
             .offset(skip).limit(limit).all())
    return [{
        "id": s.id, "url": s.url, "name": s.name, "title": s.title,
        "category": s.category, "enabled": s.enabled,
        "last_checked": s.last_checked, "last_changed": s.last_changed,
        "updated_at": s.updated_at, "created_at": s.created_at,
        "last_status": s.last_status, "error": s.error_message,
        "content_preview": s.content_preview, "content": (s.content or "")[:2000],
        "source_type": s.source_type, "platform": s.platform, "score": s.score or 0,
    } for s in sites]


def weekly_top_articles(session, days: int = 7, limit: int = 15) -> List[Dict]:
    """Highest-scored items updated in the last `days` days.
    Ported from geonews-main's database.weekly_top_articles(), rewritten
    against Site.updated_at/score since that's what this schema tracks
    (geonews's version used a separate Mongo `articles` collection)."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if STORAGE_BACKEND == "mongodb":
        return list(session["sites"].find(
            {"updated_at": {"$gte": cutoff}}
        ).sort([("score", -1)]).limit(limit))
    sites = (session.query(Site)
             .filter(Site.updated_at >= cutoff)
             .order_by(Site.score.desc())
             .limit(limit).all())
    return [{"title": s.title or s.name, "url": s.url, "category": s.category,
              "score": s.score, "platform": s.platform} for s in sites]


def category_counts(session, days: int = 7) -> Dict[str, int]:
    """How many items landed in each category in the last `days` days."""
    from datetime import timedelta
    from collections import Counter
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    if STORAGE_BACKEND == "mongodb":
        docs = session["sites"].find({"updated_at": {"$gte": cutoff}}, {"category": 1})
        return dict(Counter(d.get("category", "general") for d in docs))
    sites = session.query(Site.category).filter(Site.updated_at >= cutoff).all()
    return dict(Counter(c for (c,) in sites))

