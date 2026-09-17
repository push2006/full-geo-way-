"""Tor / Onion support."""
import warnings
import requests
from core.config import USE_TOR, TOR_SOCKS_HOST, TOR_SOCKS_PORT, ENABLE_ONION, USER_AGENT

def is_onion(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        return host.endswith(".onion")
    except Exception:
        return False

def _browser_headers() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

def get_session_for(url: str = None) -> requests.Session:
    """Return a requests session, routed through Tor if needed."""
    session = requests.Session()
    session.headers.update(_browser_headers())

    need_tor = USE_TOR or (url and is_onion(url) and ENABLE_ONION)
    if need_tor:
        proxy = f"socks5h://{TOR_SOCKS_HOST}:{TOR_SOCKS_PORT}"
        session.proxies = {"http": proxy, "https": proxy}
    return session

def check_tor() -> bool:
    if not (USE_TOR or ENABLE_ONION):
        return False
    try:
        s = get_session_for("http://check.torproject.org")
        r = s.get("https://check.torproject.org/api/ip", timeout=15)
        return r.json().get("IsTor", False)
    except Exception:
        return False
