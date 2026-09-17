"""WhatsApp delivery via the free CallMeBot API.
OFF unless ENABLE_WHATSAPP=true in .env.

Setup: message +34 644 71 79 92 on WhatsApp with the text
'I allow callmebot to send me messages', then use the apikey it replies
with as WHATSAPP_APIKEY.
"""
import requests
from core import config as C


def send(articles, limit=10):
    if not getattr(C, "ENABLE_WHATSAPP", False) or not articles:
        return False
    lines = [f"GeoWatch: {len(articles)} new items"]
    for a in articles[:limit]:
        title = a.get("title") or a.get("name") or "Untitled"
        source = a.get("platform") or a.get("source") or ""
        lines.append(f"- {title} ({source})")
    text = "\n".join(lines)
    resp = requests.get(
        "https://api.callmebot.com/whatsapp.php",
        params={"phone": C.WHATSAPP_PHONE, "text": text, "apikey": C.WHATSAPP_APIKEY},
        timeout=15,
    )
    return resp.status_code == 200
