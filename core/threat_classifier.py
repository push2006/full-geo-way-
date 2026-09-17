"""Tiered keyword threat classifier — ported from worldmonitor's
`shared/threat-keyword-classifier.ts` (github.com/koala73/worldmonitor,
AGPL-3.0). Their headline-classifier logic is more thorough than a plain
substring match: tiered severity, word-boundary regex on ambiguous short
words, an exclusion list for false positives ("strikes a deal" is not a
military strike), and "compound escalation" (a military-action verb next
to a flashpoint country name bumps HIGH to CRITICAL even when the two
words aren't adjacent).

Ported by hand, faithfully — same keyword tables, same tiers, same
regex-boundary rules, same escalation logic — just Python instead of
TypeScript. Not a rewrite-from-scratch; a translation.
"""
import re
from typing import Literal, TypedDict

ThreatLevel = Literal["critical", "high", "medium", "low", "info"]
EventCategory = Literal[
    "conflict", "protest", "disaster", "diplomatic", "economic",
    "terrorism", "cyber", "health", "environmental", "military",
    "crime", "infrastructure", "tech", "general",
]


class ThreatClassification(TypedDict):
    level: ThreatLevel
    category: EventCategory
    confidence: float
    source: str


CRITICAL_KEYWORDS = {
    "nuclear strike": "military", "nuclear attack": "military", "nuclear war": "military",
    "invasion": "conflict", "declaration of war": "conflict", "declares war": "conflict",
    "all-out war": "conflict", "full-scale war": "conflict", "martial law": "military",
    "coup": "military", "coup attempt": "military", "genocide": "conflict",
    "ethnic cleansing": "conflict", "chemical attack": "terrorism", "biological attack": "terrorism",
    "dirty bomb": "terrorism", "mass casualty": "conflict", "massive strikes": "military",
    "military strikes": "military", "retaliatory strikes": "military", "launches strikes": "military",
    "launch attacks on iran": "military", "launch attack on iran": "military",
    "attacks on iran": "military", "strikes on iran": "military", "strikes iran": "military",
    "bombs iran": "military", "attacks iran": "military", "attack on iran": "military",
    "attack iran": "military", "attacked iran": "military", "attack against iran": "military",
    "bombing iran": "military", "bombed iran": "military", "war with iran": "conflict",
    "war on iran": "conflict", "war against iran": "conflict", "iran retaliates": "military",
    "iran strikes": "military", "iran launches": "military", "iran attacks": "military",
    "pandemic declared": "health", "health emergency": "health", "nato article 5": "military",
    "evacuation order": "disaster", "meltdown": "disaster", "nuclear meltdown": "disaster",
    "major combat operations": "military", "declared war": "conflict",
}

HIGH_KEYWORDS = {
    "war": "conflict", "armed conflict": "conflict", "airstrike": "conflict",
    "airstrikes": "conflict", "air strike": "conflict", "air strikes": "conflict",
    "drone strike": "conflict", "drone strikes": "conflict", "strikes": "conflict",
    "missile": "military", "missile launch": "military", "missiles fired": "military",
    "troops deployed": "military", "military escalation": "military", "military operation": "military",
    "ground offensive": "military", "bombing": "conflict", "bombardment": "conflict",
    "shelling": "conflict", "casualties": "conflict", "killed in": "conflict",
    "hostage": "terrorism", "terrorist": "terrorism", "terror attack": "terrorism",
    "assassination": "crime", "cyber attack": "cyber", "ransomware": "cyber",
    "data breach": "cyber", "sanctions": "economic", "embargo": "economic",
    "earthquake": "disaster", "tsunami": "disaster", "hurricane": "disaster", "typhoon": "disaster",
    "strike on": "conflict", "strikes on": "conflict", "attack on": "conflict",
    "attack against": "conflict", "attacks on": "conflict", "launched attack": "conflict",
    "launched attacks": "conflict", "launches attack": "conflict", "launches attacks": "conflict",
    "explosions": "conflict", "military operations": "military", "combat operations": "military",
    "retaliatory strike": "military", "retaliatory attack": "military", "retaliatory attacks": "military",
    "preemptive strike": "military", "preemptive attack": "military", "preventive attack": "military",
    "preventative attack": "military", "military offensive": "military", "ballistic missile": "military",
    "cruise missile": "military", "air defense intercepted": "military", "forces struck": "conflict",
}

