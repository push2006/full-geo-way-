"""
Social media trends collector — public sources only, no paid API keys.

Platforms:
- Reddit        (public JSON)
- Hacker News   (public API)
- YouTube       (public per-channel RSS feeds)
- Mastodon      (public trends/timeline API most instances expose)
- Telegram      (public channel preview pages — t.me/s/<channel>, off by default)
- Twitter/X     (via a Nitter mirror you provide — off by default; X itself
  has no free public API, so this is the only no-cost path and it's only
  as reliable as whichever Nitter instance you point it at)
"""
import re
from datetime import datetime
from typing import List, Dict
import requests
import feedparser
from core.config import (
    USER_AGENT, REQUEST_TIMEOUT, TREND_SUBREDDITS,
    ENABLE_YOUTUBE_TRENDS, YOUTUBE_CHANNEL_IDS,
    ENABLE_MASTODON_TRENDS, MASTODON_INSTANCES,
    ENABLE_TELEGRAM_TRENDS, TELEGRAM_PUBLIC_CHANNELS,
    ENABLE_TWITTER_TRENDS, NITTER_INSTANCE, TWITTER_ACCOUNTS,
    ENABLE_FACEBOOK_TRENDS, FACEBOOK_PAGE_ACCESS_TOKEN, FACEBOOK_PAGE_IDS,
    ENABLE_INSTAGRAM_TRENDS, INSTAGRAM_BUSINESS_ACCOUNT_IDS,
)
from core.tor_support import get_session_for

DEFAULT_SUBREDDITS = TREND_SUBREDDITS


def fetch_reddit_hot(subreddit: str = "worldnews", limit: int = 15) -> List[Dict]:
    """Fetch hot posts from a subreddit (public JSON, no key needed)."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    headers = {"User-Agent": USER_AGENT}
    try:
        session = get_session_for(url)
        resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
            d = child.get("data", {})
            posts.append({
                "platform": "Reddit",
                "source": f"r/{subreddit}",
                "title": d.get("title", ""),
                "url": "https://www.reddit.com" + d.get("permalink", ""),
                "score": d.get("score", 0),
                "comments": d.get("num_comments", 0),
                "created": datetime.utcfromtimestamp(d.get("created_utc", 0)).isoformat() if d.get("created_utc") else "",
            })
        return posts
    except Exception:
        return []


def fetch_all_reddit_trends(subreddits: List[str] = None, limit_per: int = 8) -> List[Dict]:
    subreddits = subreddits or DEFAULT_SUBREDDITS
    all_posts = []
    for sub in subreddits:
        all_posts.extend(fetch_reddit_hot(sub, limit=limit_per))
    all_posts.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_posts


def fetch_hackernews_top(limit: int = 15) -> List[Dict]:
    """Hacker News top stories (public API)."""
    try:
        session = get_session_for("https://hacker-news.firebaseio.com")
        ids = session.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=15).json()[:limit]
        items = []
        for i in ids[:limit]:
            try:
                item = session.get(f"https://hacker-news.firebaseio.com/v0/item/{i}.json", timeout=10).json()
                if item and item.get("title"):
                    items.append({
                        "platform": "HackerNews",
                        "source": "HN",
                        "title": item.get("title", ""),
                        "url": item.get("url") or f"https://news.ycombinator.com/item?id={i}",
                        "score": item.get("score", 0),
                        "comments": item.get("descendants", 0),
                        "created": datetime.utcfromtimestamp(item.get("time", 0)).isoformat() if item.get("time") else "",
                    })
            except Exception:
                continue
        return items
    except Exception:
        return []


def fetch_youtube_channel(channel_id: str, limit: int = 10) -> List[Dict]:
    """Latest uploads from one channel via YouTube's public per-channel
    RSS feed — no API key needed, but no view/like counts either (that
    data isn't in the feed)."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        session = get_session_for(url)
        resp = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.content)
        items = []
        for e in feed.entries[:limit]:
            items.append({
                "platform": "YouTube",
                "source": getattr(feed.feed, "title", channel_id),
                "title": e.get("title", ""),
                "url": e.get("link", ""),
                "score": 0,  # not exposed by the RSS feed
                "comments": 0,
                "created": e.get("published", ""),
            })
        return items
    except Exception:
        return []


def fetch_all_youtube_trends(channel_ids: List[str] = None, limit_per: int = 5) -> List[Dict]:
    if not ENABLE_YOUTUBE_TRENDS:
        return []
    channel_ids = channel_ids or YOUTUBE_CHANNEL_IDS
    items = []
    for cid in channel_ids:
        items.extend(fetch_youtube_channel(cid, limit=limit_per))
    return items


