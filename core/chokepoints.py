"""Matches article text against the 13 global trade chokepoints (see
config/chokepoints.yaml). Lets the dashboard show which stories are
about a strategic waterway, and plots the chokepoints themselves as
fixed map markers alongside your dynamic source pins -- unlike sources,
these never move and don't need a `country` field guessed from a feed
name, so they're a firmer anchor for the map tab.

Ported (coordinates + names only, not routing/shock-model logic) from
worldmonitor's src/config/chokepoint-registry.ts (AGPL-3.0).
"""
import yaml
from core.config import CONFIG_DIR

_FILE = CONFIG_DIR / "chokepoints.yaml"
_data = yaml.safe_load(_FILE.read_text(encoding="utf-8")) if _FILE.exists() else {}
CHOKEPOINTS = _data.get("chokepoints", [])


def load_chokepoints():
    return CHOKEPOINTS


def match_chokepoints(text: str):
    """Return the list of chokepoint dicts mentioned in `text` (by name
    or alias, case-insensitive)."""
    lower = (text or "").lower()
    hits = []
    for cp in CHOKEPOINTS:
        names = [cp.get("name", "").lower()] + [a.lower() for a in cp.get("aliases", [])]
        if any(n and n in lower for n in names):
            hits.append(cp)
    return hits
