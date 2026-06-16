"""
IntelliMandate v3 — Obligation Extractor
File: agents/obligation_extractor.py

June 15 Member B Task B-2-1
Uses spaCy sentence/dependency parsing plus deterministic compliance patterns.
No LLMs, no remote APIs.

Run:
    python -m agents.obligation_extractor
"""

from __future__ import annotations

import re
from typing import List

try:
    import spacy
except Exception:  # pragma: no cover
    spacy = None


REGULATED_ENTITY_TERMS = {
    "bank",
    "banks",
    "regulated entity",
    "regulated entities",
    "re",
    "res",
    "nbfc",
    "nbfcs",
    "branch",
    "branches",
    "canara bank",
    "scheduled commercial bank",
    "scheduled commercial banks",
}

OBLIGATION_TERMS = {
    "shall",
    "must",
    "will",
    "required",
    "require",
    "obligated",
    "ensure",
    "submit",
    "comply",
    "maintain",
    "rectify",
    "upload",
    "report",
    "implement",
    "display",
    "publish",
}

SOFT_ADVISORY_TERMS = {
    "may",
    "advised",
    "encouraged",
    "recommended",
    "best practice",
    "should consider",
    "guidance",
}


def _load_nlp():
    """Load a spaCy model with graceful fallback for first-time setup issues."""
    if spacy is None:
        return None
    for model_name in ("en_core_web_trf", "en_core_web_sm"):
        try:
            return spacy.load(model_name)
        except Exception:
            continue
    # Fallback: sentence splitting only. This keeps tests usable even before model download.
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


def _regex_sentences(text: str) -> List[str]:
    """Basic fallback sentence splitter if spaCy is unavailable."""
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def _has_regulated_entity(sentence_lower: str) -> bool:
    return any(term in sentence_lower for term in REGULATED_ENTITY_TERMS)


def _has_obligation_term(sentence_lower: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", sentence_lower) for term in OBLIGATION_TERMS)


def _has_action_verb(doc_or_sentence) -> bool:
    """Use dependency/POS when available, otherwise fall back to keyword check."""
    if isinstance(doc_or_sentence, str):
        return _has_obligation_term(doc_or_sentence.lower())

    # If spaCy model has no tagger/parser, token.pos_ may be blank.
    for token in doc_or_sentence:
        if token.pos_ in {"VERB", "AUX"} and token.lemma_.lower() in OBLIGATION_TERMS:
            return True
        if token.text.lower() in OBLIGATION_TERMS:
            return True
    return False


def is_obligation_sentence(sentence: str) -> bool:
    """Return True when a sentence looks like a regulated compliance obligation."""
    sentence = (sentence or "").strip()
    if len(sentence) < 10:
        return False

    lower = sentence.lower()
    entity_hit = _has_regulated_entity(lower)
    obligation_hit = _has_obligation_term(lower)
    advisory_hit = any(term in lower for term in SOFT_ADVISORY_TERMS)

    # Strong forms: "banks shall", "regulated entities must", etc.
    strong_pattern = re.search(
        r"\b(bank|banks|regulated entities|regulated entity|re|res|nbfc|nbfcs|branch|branches|canara bank)\b"
        r".{0,80}\b(shall|must|will|are required to|is required to|required to|obligated to|ensure|submit|comply|rectify|upload|report|implement)\b",
        lower,
    )

    if strong_pattern:
        return True

    # Generic strict rule from the plan: regulated entity + modal/action verb.
    if entity_hit and obligation_hit:
        return True

    # Exclude pure advisories unless there is a clear mandatory verb.
    if advisory_hit and not any(term in lower for term in ("shall", "must", "required", "obligated")):
        return False

    return False


def extract_obligation_sentences(text: str) -> List[str]:
    """
    Extract obligation sentences from regulatory circular text.

    Main function required by v3 plan:
        extract_obligation_sentences(text: str) -> list[str]
    """
    nlp = get_nlp()
    sentences: List[str] = []

    if nlp is None:
        raw_sentences = _regex_sentences(text)
        for sent in raw_sentences:
            if is_obligation_sentence(sent):
                sentences.append(sent)
        return _dedupe(sentences)

    doc = nlp(text or "")
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text:
            continue
        lower = sent_text.lower()
        if is_obligation_sentence(sent_text) and _has_action_verb(sent):
            sentences.append(sent_text)

    return _dedupe(sentences)


def _dedupe(sentences: List[str]) -> List[str]:
    seen = set()
    result = []
    for sent in sentences:
        key = re.sub(r"\s+", " ", sent.strip().lower())
        if key not in seen:
            seen.add(key)
            result.append(sent.strip())
    return result


if __name__ == "__main__":
    sample_text = """
    Reserve Bank of India Circular — Canara Bank relevant sample.
    All banks shall update customer KYC records by September 30, 2026.
    Regulated entities must comply with revised directions on CKYCR uploads.
    Banks are required to submit returns by the 15th of every month.
    Canara Bank shall rectify rejected data within 7 days of the CIC rejection report.
    Banks may consider customer awareness campaigns for digital fraud prevention.
    This circular provides background on previous supervisory observations.
    """
    extracted = extract_obligation_sentences(sample_text)
    print("Obligation sentences found:")
    for index, sentence in enumerate(extracted, 1):
        print(f"{index}. {sentence}")