def fetch_mastodon_trending(instance: str, limit: int = 15) -> List[Dict]:
    """Trending posts on a Mastodon instance's public timeline API.
    Most large instances (mastodon.social, mastodon.world, ...) allow
    this with no auth token."""
    url = f"https://{instance}/api/v1/trends/statuses?limit={limit}"
    try:
        session = get_session_for(url)
        resp = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        posts = []
        for s in resp.json():
            text = re.sub("<[^<]+?>", "", s.get("content", "")).strip()
            posts.append({
                "platform": "Mastodon",
                "source": instance,
                "title": text[:200],
                "url": s.get("url", ""),
                "score": s.get("reblogs_count", 0) + s.get("favourites_count", 0),
                "comments": s.get("replies_count", 0),
                "created": s.get("created_at", ""),
            })
        return posts
    except Exception:
        return []


def fetch_all_mastodon_trends(instances: List[str] = None, limit_per: int = 10) -> List[Dict]:
    if not ENABLE_MASTODON_TRENDS:
        return []
    instances = instances or MASTODON_INSTANCES
    posts = []
    for inst in instances:
        posts.extend(fetch_mastodon_trending(inst, limit=limit_per))
    posts.sort(key=lambda x: x.get("score", 0), reverse=True)
    return posts


def fetch_telegram_channel(channel: str, limit: int = 10) -> List[Dict]:
    """Latest posts from a PUBLIC Telegram channel via its t.me/s/
    preview page — no bot token or login needed, since Telegram serves
    this page to anyone. HTML-scraped, so more fragile than the JSON/RSS
    sources above; off by default (ENABLE_TELEGRAM_TRENDS)."""
    url = f"https://t.me/s/{channel}"
    try:
        session = get_session_for(url)
        resp = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        html = resp.text
        blocks = re.findall(
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', html, re.S
        )
        posts = []
        for b in blocks[-limit:]:
            text = re.sub("<[^<]+?>", "", b).strip()
            if text:
                posts.append({
                    "platform": "Telegram",
                    "source": f"t.me/{channel}",
                    "title": text[:200],
                    "url": f"https://t.me/{channel}",
                    "score": 0,
                    "comments": 0,
                    "created": "",
                })
        return posts
    except Exception:
        return []


def fetch_all_telegram_trends(channels: List[str] = None, limit_per: int = 8) -> List[Dict]:
    if not ENABLE_TELEGRAM_TRENDS:
        return []
    channels = channels or TELEGRAM_PUBLIC_CHANNELS
    posts = []
    for ch in channels:
        posts.extend(fetch_telegram_channel(ch, limit=limit_per))
    return posts


def fetch_twitter_account(account: str, limit: int = 10) -> List[Dict]:
    """Recent tweets from a public account, via a Nitter mirror's RSS
    feed. X/Twitter itself has had no free public API since 2023 --
    this is the only no-cost path, and it's exactly as reliable as
    NITTER_INSTANCE (public mirrors go down often; self-hosting one is
    the sturdier option). Off unless both ENABLE_TWITTER_TRENDS=true
    and NITTER_INSTANCE is set."""
    if not NITTER_INSTANCE:
        return []
    url = f"{NITTER_INSTANCE.rstrip('/')}/{account}/rss"
    try:
        session = get_session_for(url)
        resp = session.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.content)
        items = []
        for e in feed.entries[:limit]:
            items.append({
                "platform": "Twitter/X",
                "source": f"@{account}",
                "title": e.get("title", ""),
                "url": e.get("link", ""),
                "score": 0,
                "comments": 0,
                "created": e.get("published", ""),
            })
        return items
    except Exception:
        return []


def fetch_all_twitter_trends(accounts: List[str] = None, limit_per: int = 8) -> List[Dict]:
    if not ENABLE_TWITTER_TRENDS or not NITTER_INSTANCE:
        return []
    accounts = accounts or TWITTER_ACCOUNTS
    items = []
    for acc in accounts:
        items.extend(fetch_twitter_account(acc, limit=limit_per))
    return items


