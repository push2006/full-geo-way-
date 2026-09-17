"""Instant alert for high-signal items, bypassing the normal digest
schedule. OFF unless ENABLE_CRITICAL_ALERTS=true.

Uses core.threat_classifier (ported from worldmonitor's
shared/threat-keyword-classifier.ts) instead of GeoWatch-Pro's original
flat substring is_critical() -- the ported version is tiered
(critical/high/medium/low), word-boundary aware on ambiguous short
words, has an exclusion list for false positives ("Israel strikes deal"
is not a military strike), and escalates HIGH to CRITICAL when a
military-action verb appears near a flashpoint country even if the
words aren't adjacent ("strikes by US and Israel on Iran").
"""
from core import config as C
from html import escape
from urllib.parse import urlparse
import hashlib

_SENT = set()
from core.threat_classifier import classify_by_keyword
from notifications import email_report, whatsapp, telegram


def check_and_alert(articles):
    if not getattr(C, "ENABLE_CRITICAL_ALERTS", False):
        return []
    critical = []
    for a in articles:
        text = f"{a.get('title','')} {a.get('content','')}".strip()
        result = classify_by_keyword(text)
        if result["level"] == "critical":
            a = dict(a)
            a["_threat_category"] = result["category"]
            critical.append(a)
    if not critical:
        return []

    lines = ["<h2>\U0001F6A8 CRITICAL ALERT</h2><ul>"]
    for a in critical:
        title = a.get("title") or a.get("name") or "Untitled"
        cat = a.get("_threat_category", "")
        lines.append(f"<li><a href='{a.get('url','')}'>{title}</a> "
                      f"\u2014 {a.get('platform','')} [{cat}]</li>")
    lines.append("</ul>")
    html = "\n".join(lines)

    # FIX #10: Add error handling for all notification sends
    if getattr(C, "ENABLE_EMAIL", False):
        try:
            email_report.send(html, subject="\U0001F6A8 GeoWatch CRITICAL ALERT")
        except Exception as e:
            print(f"⚠️  Email alert failed: {e}")
    
    if getattr(C, "ENABLE_WHATSAPP", False):
        try:
            whatsapp.send(critical, limit=5)
        except Exception as e:
            print(f"⚠️  WhatsApp alert failed: {e}")
    
    if getattr(C, "ENABLE_TELEGRAM", False):
        try:
            telegram.send(critical, limit=5)
        except Exception as e:
            print(f"⚠️  Telegram alert failed: {e}")
    
    return critical
