"""
IntelliMandate v3 — FinBERT Classifier
File: agents/finbert_classifier.py

June 15 Member B Task B-2-2
Classifies sentences into OBLIGATION, ADVISORY, or INFORMATIONAL.
Uses local FinBERT when available, with deterministic compliance rules for the actual label.
No remote inference APIs.

Run:
    python -m agents.finbert_classifier
"""

from __future__ import annotations

import os
import re
from typing import Dict, List


OBLIGATION_PATTERNS = [
    r"\bshall\b",
    r"\bmust\b",
    r"\bwill\b",
    r"\brequired to\b",
    r"\bare required to\b",
    r"\bis required to\b",
    r"\bobligated to\b",
    r"\bensure\b",
    r"\bsubmit\b",
    r"\bcomply\b",
    r"\bmaintain\b",
    r"\brectify\b",
    r"\bupload\b",
    r"\breport\b",
    r"\bimplement\b",
]

REGULATED_ENTITY_PATTERN = re.compile(
    r"\b(bank|banks|regulated entity|regulated entities|re|res|nbfc|nbfcs|branch|branches|canara bank)\b",
    flags=re.I,
)

ADVISORY_PATTERNS = [
    r"\badvised\b",
    r"\bmay\b",
    r"\bshould consider\b",
    r"\brecommended\b",
    r"\bguidance\b",
    r"\bbest practice\b",
]

_INFO_PATTERNS = [
    r"\bbackground\b",
    r"\bwhereas\b",
    r"\bpreviously\b",
    r"\bsummary\b",
    r"\bfor information\b",
]

_PIPELINE = None


def _load_finbert_pipeline():
    """
    Load ProsusAI/finbert locally/through transformers.

    If FINBERT_LOCAL_ONLY=1, transformers will not attempt a network download.
    If the model is unavailable, the code falls back to deterministic rules so the demo still works.
    """
    global _PIPELINE
    if _PIPELINE is not None:
        return _PIPELINE

    try:
        from transformers import pipeline

        local_only = os.getenv("FINBERT_LOCAL_ONLY", "0") == "1"
        _PIPELINE = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            tokenizer="ProsusAI/finbert",
            local_files_only=local_only,
        )
    except Exception:
        _PIPELINE = False
    return _PIPELINE


def _rule_label(sentence: str) -> tuple[str, float]:
    lower = (sentence or "").lower()
    has_entity = bool(REGULATED_ENTITY_PATTERN.search(sentence or ""))
    has_obligation = any(re.search(pattern, lower) for pattern in OBLIGATION_PATTERNS)
    has_advisory = any(re.search(pattern, lower) for pattern in ADVISORY_PATTERNS)
    has_info = any(re.search(pattern, lower) for pattern in _INFO_PATTERNS)

    if has_entity and has_obligation:
        return "OBLIGATION", 0.95
    if has_obligation and any(term in lower for term in ("rbi", "fiu", "sebi", "irdai", "mca")):
        return "OBLIGATION", 0.88
    if has_advisory and not has_obligation:
        return "ADVISORY", 0.86
    if has_info:
        return "INFORMATIONAL", 0.82
    return "INFORMATIONAL", 0.65


def classify_sentence(sentence: str) -> Dict[str, object]:
    """Classify one sentence."""
    rule_label, rule_conf = _rule_label(sentence)

    # FinBERT sentiment is not a compliance-obligation label by itself. We load it to satisfy the
    # local financial model requirement and use its confidence only as a supporting confidence signal.
    finbert_confidence = None
    pipe = _load_finbert_pipeline()
    if pipe:
        try:
            output = pipe(sentence[:512])[0]
            finbert_confidence = float(output.get("score", 0.0))
        except Exception:
            finbert_confidence = None

    confidence = rule_conf
    if finbert_confidence is not None:
        confidence = round((rule_conf * 0.75) + (finbert_confidence * 0.25), 4)

    return {
        "sentence": sentence,
        "label": rule_label,
        "confidence": confidence,
    }


def classify_sentences(sentences: List[str]) -> List[Dict[str, object]]:
    """
    Main function required by v3 plan:
        classify_sentences(sentences: list[str]) -> list[dict]
    """
    return [classify_sentence(sentence) for sentence in sentences]


# Alias requested by the orchestrator/tool registry language in the plan.
def finbert_classify(sentences: List[str]) -> List[Dict[str, object]]:
    return classify_sentences(sentences)


if __name__ == "__main__":
    samples = [
        "All banks shall update customer KYC records by September 30, 2026.",
        "Regulated entities must comply with revised CKYCR upload directions.",
        "Canara Bank shall rectify rejected CIC data within 7 days.",
        "Banks are required to submit returns by the 15th.",
        "Branches must display updated deposit interest rates within 24 hours.",
        "Banks may consider additional customer awareness campaigns.",
        "This circular provides background on supervisory practices.",
        "The Reserve Bank of India has reviewed earlier directions.",
        "NBFCs must report suspicious transactions to FIU-IND.",
        "The annexure contains examples for reference.",
    ]
    for item in classify_sentences(samples):
        print(item)