MEDIUM_KEYWORDS = {
    "protest": "protest", "protests": "protest", "riot": "protest", "riots": "protest",
    "unrest": "protest", "demonstration": "protest", "strike action": "protest",
    "military exercise": "military", "naval exercise": "military", "arms deal": "military",
    "weapons sale": "military", "diplomatic crisis": "diplomatic", "ambassador recalled": "diplomatic",
    "expel diplomats": "diplomatic", "trade war": "economic", "tariff": "economic",
    "recession": "economic", "inflation": "economic", "market crash": "economic",
    "flood": "disaster", "flooding": "disaster", "wildfire": "disaster", "volcano": "disaster",
    "eruption": "disaster", "outbreak": "health", "epidemic": "health", "infection spread": "health",
    "oil spill": "environmental", "pipeline explosion": "infrastructure", "blackout": "infrastructure",
    "power outage": "infrastructure", "internet outage": "infrastructure", "derailment": "infrastructure",
}

LOW_KEYWORDS = {
    "election": "diplomatic", "vote": "diplomatic", "referendum": "diplomatic", "summit": "diplomatic",
    "treaty": "diplomatic", "agreement": "diplomatic", "negotiation": "diplomatic", "talks": "diplomatic",
    "peacekeeping": "diplomatic", "humanitarian aid": "diplomatic", "ceasefire": "diplomatic",
    "peace treaty": "diplomatic", "climate change": "environmental", "emissions": "environmental",
    "pollution": "environmental", "deforestation": "environmental", "drought": "environmental",
    "vaccine": "health", "vaccination": "health", "disease": "health", "virus": "health",
    "public health": "health", "covid": "health", "interest rate": "economic", "gdp": "economic",
    "unemployment": "economic", "regulation": "economic",
}

TECH_HIGH_KEYWORDS = {
    "major outage": "infrastructure", "service down": "infrastructure", "global outage": "infrastructure",
    "zero-day": "cyber", "critical vulnerability": "cyber", "supply chain attack": "cyber",
    "mass layoff": "economic",
}

TECH_MEDIUM_KEYWORDS = {
    "outage": "infrastructure", "breach": "cyber", "hack": "cyber", "vulnerability": "cyber",
    "layoff": "economic", "layoffs": "economic", "antitrust": "economic", "monopoly": "economic",
    "ban": "economic", "shutdown": "infrastructure",
}

TECH_LOW_KEYWORDS = {
    "ipo": "economic", "funding": "economic", "acquisition": "economic", "merger": "economic",
    "launch": "tech", "release": "tech", "update": "tech", "partnership": "economic",
    "startup": "tech", "ai model": "tech", "open source": "tech",
}

EXCLUSIONS = [
    "protein", "couples", "relationship", "dating", "diet", "fitness",
    "recipe", "cooking", "shopping", "fashion", "celebrity", "movie",
    "tv show", "sports", "game", "concert", "festival", "wedding",
    "vacation", "travel tips", "life hack", "self-care", "wellness",
    "strikes deal", "strikes agreement", "strikes partnership",
]

SHORT_KEYWORDS = {
    "war", "coup", "ban", "vote", "riot", "riots", "hack", "talks", "ipo", "gdp",
    "virus", "disease", "flood", "strikes",
}

TRAILING_BOUNDARY_KEYWORDS = {
    "attack iran", "attacked iran", "attack on iran", "attack against iran",
    "attacks on iran", "launch attacks on iran", "launch attack on iran",
    "bombing iran", "bombed iran", "strikes iran", "attacks iran",
    "bombs iran", "war on iran", "war with iran", "war against iran",
    "iran retaliates", "iran strikes", "iran launches", "iran attacks",
}

