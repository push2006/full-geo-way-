"""Storage — SQLite (default) or MongoDB. Stores real content, not just metadata."""
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.config import STORAGE_BACKEND, SQLITE_PATH, MONGODB_URI, MONGODB_DB

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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ChangeLog(Base):
    __tablename__ = "change_logs"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, index=True)
    url = Column(String(2048))
    title = Column(String(512), default="")
    old_hash = Column(String(64), nullable=True)
    new_hash = Column(String(64))
    content_preview = Column(Text, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow)

def _init_sqlite():
    global _engine, _Session
    _engine = create_engine(f"sqlite:///{SQLITE_PATH}", echo=False)
    Base.metadata.create_all(bind=_engine)
    _Session = sessionmaker(bind=_engine)

def _init_mongo():
    from pymongo import MongoClient
    return MongoClient(MONGODB_URI, serverSelectionTimeoutMS=4000)[MONGODB_DB]

def init_db():
    if STORAGE_BACKEND == "mongodb":
        _init_mongo()
    else:
        _init_sqlite()

def get_session():
    if STORAGE_BACKEND == "mongodb":
        return _init_mongo()
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
                "updated_at": datetime.utcnow()
            }, "$setOnInsert": {"created_at": datetime.utcnow()}},
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
            site.updated_at = datetime.utcnow()
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
    now = datetime.utcnow()
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

def get_content_items(session, limit: int = 100) -> List[Dict]:
    """Return items that actually have content (for the info feed)."""
    if STORAGE_BACKEND == "mongodb":
        return list(session["sites"].find(
            {"content_preview": {"$exists": True, "$ne": None, "$ne": ""}}
        ).sort([("score", -1), ("last_changed", -1)]).limit(limit))
    sites = (session.query(Site)
             .filter(Site.content_preview.isnot(None), Site.content_preview != "")
             .order_by(Site.score.desc(), Site.last_changed.desc().nullslast())
             .limit(limit).all())
    return get_all_sites_summary(session)[:limit]  # already ordered; filter below in UI


def weekly_top_articles(session, days: int = 7, limit: int = 15) -> List[Dict]:
    """Highest-scored items updated in the last `days` days.
    Ported from geonews-main's database.weekly_top_articles(), rewritten
    against Site.updated_at/score since that's what this schema tracks
    (geonews's version used a separate Mongo `articles` collection)."""
    from datetime import timedelta
    cutoff = datetime.utcnow() - timedelta(days=days)
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
    cutoff = datetime.utcnow() - timedelta(days=days)
    if STORAGE_BACKEND == "mongodb":
        docs = session["sites"].find({"updated_at": {"$gte": cutoff}}, {"category": 1})
        return dict(Counter(d.get("category", "general") for d in docs))
    sites = session.query(Site.category).filter(Site.updated_at >= cutoff).all()
    return dict(Counter(c for (c,) in sites))

