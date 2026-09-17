"""Glue: pull recent items from GeoWatch-Pro's storage and fan them out
to whichever notification channels are enabled. Call run_digest() from
a scheduler, a cron job, or manually — it is not wired into run.py's
core loop automatically so that notifications stay opt-in.

Usage:
    python -m notifications.digest
"""
from core.storage import get_session, get_content_items
from core import config as C
from notifications import email_report, whatsapp, telegram, critical_alert


def run_digest(limit=50):
    session = get_session()
    try:
        items = get_content_items(session, limit=limit)
    finally:
        if hasattr(session, "close"):
            session.close()

    critical_alert.check_and_alert(items)

    if getattr(C, "ENABLE_EMAIL", False):
        html = email_report.build_digest(items)
        email_report.send(html)
    if getattr(C, "ENABLE_TELEGRAM", False):
        telegram.send(items)
    if getattr(C, "ENABLE_WHATSAPP", False):
        whatsapp.send(items)

    return items


if __name__ == "__main__":
    sent = run_digest()
    print(f"Digest run: {len(sent)} items considered")
