"""Live video streams to embed on the dashboard (ported from BRICS--).
Loads config/streams.yaml and builds YouTube embed URLs. Accepts a
video_id as either a bare ID or a full YouTube URL in any common
format (watch?v=, youtu.be/, /live/, /embed/).
"""
import re
import threading
import yaml
from core.config import CONFIG_DIR

STREAMS_FILE = CONFIG_DIR / "streams.yaml"

# Two things (scheduler cycle + dashboard request) could read-modify-write
# this file at once; this lock serializes that within one process.
_STREAMS_LOCK = threading.Lock()

_URL_PATTERNS = [
    r"(?:youtube\.com/watch\?v=|youtube\.com/live/|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{6,})",
]


def extract_video_id(value):
    value = (value or "").strip()
    if not value:
        return ""
    for pattern in _URL_PATTERNS:
        m = re.search(pattern, value)
        if m:
            return m.group(1)
    return value


def _read_raw_streams():
    if not STREAMS_FILE.exists():
        return []
    with open(STREAMS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("streams", []) or []


def _enrich_stream(s):
    stype = s.get("type")
    if stype == "channel":
        channel_id = s.get("channel_id", "")
        if channel_id:
            s["embed_url"] = f"https://www.youtube.com/embed/live_stream?channel={channel_id}"
            s["watch_url"] = f"https://www.youtube.com/channel/{channel_id}/live"
    elif stype == "video":
        vid = extract_video_id(s.get("video_id", ""))
        s["video_id"] = vid
        if vid:
            s["embed_url"] = f"https://www.youtube.com/embed/{vid}"
            s["watch_url"] = f"https://www.youtube.com/watch?v={vid}"
    return s


def load_streams():
    streams = _read_raw_streams()
    for s in streams:
        _enrich_stream(s)
    return streams


_FILE_HEADER = """# Live video streams to embed on the dashboard.
# Paste any YouTube link format into video_id.
"""


def _write_raw_streams(streams):
    with open(STREAMS_FILE, "w", encoding="utf-8") as f:
        f.write(_FILE_HEADER)
        f.write("\n")
        yaml.safe_dump({"streams": streams}, f, sort_keys=False, allow_unicode=True)


def add_stream(name, country, link):
    name = (name or "").strip()
    country = (country or "Custom").strip() or "Custom"
    vid = extract_video_id(link)
    if not name:
        raise ValueError("Stream name is required.")
    if not vid:
        raise ValueError("Could not read a video ID from that link.")

    with _STREAMS_LOCK:
        streams = _read_raw_streams()
        if any(s.get("name", "").strip().lower() == name.lower() for s in streams):
            raise ValueError(f'A stream named "{name}" already exists.')
        new_stream = {"name": name, "country": country, "type": "video", "video_id": vid}
        streams.append(new_stream)
        _write_raw_streams(streams)
    return _enrich_stream(dict(new_stream))


def remove_stream(name):
    name = (name or "").strip().lower()
    with _STREAMS_LOCK:
        streams = _read_raw_streams()
        kept = [s for s in streams if s.get("name", "").strip().lower() != name]
        if len(kept) == len(streams):
            return False
        _write_raw_streams(kept)
    return True
