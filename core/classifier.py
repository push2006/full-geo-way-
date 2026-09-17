"""Merged classifier logic from GeoNews + BRICS."""
import re

_TAG_RE = re.compile(r"<[^>]+>")
_ENTITY_MAP = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&quot;": '"', "&#39;": "'", "&#8230;": "...", "&hellip;": "...",
}

def strip_html(text: str) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    for entity, replacement in _ENTITY_MAP.items():
        text = text.replace(entity, replacement)
    return re.sub(r"\s+", " ", text).strip()


# GeoNews rules + BRICS keywords merged
RULES = {
    "GEOPOLITICS": [
        "geopolit", "diplomatic", "foreign policy", "war", "conflict", "ceasefire",
        "military", "alliance", "border", "nato", "brics", "sco", "summit",
        "diplomat", "bilateral", "foreign minister", "president", "prime minister",
    ],
    "TRADE": [
        "tariff", "trade war", "trade agreement", "export control", "import restriction",
        "customs", "supply chain", "critical mineral", "semiconductor", "trade dispute",
        "fta", "trade policy", "import ban", "export ban", "trade deal", "currency",
        "export", "import",
    ],
    "SANCTIONS": [
        "sanction", "embargo", "asset freeze", "designated entity", "secondary sanctions",
        "ofac", "denied party", "blacklist", "restricted", "financial restriction",
    ],
    "RISK": [
        "risk", "escalation", "crisis", "instability", "shortage", "disruption",
        "shock", "volatility", "chokepoint", "attack", "explosion", "unrest", "coup",
    ],
    "CONFERENCE": [
        "summit", "conference", "forum", "ministerial", "assembly", "meeting",
        "g20", "brics", "sco", "wto", "imf", "world bank", "declaration",
    ],
    "RESEARCH": [
        "working paper", "research paper", "policy brief", "preprint", "white paper",
        "arxiv", "ssrn", "nber", "peer-reviewed", "journal article",
    ],
}

HIGH_IMPACT = [
    "breaking", "new sanctions", "sanctions package", "invasion", "ceasefire",
    "tariff", "export ban", "trade war", "nuclear", "military operation", "emergency",
]

STRONG_BRICS = [
    "brics", "new delhi declaration", "bharat mandapam", "18th brics",
    "brics summit", "brics nations", "brics countries", "brics leaders",
]
LEADER_NAMES = [
    "modi", "putin", "xi jinping", "ramaphosa", "lula", "abiy ahmed",
    "prabowo", "pezeshkian", "el-sisi", "al nahyan", "faisal al saud",
]
DIPLOMATIC_TERMS = [
    "summit", "bilateral meeting", "bilateral talks", "joint statement",
    "multilateral", "state visit", "delegation", "foreign minister meeting",
    "trade agreement", "trade deal", "de-dollarization", "currency pact",
    "diplomatic", "sanctions", "new delhi", "declaration",
]


def classify(title: str = "", summary: str = "") -> str:
    text = f"{title} {summary}".lower()
    scores = {}
    for cat, words in RULES.items():
        scores[cat] = sum(1 for w in words if w in text)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "GENERAL"
    return best


def is_critical(title: str = "", summary: str = "") -> bool:
    text = f"{title} {summary}".lower()
    return any(k in text for k in HIGH_IMPACT)


def is_brics_relevant(title: str = "", summary: str = "") -> bool:
    text = f"{title} {summary}".lower()
    if any(kw in text for kw in STRONG_BRICS):
        return True
    has_leader = any(kw in text for kw in LEADER_NAMES)
    has_diplo = any(kw in text for kw in DIPLOMATIC_TERMS)
    return has_leader and has_diplo


def risk_score(title: str = "", summary: str = "") -> int:
    text = f"{title} {summary}".lower()
    score = 0
    for w in HIGH_IMPACT:
        if w in text:
            score += 10
    for w in RULES.get("RISK", []):
        if w in text:
            score += 3
    for w in RULES.get("SANCTIONS", []):
        if w in text:
            score += 5
    return min(100, score)
