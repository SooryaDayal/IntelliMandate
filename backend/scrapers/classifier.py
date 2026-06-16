"""
Document Classifier
File: backend/scrapers/classifier.py

Classifies every RBI circular into one of five signal types
using spaCy rule-based pattern matching on title and text content.

Signal Types:
    MANDATORY_IMMEDIATE  → Master Directions, penalty clauses, immediate action required
    MANDATORY_FUTURE     → Policy changes with future deadlines
    CIRCULAR_AMENDMENT   → Updates or amendments to existing circulars
    CONSULTATION_PAPER   → Draft regulations, proposals open for feedback
    ADVISORY             → Guidance notes, clarifications, no penalty attached

Classification uses three layers in priority order:
    Layer 1 → Title pattern matching (fastest, most reliable)
    Layer 2 → Body text keyword scoring (weighted voting)
    Layer 3 → Default fallback → ADVISORY
"""

import re
import spacy
from typing import Optional

# Load spaCy English model
# Install: python -m spacy download en_core_web_sm
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise OSError(
        "spaCy model not found. Run: python -m spacy download en_core_web_sm"
    )


# ============================================================
# SIGNAL TYPE CONSTANTS
# ============================================================

MANDATORY_IMMEDIATE = "MANDATORY_IMMEDIATE"
MANDATORY_FUTURE    = "MANDATORY_FUTURE"
CIRCULAR_AMENDMENT  = "CIRCULAR_AMENDMENT"
CONSULTATION_PAPER  = "CONSULTATION_PAPER"
ADVISORY            = "ADVISORY"

ALL_SIGNAL_TYPES = [
    MANDATORY_IMMEDIATE,
    MANDATORY_FUTURE,
    CIRCULAR_AMENDMENT,
    CONSULTATION_PAPER,
    ADVISORY,
]


# ============================================================
# LAYER 1: TITLE PATTERN RULES
# Order matters — first match wins
# More specific patterns come before general ones
# ============================================================

TITLE_PATTERNS = [

    # CONSULTATION_PAPER — must check before MANDATORY patterns
    # because drafts can contain "shall" and "must" in proposed text
    {
        "signal_type": CONSULTATION_PAPER,
        "patterns": [
            r"\bdraft\b",
            r"\bconsultation paper\b",
            r"\bdiscussion paper\b",
            r"\bexposure draft\b",
            r"\bproposed\b.*\bregulation",
            r"\bcomments? invited\b",
            r"\bfeedback\b.*\bsought\b",
            r"\bstakeholder\b.*\bconsult",
        ],
    },

    # CIRCULAR_AMENDMENT — updates to existing instructions
    {
        "signal_type": CIRCULAR_AMENDMENT,
        "patterns": [
            r"\bamendment\b",
            r"\bamended\b",
            r"\bmodification\b",
            r"\bmodified\b",
            r"\brevision\b",
            r"\brevised\b",
            r"\bupdated?\b.*\binstructions?\b",
            r"\bconsolidation of instructions\b",
            r"\brescinded?\b",
            r"\bwithdrawn?\b.*\bcircular\b",
            r"\bsupersed",
        ],
    },

    # MANDATORY_IMMEDIATE — master directions, immediate compliance
    {
        "signal_type": MANDATORY_IMMEDIATE,
        "patterns": [
            r"\bmaster direction",
            r"\bmaster circular",
            r"\bdirections?,?\s+\d{4}\b",
            r"\bpenalt",
            r"\bpenalties\b",
            r"\bfine\b.*\bimposed\b",
            r"\bimmediate\b.*\beffect\b",
            r"\bwith\b.*\bimmediate\b.*\beffect\b",
            r"\bcomply\b.*\bforthwith\b",
            r"\bsection\s+\d+.*\bact\b",
        ],
    },

    # MANDATORY_FUTURE — compliance required by a future date
    {
        "signal_type": MANDATORY_FUTURE,
        "patterns": [
            r"\bwith\s+effect\s+from\b",
            r"\beffective\s+(from|date)\b",
            r"\bby\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b",
            r"\bdeadline\b",
            r"\bcomply\b.*\bby\b",
            r"\bimplemented?\b.*\bby\b",
        ],
    },

    # ADVISORY — guidance, clarification, consolidation
    {
        "signal_type": ADVISORY,
        "patterns": [
            r"\bguidance\b",
            r"\bguidelines?\b",
            r"\bclarification\b",
            r"\bfrequently\s+asked\b",
            r"\bfaq\b",
            r"\bawareness\b",
            r"\badvisory\b",
            r"\bcaution\b",
        ],
    },
]