def fetch_facebook_page(page_id: str, limit: int = 10) -> List[Dict]:
    """Posts from a Facebook Page YOU administer, via the official Graph
    API. There is no public/anonymous Facebook feed -- this only ever
    sees Pages the configured FACEBOOK_PAGE_ACCESS_TOKEN has access to,
    not a general "trending on Facebook" feed (that doesn't exist)."""
    if not FACEBOOK_PAGE_ACCESS_TOKEN:
        return []
    url = f"https://graph.facebook.com/v19.0/{page_id}/posts"
    params = {
        "fields": "message,permalink_url,created_time,shares,reactions.summary(true),comments.summary(true)",
        "limit": limit,
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
    }
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        posts = []
        for p in resp.json().get("data", []):
            reactions = (p.get("reactions", {}) or {}).get("summary", {}).get("total_count", 0)
            comments = (p.get("comments", {}) or {}).get("summary", {}).get("total_count", 0)
            posts.append({
                "platform": "Facebook",
                "source": page_id,
                "title": (p.get("message") or "")[:200],
                "url": p.get("permalink_url", ""),
                "score": reactions + (p.get("shares", {}) or {}).get("count", 0),
                "comments": comments,
                "created": p.get("created_time", ""),
            })
        return posts
    except Exception:
        return []


def fetch_all_facebook_trends(page_ids: List[str] = None, limit_per: int = 10) -> List[Dict]:
    if not ENABLE_FACEBOOK_TRENDS or not FACEBOOK_PAGE_ACCESS_TOKEN:
        return []
    page_ids = page_ids or FACEBOOK_PAGE_IDS
    posts = []
    for pid in page_ids:
        posts.extend(fetch_facebook_page(pid, limit=limit_per))
    return posts


def fetch_instagram_account(ig_account_id: str, limit: int = 10) -> List[Dict]:
    """Posts from an Instagram Business/Creator account YOU administer
    (must be linked to a Facebook Page), via the same Graph API + token
    as Facebook above. Instagram has no separate free/public API and no
    anonymous "explore/trending" endpoint at all."""
    if not FACEBOOK_PAGE_ACCESS_TOKEN:
        return []
    url = f"https://graph.facebook.com/v19.0/{ig_account_id}/media"
    params = {
        "fields": "caption,permalink,timestamp,like_count,comments_count",
        "limit": limit,
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN,
    }
    try:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return []
        posts = []
        for p in resp.json().get("data", []):
            posts.append({
                "platform": "Instagram",
                "source": ig_account_id,
                "title": (p.get("caption") or "")[:200],
                "url": p.get("permalink", ""),
                "score": p.get("like_count", 0),
                "comments": p.get("comments_count", 0),
                "created": p.get("timestamp", ""),
            })
        return posts
    except Exception:
        return []


def fetch_all_instagram_trends(account_ids: List[str] = None, limit_per: int = 10) -> List[Dict]:
    if not ENABLE_INSTAGRAM_TRENDS or not FACEBOOK_PAGE_ACCESS_TOKEN:
        return []
    account_ids = account_ids or INSTAGRAM_BUSINESS_ACCOUNT_IDS
    posts = []
    for aid in account_ids:
        posts.extend(fetch_instagram_account(aid, limit=limit_per))
    return posts


def collect_trends() -> List[Dict]:
    """Collect trends from every enabled platform."""
    results = []

    print("📡 Fetching Reddit trends...")
    results.extend(fetch_all_reddit_trends())

    print("📡 Fetching Hacker News...")
    results.extend(fetch_hackernews_top())

    if ENABLE_YOUTUBE_TRENDS:
        print("📡 Fetching YouTube channel uploads...")
        results.extend(fetch_all_youtube_trends())

    if ENABLE_MASTODON_TRENDS:
        print("📡 Fetching Mastodon trending posts...")
        results.extend(fetch_all_mastodon_trends())

    if ENABLE_TELEGRAM_TRENDS:
        print("📡 Fetching Telegram public channels...")
        results.extend(fetch_all_telegram_trends())

    if ENABLE_TWITTER_TRENDS:
        print("📡 Fetching Twitter/X via Nitter...")
        results.extend(fetch_all_twitter_trends())

    if ENABLE_FACEBOOK_TRENDS:
        print("📡 Fetching Facebook Page posts...")
        results.extend(fetch_all_facebook_trends())

    if ENABLE_INSTAGRAM_TRENDS:
        print("📡 Fetching Instagram Business account posts...")
        results.extend(fetch_all_instagram_trends())

    # Deduplicate by title roughly
    seen = set()
    unique = []
    for r in results:
        key = (r.get("title") or "")[:80].lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    unique.sort(key=lambda x: x.get("score", 0), reverse=True)
    return unique
