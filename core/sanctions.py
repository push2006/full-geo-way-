"""OFAC sanctions-list screening (ported from geonews-main).
Downloads the OFAC SDN name list and lets you check article text for
hits. Not wired into the crawl loop automatically -- call screen_text()
from wherever you want it (e.g. before a critical alert fires).
"""
import csv
import io
import requests
from core.config import REQUEST_TIMEOUT

OFAC_SDN = "https://www.treasury.gov/ofac/downloads/sdn.csv"


def update_ofac_names():
    try:
        r = requests.get(OFAC_SDN, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return [row[0].strip() for row in csv.reader(io.StringIO(r.text)) if row and row[0].strip()]
    except Exception as exc:
        print("[SANCTIONS] OFAC download failed:", exc)
        return []


def screen_text(text, names):
    t = (text or "").lower()
    return [n for n in names if n.lower() in t][:20]
