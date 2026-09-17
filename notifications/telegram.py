"""Telegram delivery via the official Bot API.
OFF unless ENABLE_TELEGRAM=true in .env.

Setup: message @BotFather -> /newbot -> copy the token, add the bot to
your channel/chat, then get the chat id from
https://api.telegram.org/bot<token>/getUpdates
"""
import requests
from core import config as C


def send(articles, limit=10):
    if not getattr(C, "ENABLE_TELEGRAM", False) or not articles:
        return False
    lines = [f"\U0001F30D *GeoWatch*: {len(articles)} new items"]
    for a in articles[:limit]:
        title = a.get("title") or a.get("name") or "Untitled"
        url = a.get("url", "")
        source = a.get("platform") or a.get("source") or ""
        lines.append(f"\u2022 [{title}]({url}) \u2014 {source}")
    text = "\n".join(lines)
    api = f"https://api.telegram.org/bot{C.TELEGRAM_BOT_TOKEN}/sendMessage"
    resp = requests.post(api, data={
        "chat_id": C.TELEGRAM_CHAT_ID, "text": text,
        "parse_mode": "Markdown", "disable_web_page_preview": True,
    }, timeout=15)
    return resp.status_code == 200
