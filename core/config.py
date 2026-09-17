import os
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)
CONFIG_DIR = ROOT / "config"

# Single sources config (replaces sources.csv + brics_sources.yaml)
SOURCES_FILE = CONFIG_DIR / "sources.yaml"


def load_sources(enabled_only: bool = False) -> List[Dict]:
    """Load all sources from the single config/sources.yaml file."""
    import yaml
    if not SOURCES_FILE.exists():
        return []
    with open(SOURCES_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    sources = data.get("sources") or []
    out = []
    for s in sources:
        if not isinstance(s, dict) or not s.get("url"):
            continue
        enabled = s.get("enabled", True)
        if isinstance(enabled, str):
            enabled = enabled.lower() in ("true", "1", "yes")
        if enabled_only and not enabled:
            continue
        out.append({
            "name": (s.get("name") or "").strip(),
            "url": (s.get("url") or "").strip(),
            "category": (s.get("category") or "general").strip(),
            "enabled": bool(enabled),
            "type": (s.get("type") or "rss").strip().lower(),
            "country": (s.get("country") or "").strip(),
            "tier": s.get("tier"),
        })
    return out


# Storage backend: "sqlite" or "mongodb"
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "sqlite").lower()
SQLITE_PATH = os.getenv("SQLITE_PATH", str(DATA_DIR / "geowatch.db"))
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "geowatch")

USER_AGENT = os.getenv("USER_AGENT", "GeoWatch-Pro/2.0 (legitimate research)")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "25"))
DELAY_BETWEEN_REQUESTS = float(os.getenv("DELAY_BETWEEN_REQUESTS", "1.2"))
MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_LENGTH", "600000"))

# Tor / Onion
USE_TOR = os.getenv("USE_TOR", "false").lower() in ("true", "1", "yes")
TOR_SOCKS_HOST = os.getenv("TOR_SOCKS_HOST", "127.0.0.1")
TOR_SOCKS_PORT = int(os.getenv("TOR_SOCKS_PORT", "9050"))
ENABLE_ONION = os.getenv("ENABLE_ONION", "true").lower() in ("true", "1", "yes")

# RSS
RSS_MAX_ITEMS = int(os.getenv("RSS_MAX_ITEMS", "15"))

# Google News keyword collector (ported from geonews-main; off by default)
ENABLE_GNEWS = os.getenv("ENABLE_GNEWS", "false").lower() in ("true", "1", "yes")
GNEWS_LANGUAGE = os.getenv("GNEWS_LANGUAGE", "en")
GNEWS_COUNTRY = os.getenv("GNEWS_COUNTRY", "US")
GNEWS_PERIOD = os.getenv("GNEWS_PERIOD", "1d")
GNEWS_MAX_RESULTS = int(os.getenv("GNEWS_MAX_RESULTS", "20"))
GNEWS_QUERY_GROUPS = [
    ["BRICS", "BRICS summit"],
    ["sanctions", "trade order", "FTA"],
    ["geopolitics", "diplomatic crisis"],
]

# OFAC sanctions screening (ported from geonews-main; not auto-run)
ENABLE_SANCTIONS_SCREEN = os.getenv("ENABLE_SANCTIONS_SCREEN", "false").lower() in ("true", "1", "yes")

# --- Notifications (ported from BRICS/geonews, off by default) ---
ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "false").lower() in ("true", "1", "yes")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")

ENABLE_TELEGRAM = os.getenv("ENABLE_TELEGRAM", "false").lower() in ("true", "1", "yes")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

ENABLE_WHATSAPP = os.getenv("ENABLE_WHATSAPP", "false").lower() in ("true", "1", "yes")
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")
WHATSAPP_APIKEY = os.getenv("WHATSAPP_APIKEY", "")

ENABLE_CRITICAL_ALERTS = os.getenv("ENABLE_CRITICAL_ALERTS", "false").lower() in ("true", "1", "yes")
CRITICAL_KEYWORDS = [k.strip().lower() for k in os.getenv(
    "CRITICAL_KEYWORDS", "sanctions,military strike,invasion,ceasefire collapse,nuclear"
).split(",") if k.strip()]

