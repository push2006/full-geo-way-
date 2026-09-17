"""Weekly trend summary (ported from geonews-main's reports/weekly_report.py,
rewritten against core.storage instead of geonews's own database.py).
OFF unless ENABLE_WEEKLY_REPORT=true. Meant to run alongside the normal
daily digest -- gives a 7-day view: top stories by score and which
categories were busiest, so a slow-building trend shows up even on a
day whose own digest looks quiet.
"""
from core import config as C
from core.storage import get_session, weekly_top_articles, category_counts
from notifications.email_report import send as send_email


def build_weekly_digest(days=7, limit=15):
    session = get_session()
    try:
        top = weekly_top_articles(session, days=days, limit=limit)
        counts = category_counts(session, days=days)
    finally:
        if hasattr(session, "close"):
            session.close()

    if not top:
        return None

    html = [f"<h2>\U0001F30D GeoWatch Weekly Report \u2014 last {days} days</h2>"]
    html.append("<h3>Busiest categories</h3><ul>")
    for cat, n in sorted(counts.items(), key=lambda kv: -kv[1]):
        html.append(f"<li>{cat}: {n}</li>")
    html.append("</ul>")

    html.append(f"<h3>Top {len(top)} stories by score</h3><ul>")
    for a in top:
        title = a.get("title") or "Untitled"
        html.append(f"<li><a href='{a.get('url','')}'>{title}</a> "
                     f"\u2014 {a.get('category','')} (score {a.get('score',0)})</li>")
    html.append("</ul>")
    return "\n".join(html)


def run_weekly_report():
    if not getattr(C, "ENABLE_WEEKLY_REPORT", False):
        return False
    html = build_weekly_digest()
    if not html:
        return False
    return send_email(html, subject="\U0001F30D GeoWatch Weekly Report")


if __name__ == "__main__":
    ok = run_weekly_report()
    print("Weekly report sent" if ok else "Weekly report skipped (disabled or no data)")
