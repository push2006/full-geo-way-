"""Page fetcher + change detection helpers."""
import hashlib
import time
import logging
import warnings
from typing import Optional, Tuple
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from core.config import REQUEST_TIMEOUT, DELAY_BETWEEN_REQUESTS, MAX_CONTENT_LENGTH
from core.tor_support import get_session_for, is_onion

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# FIX #7: Add logging for truncation
logger = logging.getLogger(__name__)


def clean_html(html: str) -> str:
    try:
        # Prefer HTML mode; ignore XML-as-HTML warning for RSS-like pages
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "iframe"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        return "\n".join(lines)
    except Exception:
        try:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except Exception:
            return html[:MAX_CONTENT_LENGTH]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def fetch_page(url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
    try:
        session = get_session_for(url)
        resp = session.get(
            url,
            timeout=REQUEST_TIMEOUT * (2 if is_onion(url) else 1),
            allow_redirects=True,
        )
        if resp.status_code >= 400:
            return None, resp.status_code, f"HTTP {resp.status_code}"
        text = resp.text
        # FIX #7: Log truncation instead of silently truncating
        if len(text) > MAX_CONTENT_LENGTH:
            logger.warning(f"Content truncated for {url[:80]} ({len(text)} chars -> {MAX_CONTENT_LENGTH})")
            text = text[:MAX_CONTENT_LENGTH]
        return clean_html(text), resp.status_code, None
    except Exception as e:
        return None, None, str(e)[:220]


def polite_delay():
    time.sleep(DELAY_BETWEEN_REQUESTS)
