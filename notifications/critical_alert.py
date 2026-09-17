"""Instant alert for high-signal items, bypassing the normal digest
schedule. OFF unless ENABLE_CRITICAL_ALERTS=true.

Uses GeoWatch-Pro's own core.classifier.is_critical() (its scoring/
keyword logic) rather than reimplementing BRICS's version, since that
one was tied to BRICS's separate article-scoring pipeline.
"""
from core import config as C
from core.classifier import is_critical
from notifications import email_report, whatsapp, telegram


def check_and_alert(articles):
    if not getattr(C, "ENABLE_CRITICAL_ALERTS", False):
        return []
    critical = [a for a in articles
                if is_critical(a.get("title", ""), a.get("content", ""))]
    if not critical:
        return []

    lines = ["<h2>\U0001F6A8 CRITICAL ALERT</h2><ul>"]
    for a in critical:
        title = a.get("title") or a.get("name") or "Untitled"
        lines.append(f"<li><a href='{a.get('url','')}'>{title}</a> \u2014 {a.get('platform','')}</li>")
    lines.append("</ul>")
    html = "\n".join(lines)

    if getattr(C, "ENABLE_EMAIL", False):
        email_report.send(html, subject="\U0001F6A8 GeoWatch CRITICAL ALERT")
    if getattr(C, "ENABLE_WHATSAPP", False):
        whatsapp.send(critical, limit=5)
    if getattr(C, "ENABLE_TELEGRAM", False):
        telegram.send(critical, limit=5)
    return critical