_regex_cache: dict = {}


def _get_keyword_regex(kw: str) -> re.Pattern:
    if kw in _regex_cache:
        return _regex_cache[kw]
    escaped = re.escape(kw)
    if kw in SHORT_KEYWORDS:
        pattern = rf"\b{escaped}\b"
    elif kw in TRAILING_BOUNDARY_KEYWORDS:
        pattern = rf"{escaped}(?![\w-])"
    else:
        pattern = escaped
    compiled = re.compile(pattern)
    _regex_cache[kw] = compiled
    return compiled


def _match_keywords(title_lower: str, keywords: dict):
    for kw, cat in keywords.items():
        if _get_keyword_regex(kw).search(title_lower):
            return kw, cat
    return None


_ESCALATION_ACTIONS = re.compile(
    r"\b(attack|attacks|attacked|strike|strikes|struck|bomb|bombs|bombed|bombing|"
    r"shell|shelled|shelling|missile|missiles|intercept|intercepted|retaliates|"
    r"retaliating|retaliation|killed|casualties|offensive|invaded|invades)\b"
)
_ESCALATION_TARGETS = re.compile(
    r"\b(iran|tehran|isfahan|tabriz|russia|moscow|china|beijing|taiwan|taipei|"
    r"north korea|pyongyang|nato|us base|us forces|american forces|us military)\b"
)


def _should_escalate_to_critical(lower: str, match_cat: str) -> bool:
    if match_cat not in ("conflict", "military"):
        return False
    return bool(_ESCALATION_ACTIONS.search(lower)) and bool(_ESCALATION_TARGETS.search(lower))


def classify_by_keyword(title: str, variant: str = "full") -> ThreatClassification:
    """Tiered classification of a headline. `variant='tech'` also checks
    the tech-specific keyword tables (outages, breaches, layoffs...)."""
    lower = (title or "").lower()

    if any(ex in lower for ex in EXCLUSIONS):
        return {"level": "info", "category": "general", "confidence": 0.3, "source": "keyword"}

    is_tech = variant == "tech"

    match = _match_keywords(lower, CRITICAL_KEYWORDS)
    if match:
        return {"level": "critical", "category": match[1], "confidence": 0.9, "source": "keyword"}

    match = _match_keywords(lower, HIGH_KEYWORDS)
    if match:
        if _should_escalate_to_critical(lower, match[1]):
            return {"level": "critical", "category": match[1], "confidence": 0.85, "source": "keyword"}
        return {"level": "high", "category": match[1], "confidence": 0.8, "source": "keyword"}

    if is_tech:
        match = _match_keywords(lower, TECH_HIGH_KEYWORDS)
        if match:
            return {"level": "high", "category": match[1], "confidence": 0.75, "source": "keyword"}

    match = _match_keywords(lower, MEDIUM_KEYWORDS)
    if match:
        return {"level": "medium", "category": match[1], "confidence": 0.7, "source": "keyword"}

    if is_tech:
        match = _match_keywords(lower, TECH_MEDIUM_KEYWORDS)
        if match:
            return {"level": "medium", "category": match[1], "confidence": 0.65, "source": "keyword"}

    match = _match_keywords(lower, LOW_KEYWORDS)
    if match:
        return {"level": "low", "category": match[1], "confidence": 0.6, "source": "keyword"}

    if is_tech:
        match = _match_keywords(lower, TECH_LOW_KEYWORDS)
        if match:
            return {"level": "low", "category": match[1], "confidence": 0.55, "source": "keyword"}

    return {"level": "info", "category": "general", "confidence": 0.3, "source": "keyword"}


def is_critical(title: str, summary: str = "", variant: str = "full") -> bool:
    """Drop-in for core.classifier.is_critical(), but tiered instead of
    a flat substring match. Treats 'critical' as critical; 'high' with
    escalation already folds into 'critical' inside classify_by_keyword."""
    text = f"{title} {summary}".strip()
    return classify_by_keyword(text, variant=variant)["level"] == "critical"
