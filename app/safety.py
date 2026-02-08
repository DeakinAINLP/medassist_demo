import re
from typing import List, Tuple, Literal

Triage = Literal["emergency", "urgent", "soon", "routine"]

# NOTE: This is a demo. For real use, apply medically-reviewed triage logic.
EMERGENCY_PATTERNS = [
    r"\b(chest pain|pressure in chest|crushing chest)\b",
    r"\b(short(ness)? of breath|can't breathe|difficulty breathing)\b",
    r"\b(stroke|face droop|arm weakness|slurred speech)\b",
    r"\b(seizure|convulsion)\b",
    r"\b(passed out|faint(ed)?|unconscious)\b",
    r"\b(severe bleeding|bleeding won't stop)\b",
    r"\b(suicid(al)?|kill myself|self-harm)\b",
    r"\b(anaphylaxis|throat closing|swelling of (lips|tongue)|hives with breathing)\b",
    r"\b(severe allergic)\b",
]
URGENT_PATTERNS = [
    r"\b(high fever|fever over)\b",
    r"\b(severe pain|worst pain)\b",
    r"\b(vomiting blood|blood in vomit)\b",
    r"\b(blood in stool|black tarry stools)\b",
    r"\b(severe dehydration|not urinating)\b",
    r"\b(pregnan(t|cy).*(bleeding|severe pain))\b",
]

def classify_urgency_rule_based(text: str) -> Tuple[Triage, List[str]]:
    """
    Very lightweight screen. Returns (triage_level, triggered_patterns).
    """
    if not text:
        return "routine", []
    t = text.lower()

    triggered = []
    for p in EMERGENCY_PATTERNS:
        if re.search(p, t, re.IGNORECASE):
            triggered.append(p)
    if triggered:
        return "emergency", triggered

    for p in URGENT_PATTERNS:
        if re.search(p, t, re.IGNORECASE):
            triggered.append(p)
    if triggered:
        return "urgent", triggered

    # If severe duration or rapid worsening hints, bump
    if re.search(r"\b(worsening rapidly|getting much worse|sudden onset)\b", t):
        return "soon", ["worsening_heuristic"]

    return "routine", []


# Extremely naive PII redaction for demo purposes only.
_EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
_PHONE_RE = re.compile(r"\b(\+?\d[\d\s\-]{7,}\d)\b")
_ADDRESS_RE = re.compile(r"\b(\d{1,5}\s+\w+(\s+\w+){1,5}\s+(st|street|rd|road|ave|avenue|blvd|boulevard|dr|drive|ln|lane|ct|court)\b)", re.IGNORECASE)

def redact_pii_basic(text: str) -> str:
    if not text:
        return text
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _ADDRESS_RE.sub("[REDACTED_ADDRESS]", text)
    return text
