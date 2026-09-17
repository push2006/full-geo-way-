"""Email digest delivery. OFF unless ENABLE_EMAIL=true in .env."""
import smtplib
import datetime
from html import escape
from urllib.parse import urlparse
from email.mime.text import MIMEText
from core import config as C


def build_digest(articles):
    if not articles:
        return None
    by_cat = {}
    for a in articles:
        by_cat.setdefault(a.get("category", "general"), []).append(a)

    date_str = datetime.date.today().strftime("%d %b %Y")
    html = [f"<h2>\U0001F30D GeoWatch Digest \u2014 {date_str}</h2>",
            f"<p>{len(articles)} items across {len(by_cat)} categories</p>"]
    for cat, items in by_cat.items():
        html.append(f"<h3>{cat}</h3><ul>")
        for a in items:
            title = a.get("title") or a.get("name") or "Untitled"
            source = a.get("platform") or a.get("source") or ""
            html.append(f"<li><a href='{a.get('url','')}'>{title}</a> \u2014 {source}</li>")
        html.append("</ul>")
    return "\n".join(html)


def send(html, subject=None):
    if not getattr(C, "ENABLE_EMAIL", False) or not html:
        return False
    subject = subject or f"\U0001F30D GeoWatch Digest \u2014 {datetime.date.today().strftime('%d %b %Y')}"
    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = C.EMAIL_FROM
    msg["To"] = C.EMAIL_TO

    # Fix carried over from BRICS: strip whitespace and drop empty entries
    # so "a@x.com, b@x.com" doesn't send a literal leading-space address.
    recipients = [addr.strip() for addr in C.EMAIL_TO.split(",") if addr.strip()]

    with smtplib.SMTP(C.SMTP_HOST, C.SMTP_PORT) as server:
        server.starttls()
        server.login(C.EMAIL_FROM, C.EMAIL_APP_PASSWORD)
        server.sendmail(C.EMAIL_FROM, recipients, msg.as_string())
    return True