# ============================================================
# LAYER 2: BODY TEXT KEYWORD SCORING
# Each keyword contributes a weighted vote to a signal type
# Signal type with highest total score wins
# ============================================================

BODY_KEYWORDS = {

    MANDATORY_IMMEDIATE: [
        ("shall comply",            10),
        ("must comply",             10),
        ("shall be complied",       10),
        ("penalty",                 8),
        ("penalties",               8),
        ("immediate effect",        9),
        ("forthwith",               9),
        ("master direction",        10),
        ("master circular",         10),
        ("impose fine",             8),
        ("non-compliance",          7),
        ("violation",               6),
        ("section 47a",             9),   # RBI Act penalty section
        ("section 46",              9),
        ("prosecuted",              8),
        ("shall",                   2),   # low weight — common in all docs
        ("must",                    2),
    ],

    MANDATORY_FUTURE: [
        ("with effect from",        9),
        ("effective from",          9),
        ("by march 31",             8),
        ("by june 30",              8),
        ("by september 30",         8),
        ("by december 31",          8),
        ("shall be implemented",    8),
        ("shall be complied with",  8),
        ("within",                  3),
        ("deadline",                7),
        ("target date",             7),
        ("not later than",          8),
        ("on or before",            7),
    ],

    CIRCULAR_AMENDMENT: [
        ("amendment",               9),
        ("hereby amended",          10),
        ("stands amended",          10),
        ("modified",                7),
        ("revised",                 7),
        ("supersedes",              9),
        ("in partial modification", 10),
        ("in modification of",      10),
        ("consolidated",            6),
        ("rescinded",               9),
        ("withdrawn",               7),
        ("substituted",             8),
        ("paragraph",               2),   # often used in amendments
    ],

    CONSULTATION_PAPER: [
        ("draft",                   9),
        ("proposed",                7),
        ("comments invited",        10),
        ("feedback",                7),
        ("suggestions",             6),
        ("stakeholders",            7),
        ("public consultation",     10),
        ("discussion paper",        10),
        ("exposure draft",          10),
        ("under consideration",     7),
        ("may be sent to",          9),   # typical in consultation papers
    ],

    ADVISORY: [
        ("guidance",                8),
        ("advised",                 5),
        ("it is clarified",         8),
        ("frequently asked",        9),
        ("for information",         6),
        ("for awareness",           8),
        ("caution",                 7),
        ("alert",                   6),
        ("be informed",             5),
        ("noted that",              3),
    ],
}


# ============================================================
# LAYER 1: CLASSIFY BY TITLE
# ============================================================

def classify_by_title(title: str) -> Optional[str]:
    """
    Checks title against regex patterns.
    Returns signal type on first match, or None if no match.
    """
    title_lower = title.lower()

    for rule in TITLE_PATTERNS:
        for pattern in rule["patterns"]:
            if re.search(pattern, title_lower):
                return rule["signal_type"]

    return None


# ============================================================
# LAYER 2: CLASSIFY BY BODY TEXT SCORING
# ============================================================

def classify_by_body(text: str) -> Optional[str]:
    """
    Scores body text against keyword lists.
    Returns signal type with highest score, or None if all scores are 0.
    """
    text_lower = text.lower()
    scores = {signal: 0 for signal in ALL_SIGNAL_TYPES}

    for signal_type, keyword_list in BODY_KEYWORDS.items():
        for keyword, weight in keyword_list:
            # Count occurrences — more mentions = stronger signal
            count = text_lower.count(keyword.lower())
            if count > 0:
                # Cap at 3 occurrences to prevent single keyword dominating
                scores[signal_type] += weight * min(count, 3)

    # Only return a result if at least one signal scored above threshold
    best_signal = max(scores, key=lambda s: scores[s])
    best_score  = scores[best_signal]

    if best_score < 5:
        return None

    return best_signal


# ============================================================
# MAIN CLASSIFIER
# ============================================================