ENABLE_WEEKLY_REPORT = os.getenv("ENABLE_WEEKLY_REPORT", "false").lower() in ("true", "1", "yes")

# Dashboard (core/webapp.py)
DASHBOARD_HOST = os.getenv("HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.getenv("PORT", "8501"))

# --- Trends: social platforms beyond Reddit/HN ---
# All of these use free public endpoints — no paid API keys required.
TREND_SUBREDDITS = [s.strip() for s in os.getenv(
    "TREND_SUBREDDITS",
    "worldnews,geopolitics,news,India,China,Russia,europe,africa,MiddleEast,economics,technology"
).split(",") if s.strip()]

ENABLE_YOUTUBE_TRENDS = os.getenv("ENABLE_YOUTUBE_TRENDS", "true").lower() in ("true", "1", "yes")
# Channel IDs, not @handles — find one via a channel's page source or
# https://commentpicker.com/youtube-channel-id.php
YOUTUBE_CHANNEL_IDS = [c.strip() for c in os.getenv(
    "YOUTUBE_CHANNEL_IDS",
    "UC16niRr50-MSBwiO3YDb3RA,UCknLrEdhRCp1aegoMqRaCZg"  # DW News, Al Jazeera English
).split(",") if c.strip()]

ENABLE_MASTODON_TRENDS = os.getenv("ENABLE_MASTODON_TRENDS", "true").lower() in ("true", "1", "yes")
# Public timeline/trends API — most large instances allow anonymous reads
MASTODON_INSTANCES = [m.strip() for m in os.getenv(
    "MASTODON_INSTANCES", "mastodon.social,mastodon.world"
).split(",") if m.strip()]

ENABLE_TELEGRAM_TRENDS = os.getenv("ENABLE_TELEGRAM_TRENDS", "false").lower() in ("true", "1", "yes")
# Public channel usernames (no @, no bot token needed) — scrapes the
# public t.me/s/<channel> preview page, which Telegram serves with no
# login. Off by default since scraping HTML is more fragile than the
# JSON/RSS endpoints the other platforms use.
TELEGRAM_PUBLIC_CHANNELS = [c.strip().lstrip("@") for c in os.getenv(
    "TELEGRAM_PUBLIC_CHANNELS", ""
).split(",") if c.strip()]

ENABLE_TWITTER_TRENDS = os.getenv("ENABLE_TWITTER_TRENDS", "false").lower() in ("true", "1", "yes")
# X/Twitter has no free public API since 2023. This talks to a
# self-hosted or public Nitter mirror instead, which is why it's off by
# default and needs a URL you trust/control -- public Nitter instances
# go up and down often. Run your own for anything you depend on.
NITTER_INSTANCE = os.getenv("NITTER_INSTANCE", "")  # e.g. https://nitter.example.com
TWITTER_ACCOUNTS = [a.strip().lstrip("@") for a in os.getenv(
    "TWITTER_ACCOUNTS", ""
).split(",") if a.strip()]

# Facebook / Instagram: unlike the platforms above, these have no
# anonymous public endpoint at all -- Meta's Graph API requires a token
# tied to a Page/account you administer. This can only pull posts from
# YOUR OWN Page(s), not a public firehose or "trending" feed. Get a
# Page access token via https://developers.facebook.com/tools/explorer
ENABLE_FACEBOOK_TRENDS = os.getenv("ENABLE_FACEBOOK_TRENDS", "false").lower() in ("true", "1", "yes")
FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
FACEBOOK_PAGE_IDS = [p.strip() for p in os.getenv("FACEBOOK_PAGE_IDS", "").split(",") if p.strip()]

# Instagram Business/Creator accounts linked to a Facebook Page, via the
# same Graph API + token as above (Instagram has no separate free API).
ENABLE_INSTAGRAM_TRENDS = os.getenv("ENABLE_INSTAGRAM_TRENDS", "false").lower() in ("true", "1", "yes")
INSTAGRAM_BUSINESS_ACCOUNT_IDS = [i.strip() for i in os.getenv(
    "INSTAGRAM_BUSINESS_ACCOUNT_IDS", ""
).split(",") if i.strip()]
