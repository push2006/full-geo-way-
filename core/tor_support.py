"""Tor / Onion support."""
import warnings
import requests
from core.config import USE_TOR, TOR_SOCKS_HOST, TOR_SOCKS_PORT, ENABLE_ONION

def is_onion(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        host = (urlparse(url).hostname or "").lower()
        return host.endswith(".onion")
    except Exception:
        return False

def get_session_for(url: str = None) -> requests.Session:
    """Return a requests session, routed through Tor if needed."""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; GeoWatch-Pro/2.0)"})

    need_tor = USE_TOR or (url and is_onion(url) and ENABLE_ONION)
    if need_tor:
        if not USE_TOR and is_onion(url):
            # Auto-enable Tor path for onion when ENABLE_ONION=true
            pass
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
