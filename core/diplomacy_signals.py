"""Diplomatic-signal detector — ported from worldmonitor's
shared/diplomacy-keywords.json (github.com/koala73/worldmonitor,
AGPL-3.0). Flags headlines that pair a flashpoint country/actor with
diplomacy language ("Iran talks", "Gaza ceasefire") -- useful as a
separate, lower-urgency signal from threat_classifier's critical alerts:
this catches de-escalation news, not escalation.
"""
import json
from pathlib import Path
from core.config import CONFIG_DIR

_KEYWORDS_FILE = CONFIG_DIR / "diplomacy-keywords.json"
_data = json.loads(_KEYWORDS_FILE.read_text(encoding="utf-8")) if _KEYWORDS_FILE.exists() else {}

DIPLOMACY_KEYWORDS = _data.get("diplomacyKeywords", [])
FLASHPOINT_KEYWORDS = _data.get("flashpointKeywords", [])
DIPLOMACY_FLASHPOINT_PAIRS = [tuple(p) for p in _data.get("diplomacyFlashpointPairs", [])]


def is_diplomatic_signal(title: str) -> bool:
    """True if the headline pairs a known flashpoint with diplomacy
    language -- either an explicit listed pair, or a flashpoint word
    plus any general diplomacy word appearing together."""
    lower = (title or "").lower()

    for flashpoint, diplo_word in DIPLOMACY_FLASHPOINT_PAIRS:
        if flashpoint in lower and diplo_word in lower:
            return True

    has_flashpoint = any(fp in lower for fp in FLASHPOINT_KEYWORDS)
    has_diplomacy = any(dw in lower for dw in DIPLOMACY_KEYWORDS)
    return has_flashpoint and has_diplomacy
