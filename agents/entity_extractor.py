"""
IntelliMandate v3 — Entity Extractor
File: agents/entity_extractor.py

June 15 Member B Task B-2-3
Uses spaCy NER + regex for MONEY, DATE, ORG, and CLAUSE extraction.
No LLMs, no remote APIs.

Run:
    python -m agents.entity_extractor
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

try:
    import spacy
except Exception:  # pragma: no cover
    spacy = None


CLAUSE_PATTERN = re.compile(r"\b(Clause|Section|Paragraph|Para|Rule)\s+[\d]+[\w()./-]*", re.I)
MONEY_PATTERN = re.compile(
    r"(?:(?:₹|rs\.?|inr)\s*)?([0-9]+(?:\.[0-9]+)?)\s*(crore|cr|lakh|lac|lakhs|lacs|million|thousand|rupees?)?",
    re.I,
)
RELATIVE_DEADLINE_PATTERN = re.compile(
    r"\bwithin\s+([0-9]+)\s+(day|days|week|weeks|month|months)\b",
    re.I,
)
ABSOLUTE_DATE_PATTERN = re.compile(
    r"\b(?:on\s+or\s+before\s+|by\s+)?"
    r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
    re.I,
)
NUMERIC_DATE_PATTERN = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b")

ORG_NORMALIZATION = {
    "reserve bank of india": "RBI",
    "rbi": "RBI",
    "fiu-ind": "FIU_IND",
    "fiu ind": "FIU_IND",
    "financial intelligence unit": "FIU_IND",
    "sebi": "SEBI",
    "securities and exchange board of india": "SEBI",
    "irdai": "IRDAI",
    "insurance regulatory and development authority of india": "IRDAI",
    "mca": "MCA",
    "ministry of corporate affairs": "MCA",
    "canara bank": "CANARA_BANK",
}


def _load_nlp():
    if spacy is None:
        return None
    for model_name in ("en_core_web_trf", "en_core_web_sm"):
        try:
            return spacy.load(model_name)
        except Exception:
            continue
    nlp = spacy.blank("en")
    if "sentencizer" not in nlp.pipe_names:
        nlp.add_pipe("sentencizer")
    return nlp


_NLP = None


def get_nlp():
    global _NLP
    if _NLP is None:
        _NLP = _load_nlp()
    return _NLP


def parse_money_to_rupees(text: str) -> float:
    """Convert money text such as '41.8 lakh' or '₹1.63 crore' to rupee float."""
    if not text:
        return 0.0

    # Prefer explicit currency/scale phrases to avoid accidental clause numbers.
    matches = []
    for match in MONEY_PATTERN.finditer(text):
        full = match.group(0).strip()
        number = match.group(1)
        unit = (match.group(2) or "").lower()
        full_lower = full.lower()

        # Avoid false positives like '24 hours'. Bare numbers are money only when the
        # matched phrase itself carries a currency marker. Do not inspect surrounding
        # words because words like 'Branches' contain 'rs'.
        if not unit and not any(marker in full_lower for marker in ("₹", "rs", "inr", "rupee")):
            continue
        if not number:
            continue
        matches.append((float(number), unit, full))

    if not matches:
        return 0.0

    # Return the largest money value in the sentence.
    values = []
    for amount, unit, _full in matches:
        if unit in {"crore", "cr"}:
            values.append(amount * 10_000_000)
        elif unit in {"lakh", "lac", "lakhs", "lacs"}:
            values.append(amount * 100_000)
        elif unit == "million":
            values.append(amount * 1_000_000)
        elif unit == "thousand":
            values.append(amount * 1_000)
        else:
            values.append(amount)
    return float(max(values))


def extract_money_phrases(text: str) -> List[str]:
    phrases = []
    for match in MONEY_PATTERN.finditer(text or ""):
        full = match.group(0).strip()
        unit = (match.group(2) or "").lower()
        full_lower = full.lower()
        if unit or any(marker in full_lower for marker in ("₹", "rs", "inr", "rupee")):
            phrases.append(full)
    return phrases


def _parse_absolute_date(date_text: str) -> Optional[date]:
    from datetime import datetime

    cleaned = re.sub(r",", "", date_text.strip())
    for fmt in ("%B %d %Y", "%d %m %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except Exception:
            continue
    return None


def extract_dates(sentence: str, reference_date: Optional[date] = None) -> List[Dict[str, Any]]:
    reference_date = reference_date or date.today()
    results: List[Dict[str, Any]] = []

    for match in ABSOLUTE_DATE_PATTERN.finditer(sentence or ""):
        parsed = _parse_absolute_date(match.group(1))
        results.append({"text": match.group(1), "type": "absolute", "date": parsed.isoformat() if parsed else None})

    for match in NUMERIC_DATE_PATTERN.finditer(sentence or ""):
        d, m, y = match.groups()
        y = int(y)
        if y < 100:
            y += 2000
        try:
            parsed = date(y, int(m), int(d))
        except ValueError:
            try:
                parsed = date(y, int(d), int(m))
            except ValueError:
                parsed = None
        results.append({"text": match.group(0), "type": "absolute", "date": parsed.isoformat() if parsed else None})

    for match in RELATIVE_DEADLINE_PATTERN.finditer(sentence or ""):
        number = int(match.group(1))
        unit = match.group(2).lower()
        days = number
        if unit.startswith("week"):
            days = number * 7
        elif unit.startswith("month"):
            days = number * 30
        computed = reference_date + timedelta(days=days)
        results.append(
            {
                "text": match.group(0),
                "type": "relative",
                "days": days,
                "date": computed.isoformat(),
            }
        )
    return results


def extract_orgs(sentence: str) -> List[str]:
    found = set()
    lower = (sentence or "").lower()
    for phrase, normalized in ORG_NORMALIZATION.items():
        if phrase in lower:
            found.add(normalized)

    nlp = get_nlp()
    if nlp is not None:
        try:
            doc = nlp(sentence or "")
            for ent in doc.ents:
                if ent.label_ in {"ORG", "GPE"}:
                    normalized = ORG_NORMALIZATION.get(ent.text.lower(), ent.text.upper().replace(" ", "_"))
                    found.add(normalized)
        except Exception:
            pass
    return sorted(found)


def extract_entities(sentence: str) -> Dict[str, Any]:
    """
    Main function required by v3 plan:
        extract_entities(sentence: str) -> dict
    """
    clauses = [match.group(0) for match in CLAUSE_PATTERN.finditer(sentence or "")]
    dates = extract_dates(sentence)
    return {
        "money": parse_money_to_rupees(sentence),
        "money_phrases": extract_money_phrases(sentence),
        "dates": dates,
        "orgs": extract_orgs(sentence),
        "clauses": clauses,
    }


if __name__ == "__main__":
    samples = [
        "Canara Bank shall rectify rejected CKYCR uploads within 7 days under Clause 38(ii) and penalty exposure of ₹41.8 lakh.",
        "Priority sector lending shortfall may attract ₹1.63 crore under Paragraph 4.3 by September 30, 2026.",
        "Rs.32 lakh penalty applies where banks fail to upload corrected CIC data within 7 days.",
        "AML reporting under Section 47A must be completed for FIU-IND and RBI monitoring; penalty may be 2 crore.",
        "Branches must display updated deposit interest rates within 24 hours of rate revision.",
    ]
    for sample in samples:
        print("\nSentence:", sample)
        print(extract_entities(sample))
