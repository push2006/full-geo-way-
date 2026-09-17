"""OFAC sanctions-list screening (ported from geonews-main).
Downloads the OFAC SDN name list and screens article text for hits.
Level-up: skips short/numeric tokens and uses word-boundary matching
to cut false positives (random numbers, partial substrings).
"""
import csv
import io
import re
import requests
from core.config import REQUEST_TIMEOUT

OFAC_SDN = "https://www.treasury.gov/ofac/downloads/sdn.csv"

# Cache names for the process lifetime after first successful download
_cached_names = None


def update_ofac_names(force: bool = False):
    global _cached_names
    if _cached_names is not None and not force:
        return _cached_names
    try:
        r = requests.get(OFAC_SDN, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        names = []
        for row in csv.reader(io.StringIO(r.text)):
            if not row or not row[0].strip():
                continue
            n = row[0].strip()
            if len(n) < 5:
                continue
            if not any(c.isalpha() for c in n):
                continue
            names.append(n)
        _cached_names = names
        return names
    except Exception as exc:
        print("[SANCTIONS] OFAC download failed:", exc)
        return _cached_names or []


def screen_text(text, names):
    """Return matched OFAC names (max 20). Word-boundary, min length 5, must have letters."""
    t = (text or "").lower()
    if not t or not names:
        return []
    hits = []
    for n in names:
        nl = n.lower().strip()
        if len(nl) < 5:
            continue
        if not any(c.isalpha() for c in nl):
            continue
        try:
            if re.search(r"(?<!\w)" + re.escape(nl) + r"(?!\w)", t):
                hits.append(n)
        except re.error:
            if nl in t:
                hits.append(n)
        if len(hits) >= 20:
            break
    return hits