def classify_circular(
    title: str,
    text: Optional[str] = None,
    ref_number: Optional[str] = None
) -> dict:
    """
    Main classification function.
    Takes a circular's title, body text, and reference number.
    Returns a classification result dict.

    Args:
        title:      Circular subject/title
        text:       Full extracted text (from PDF or HTML). Optional.
        ref_number: Circular reference number. Used as additional signal.

    Returns:
        {
            "signal_type":  str   — one of the five signal types
            "confidence":   str   — HIGH / MEDIUM / LOW
            "method":       str   — TITLE / BODY / TITLE+BODY / DEFAULT
            "scores":       dict  — body keyword scores (if text provided)
            "reason":       str   — human-readable explanation
        }
    """
    title      = title or ""
    text       = text  or ""
    ref_number = ref_number or ""

    title_result = None
    body_result  = None
    scores       = {}

    # ── Layer 1: Title matching ──
    title_result = classify_by_title(title)

    # ── Also check ref_number for "master direction" patterns ──
    if not title_result and ref_number:
        ref_lower = ref_number.lower()
        if "master" in ref_lower or "dor" in ref_lower:
            title_result = MANDATORY_IMMEDIATE
        elif "fmod" in ref_lower:
            # FMOD = Financial Markets Operations Department — usually mandatory
            title_result = MANDATORY_FUTURE

    # ── Layer 2: Body text scoring ──
    if text and len(text) > 50:
        body_result = classify_by_body(text)
        scores = {
            signal: sum(
                weight * min(text.lower().count(kw.lower()), 3)
                for kw, weight in kws
            )
            for signal, kws in BODY_KEYWORDS.items()
        }

    # ── Decision logic ──
    if title_result and body_result:
        if title_result == body_result:
            # Both agree — high confidence
            final  = title_result
            method = "TITLE+BODY"
            conf   = "HIGH"
            reason = f"Title pattern and body text both indicate {final}."
        else:
            # Title takes priority — it is the most direct signal
            # But confidence is medium since body disagrees
            final  = title_result
            method = "TITLE"
            conf   = "MEDIUM"
            reason = (
                f"Title indicates {title_result}, "
                f"body suggests {body_result}. "
                f"Title takes priority."
            )

    elif title_result:
        final  = title_result
        method = "TITLE"
        conf   = "HIGH" if title_result != ADVISORY else "MEDIUM"
        reason = f"Title pattern matched {final}."

    elif body_result:
        final  = body_result
        method = "BODY"
        conf   = "MEDIUM"
        reason = f"Body text scoring indicates {final}."

    else:
        # Default fallback
        final  = ADVISORY
        method = "DEFAULT"
        conf   = "LOW"
        reason = "No strong signals found. Defaulting to ADVISORY."

    return {
        "signal_type": final,
        "confidence":  conf,
        "method":      method,
        "scores":      scores,
        "reason":      reason,
    }


# ============================================================
# BATCH CLASSIFIER
# Classify a list of circular dicts from the RBI scraper
# ============================================================

def classify_circulars_batch(circulars: list[dict]) -> list[dict]:
    """
    Classifies a list of circular dicts.
    Adds 'signal_type', 'confidence', and 'classification_reason'
    keys to each dict.

    Args:
        circulars: List of dicts from fetch_rbi_circulars()
                   Each dict must have 'title' key.
                   'raw_text' and 'ref_number' are optional but improve accuracy.

    Returns:
        Same list with classification fields added.
    """
    results = []

    for circular in circulars:
        result = classify_circular(
            title      = circular.get("title", ""),
            text       = circular.get("raw_text", ""),
            ref_number = circular.get("ref_number", ""),
        )

        circular["signal_type"]            = result["signal_type"]
        circular["confidence"]             = result["confidence"]
        circular["classification_method"]  = result["method"]
        circular["classification_reason"]  = result["reason"]
        results.append(circular)

    return results


# ============================================================
# STANDALONE TEST
# Run: python -m backend.scrapers.classifier
# ============================================================

if __name__ == "__main__":
    from backend.scrapers.rbi_scraper    import fetch_rbi_circulars
    from backend.scrapers.pdf_extractor  import extract_circular_text

    print("Fetching RBI circulars...")
    circulars = fetch_rbi_circulars(max_circulars=5)

    if not circulars:
        print("No circulars fetched.")
        exit(1)

    print(f"\nClassifying {len(circulars)} circulars...\n")
    print("=" * 70)

    for i, circular in enumerate(circulars, 1):
        # Extract full text for better classification accuracy
        print(f"[{i}] Extracting text for: {circular['title'][:50]}...")
        circular["raw_text"] = extract_circular_text(circular) or ""

        result = classify_circular(
            title      = circular["title"],
            text       = circular["raw_text"],
            ref_number = circular["ref_number"],
        )

        print(f"\n[{i}] {circular['title'][:65]}")
        print(f"     Signal Type : {result['signal_type']}")
        print(f"     Confidence  : {result['confidence']}")
        print(f"     Method      : {result['method']}")
        print(f"     Reason      : {result['reason']}")
        print("-" * 70)