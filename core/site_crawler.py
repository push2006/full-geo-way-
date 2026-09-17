"""Multi-page site crawler."""
from collections import deque
from typing import Set, List, Dict, Optional
from urllib.parse import urljoin, urlparse, urldefrag
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
warnings.filterwarnings('ignore', category=XMLParsedAsHTMLWarning)
from tqdm import tqdm
from core.config import MAX_CONTENT_LENGTH, DELAY_BETWEEN_REQUESTS
from core.crawler import clean_html, content_hash, polite_delay
from core.tor_support import get_session_for, is_onion
import time

def same_domain(base: str, link: str) -> bool:
    try:
        return urlparse(link).netloc == urlparse(base).netloc or not urlparse(link).netloc
    except Exception:
        return False

def normalize_url(base: str, link: str) -> Optional[str]:
    try:
        full = urljoin(base, link)
        full, _ = urldefrag(full)
        p = urlparse(full)
        if p.scheme not in ("http", "https"):
            return None
        skip = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".zip", ".css", ".js", ".mp4", ".mp3", ".woff", ".ico")
        if any(p.path.lower().endswith(e) for e in skip):
            return None
        return full
    except Exception:
        return None

def extract_links(html: str, base_url: str) -> List[str]:
    links = []
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("mailto:", "tel:", "javascript:")):
                continue
            full = normalize_url(base_url, href)
            if full and same_domain(base_url, full):
                links.append(full)
    except Exception:
        pass
    return list(dict.fromkeys(links))

def fetch_raw(url: str):
    try:
        session = get_session_for(url)
        resp = session.get(url, timeout=25 * (2 if is_onion(url) else 1), allow_redirects=True)
        if resp.status_code >= 400:
            return None, resp.status_code, f"HTTP {resp.status_code}"
        text = resp.text
        if len(text) > MAX_CONTENT_LENGTH * 2:
            text = text[: MAX_CONTENT_LENGTH * 2]
        return text, resp.status_code, None
    except Exception as e:
        return None, None, str(e)[:200]

def crawl_site(start_url: str, max_pages: int = 25, max_depth: int = 2) -> List[Dict]:
    visited: Set[str] = set()
    queue = deque([(start_url, 0)])
    results = []
    pbar = tqdm(total=max_pages, desc=f"Crawl {urlparse(start_url).netloc}", leave=False)

    while queue and len(results) < max_pages:
        url, depth = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        html, status, error = fetch_raw(url)
        polite_delay()
        if error or not html:
            results.append({"url": url, "title": "", "text": "", "hash": None, "status": status, "error": error, "depth": depth})
            pbar.update(1)
            continue
        title = ""
        try:
            soup = BeautifulSoup(html, "lxml")
            if soup.title and soup.title.string:
                title = soup.title.string.strip()[:300]
        except Exception:
            pass
        text = clean_html(html)
        results.append({"url": url, "title": title, "text": text, "hash": content_hash(text),
                        "status": status, "error": None, "depth": depth})
        pbar.update(1)
        if depth < max_depth:
            for link in extract_links(html, url):
                if link not in visited and len(visited) + len(queue) < max_pages * 2:
                    queue.append((link, depth + 1))
    pbar.close()
    return results

def crawl_and_store(start_url: str, site_name: str = "", max_pages: int = 20, max_depth: int = 2):
    from core.storage import init_db, get_session, upsert_site, update_site_after_check
    from urllib.parse import urlparse
    init_db()
    session = get_session()
    upsert_site(session, start_url, name=site_name or urlparse(start_url).netloc, category="crawled", source_type="page")
    pages = crawl_site(start_url, max_pages=max_pages, max_depth=max_depth)
    print(f"Crawled {len(pages)} pages from {start_url}")
    changed = 0
    for page in pages:
        site = upsert_site(session, page["url"], name=page["title"] or page["url"],
                           category="crawled-page", source_type="page")
        last_hash = site.get("last_hash") if isinstance(site, dict) else site.last_hash
        is_changed = last_hash is not None and last_hash != page["hash"]
        if is_changed:
            changed += 1
        update_site_after_check(
            session, site,
            content_hash=page["hash"],
            status_code=page["status"],
            content=page["text"] if page["text"] else None,
            title=page.get("title") or "",
            error=page["error"],
            changed=is_changed,
        )
    if not isinstance(session, dict) and hasattr(session, "close"):
        session.close()
    print(f"Stored. Changed pages: {changed}")
    return pages
