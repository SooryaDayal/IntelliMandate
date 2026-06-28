"""
IntelliMandate v3 — MAP Extraction Agent
File: agents/extraction_agent.py

June 15 Member B Task B-2-4
No LLMs. Combines:
1. obligation_extractor
2. finbert_classifier
3. entity_extractor
4. MAP assembly
5. validation
6. deduplication
7. optional MPI scoring

Run:
    python -m agents.extraction_agent
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from .entity_extractor import extract_entities, parse_money_to_rupees
from .finbert_classifier import classify_sentences
from .mpi_engine import score_maps_batch
from .obligation_extractor import extract_obligation_sentences
try:
    from .vector_store import add_map_embedding
except Exception:  # Allows extraction tests to run even if ChromaDB is not installed yet.
    add_map_embedding = None

REQUIRED_MAP_KEYS = [
    "obligation_text",
    "measurable_condition",
    "deadline",
    "penalty_exposure",
    "evidence_required",
    "regulatory_reference",
    "map_type",
]

VALID_MAP_TYPES = {
    "PROCESS_CHANGE",
    "POLICY_UPDATE",
    "SYSTEM_CHANGE",
    "REPORTING_OBLIGATION",
}


def infer_map_type(sentence: str) -> str:
    lower = (sentence or "").lower()
    if any(term in lower for term in ("upload", "system", "ckycr", "cic", "data", "portal", "automated")):
        return "SYSTEM_CHANGE"
    if any(term in lower for term in ("submit", "report", "return", "fiu", "acknowledgement", "compliance report")):
        return "REPORTING_OBLIGATION"
    if any(term in lower for term in ("policy", "direction", "master direction", "priority sector", "interest rate", "bsbda", "irac")):
        return "POLICY_UPDATE"
    return "PROCESS_CHANGE"


def infer_evidence_required(sentence: str, map_type: str) -> str:
    lower = (sentence or "").lower()
    if "ckycr" in lower or "kyc" in lower:
        return "CKYCR/KYC upload confirmation report and rejected-record queue screenshot"
    if "cic" in lower or "credit information" in lower:
        return "CIC upload confirmation and zero-pending rejection report"
    if "priority sector" in lower or "psl" in lower:
        return "Priority sector lending return and sector-wise lending portfolio report"
    if "aml" in lower or "pmla" in lower or "fiu" in lower:
        return "FIU-IND submission acknowledgement and transaction monitoring audit report"
    if "interest" in lower and "deposit" in lower:
        return "Branch display proof and website screenshot with timestamp"
    if "inoperative" in lower:
        return "Account reclassification report and branch compliance certificate"
    if "bsbda" in lower or "basic savings" in lower:
        return "BSBDA account opening report and branch compliance certificate"
    if map_type == "REPORTING_OBLIGATION":
        return "Regulatory submission acknowledgement and signed compliance report"
    if map_type == "SYSTEM_CHANGE":
        return "System report, upload log, or screenshot proving implementation"
    if map_type == "POLICY_UPDATE":
        return "Approved policy note and implementation circular"
    return "Compliance certificate, implementation report, or audit evidence"


def infer_measurable_condition(sentence: str) -> str:
    lower = (sentence or "").lower()
    if "within 7 days" in lower:
        return "100% completion within 7 days with zero overdue exceptions"
    if "within 30 days" in lower:
        return "100% completion within 30 days with documentary evidence"
    if "within 45 days" in lower:
        return "100% completion within 45 days with documentary evidence"
    if "within 90 days" in lower:
        return "100% completion within 90 days with management sign-off"
    if "ckycr" in lower:
        return "100% of customer KYC records uploaded to CKYCR with zero rejected uploads pending beyond allowed timeline"
    if "priority sector" in lower:
        return "Priority sector lending target achieved and supported by submitted RBI return"
    if "suspicious" in lower or "fiu" in lower:
        return "100% of suspicious transactions reported to FIU-IND within prescribed reporting window"
    if "display" in lower or "publish" in lower:
        return "All required displays/publications updated with timestamped proof and zero discrepancy"
    return "Documented evidence proves the obligation has been fully completed within the required timeline"


def _format_deadline(entities: Dict[str, Any]) -> str:
    dates = entities.get("dates") or []
    if not dates:
        return "Not specified"
    # Prefer the original matched phrase so UI can show the regulatory language.
    return str(dates[0].get("text") or dates[0].get("date") or "Not specified")


def _format_penalty(entities: Dict[str, Any]) -> Any:
    money = entities.get("money") or 0.0
    if money <= 0:
        return 0.0
    return float(money)


def _regulatory_reference(title: Optional[str], ref_number: Optional[str], entities: Dict[str, Any]) -> str:
    clauses = entities.get("clauses") or []
    parts = []
    if title:
        parts.append(title)
    if ref_number:
        parts.append(ref_number)
    if clauses:
        parts.append(", ".join(clauses))
    return " | ".join(parts) if parts else "Not specified"


def assemble_map(
    obligation_sentence: str,
    entities: Dict[str, Any],
    title: Optional[str] = None,
    ref_number: Optional[str] = None,
) -> Dict[str, Any]:
    map_type = infer_map_type(obligation_sentence)
    return {
        "obligation_text": obligation_sentence.strip(),
        "measurable_condition": infer_measurable_condition(obligation_sentence),
        "deadline": _format_deadline(entities),
        "penalty_exposure": _format_penalty(entities),
        "evidence_required": infer_evidence_required(obligation_sentence, map_type),
        "regulatory_reference": _regulatory_reference(title, ref_number, entities),
        "map_type": map_type,
    }


def validate_map(map_obj: Dict[str, Any]) -> bool:
    if not isinstance(map_obj, dict):
        return False
    if len(str(map_obj.get("obligation_text", "")).strip()) < 10:
        return False
    if map_obj.get("map_type") not in VALID_MAP_TYPES:
        return False
    for key in REQUIRED_MAP_KEYS:
        if key not in map_obj:
            return False
    return True


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def deduplicate_maps(maps: List[Dict[str, Any]], threshold: float = 0.88) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for candidate in maps:
        text = candidate.get("obligation_text", "")
        if not any(_similarity(text, existing.get("obligation_text", "")) >= threshold for existing in result):
            result.append(candidate)
    return result

def is_actionable_obligation(sentence: str) -> bool:
    text = " ".join((sentence or "").lower().split())

    if len(text) < 35:
        return False

    if len(text) > 900:
        return False

    noisy_phrases = [
        "shall be called",
        "shall come into effect",
        "shall supersede",
        "unless the context otherwise requires",
        "shall have the same meaning",
        "meaning assigned to them",
        "inserted with effect",
        "deleted with effect",
        "substituted vide",
        "with effect from",
        "--- page",
        "s. no.",
        "example",
        "bank a may",
        "bank b may",
        "bank c may",
        "bank d will",
    ]

    if any(phrase in text for phrase in noisy_phrases):
        return False

    action_terms = [
        "shall ensure",
        "shall submit",
        "shall report",
        "shall maintain",
        "shall upload",
        "shall update",
        "shall comply",
        "shall provide",
        "shall establish",
        "shall implement",
        "shall monitor",
        "must",
        "are required to",
        "is required to",
        "have to ensure",
        "will have to",
    ]

    return any(term in text for term in action_terms)


def has_penalty_context(sentence: str) -> bool:
    text = (sentence or "").lower()
    penalty_terms = [
        "penalty",
        "penal",
        "fine",
        "non-compliance",
        "shortfall",
        "contravention",
        "failure to",
        "liable",
        "ridf",
        "allocated amounts",
    ]
    return any(term in text for term in penalty_terms)


def extract_maps_from_text(
    text: str,
    title: Optional[str] = None,
    ref_number: Optional[str] = None,
    source: str = "RBI",
    include_scores: bool = False,
) -> List[Dict[str, Any]]:
    """Extract MAP dicts from circular text without using any LLM."""
    obligation_sentences = extract_obligation_sentences(text)
    classified = classify_sentences(obligation_sentences)

    maps: List[Dict[str, Any]] = []
    for item in classified:
        if item.get("label") != "OBLIGATION":
            continue

        sentence = str(item.get("sentence", ""))

        if not is_actionable_obligation(sentence):
            continue

        entities = extract_entities(sentence)

    # Do NOT assign document-level money to every MAP.
    # Only keep money if it appears inside the actual obligation sentence
    # and the sentence has penalty/shortfall/non-compliance context.
        if not has_penalty_context(sentence):
            entities["money"] = 0.0

        map_obj = assemble_map(sentence, entities, title=title, ref_number=ref_number)
        if validate_map(map_obj):
            maps.append(map_obj)

    maps = deduplicate_maps(maps)

    if include_scores:
        scored_maps = score_maps_batch(maps, source=source)
        scored_maps = sorted(
            scored_maps,
            key=lambda item: float(item.get("mpi_score", 0) or 0),
            reverse=True,
        )
        return scored_maps[:12]

    return maps[:12]


def _make_map_id(map_obj: Dict[str, Any], mandate_id: Any = None) -> str:
    seed = f"{mandate_id}|{map_obj.get('obligation_text', '')}|{map_obj.get('regulatory_reference', '')}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def _get_model_classes():
    """Best-effort import of backend models without hardcoding one schema too tightly."""
    try:
        import backend.models as models
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Could not import backend.models. Run from project root after Member A backend exists.") from exc

    mandate_cls = getattr(models, "Mandate", None) or getattr(models, "Mandates", None)
    map_cls = getattr(models, "MAP", None) or getattr(models, "Map", None) or getattr(models, "Maps", None)
    if mandate_cls is None or map_cls is None:
        raise RuntimeError("Could not find Mandate and MAP/Map models in backend.models.")
    return mandate_cls, map_cls


def _read_attr(obj: Any, names: List[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _set_if_exists(obj: Any, name: str, value: Any) -> None:
    if hasattr(obj, name):
        setattr(obj, name, value)

def _db_deadline_value(deadline_value: Any) -> Optional[date]:
    """
    Convert MAP deadline text into a PostgreSQL-compatible date value.
    DB deadline column expects date or None, not strings like 'Not specified'.
    """
    if deadline_value is None:
        return None

    if isinstance(deadline_value, date):
        return deadline_value

    text = str(deadline_value).strip()

    if not text or text.lower() in {"not specified", "none", "null", "n/a"}:
        return None

    # Handles: within 7 days, within 30 days, within 45 days
    match = re.search(r"within\s+(\d+)\s+days?", text.lower())
    if match:
        days = int(match.group(1))
        return datetime.utcnow().date() + timedelta(days=days)

    # Handles ISO format: 2026-09-30
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass

    # Handles: September 30, 2026
    try:
        return datetime.strptime(text, "%B %d, %Y").date()
    except ValueError:
        pass

    # If we cannot parse it, store NULL instead of crashing
    return None


def infer_canara_wing_hint(obligation_text: str) -> str:
    """Return Canara Bank Wing routing hint for logs until Member A routing engine is connected."""
    text = (obligation_text or "").lower()
    if any(term in text for term in ("kyc", "ckycr", "aml", "pmla")):
        return "MAP obligation touches KYC/AML → route to Compliance Wing and Retail Banking Wing"
    if "priority sector" in text or "psl" in text:
        return "MAP obligation touches Priority Sector → route to Commercial Banking Wing and Compliance Wing"
    if "credit information" in text or "cic" in text:
        return "MAP obligation touches Credit Information → route to Operations Wing and Compliance Wing"
    if "inoperative" in text:
        return "MAP obligation touches Inoperative Account → route to Retail Banking Wing and Operations Wing"
    if "interest" in text and "deposit" in text:
        return "MAP obligation touches Interest Rate → route to Retail Banking Wing and Financial Management Wing"
    if "bsbda" in text or "basic savings" in text:
        return "MAP obligation touches BSBDA → route to Retail Banking Wing and Compliance Wing"
    if "crr" in text or "slr" in text:
        return "MAP obligation touches CRR/SLR → route to Integrated Treasury Wing and Risk Management Wing"
    return "MAP obligation is general regulatory compliance → route to Compliance Wing"


def extract_maps_from_mandate(mandate_id, db) -> List[str]:
    """
    Required DB function:
        Fetches mandate from DB, runs pipeline, stores MAPs in maps table, marks mandate processed.

    This is written defensively because Member A's exact SQLAlchemy model names/columns may differ.
    """
    Mandate, MapModel = _get_model_classes()
    mandate = db.query(Mandate).filter(getattr(Mandate, "id") == mandate_id).first()
    if not mandate:
        raise ValueError(f"Mandate not found: {mandate_id}")

    text = _read_attr(mandate, ["text", "content", "document_text", "raw_text"], "")
    title = _read_attr(mandate, ["title", "name"], None)
    ref_number = _read_attr(mandate, ["ref_number", "reference_number", "regulatory_reference"], None)
    source = _read_attr(mandate, ["source", "authority"], "RBI")

    maps = extract_maps_from_text(text, title=title, ref_number=ref_number, source=source, include_scores=True)
    stored_ids: List[str] = []

    for map_obj in maps:
        map_id = _make_map_id(map_obj, mandate_id)
        record = MapModel()
        _set_if_exists(record, "id", map_id)
        _set_if_exists(record, "mandate_id", mandate_id)
        for key, value in map_obj.items():
            if key == "deadline":
                value = _db_deadline_value(value)
            _set_if_exists(record, key, value)
        _set_if_exists(record, "status", "OPEN")
        db.add(record)
        stored_ids.append(map_id)

        if add_map_embedding is not None:
            try:
                add_map_embedding(
                    map_id=map_id,
                    obligation_text=str(map_obj.get("obligation_text", "")),
                    measurable_condition=str(map_obj.get("measurable_condition", "")),
                )
            except Exception as exc:
                print(f"[VectorStore] Failed to store embedding for {map_id}: {exc}")

    _set_if_exists(mandate, "processed", True)
    db.commit()
    return stored_ids


def process_unprocessed_mandates(db) -> Dict[str, Any]:
    """
    Required DB function:
        Finds mandates where processed=False and runs extraction on each.
    """
    Mandate, _MapModel = _get_model_classes()
    if hasattr(Mandate, "processed"):
        mandates = db.query(Mandate).filter(getattr(Mandate, "processed") == False).all()  # noqa: E712
    else:
        mandates = db.query(Mandate).all()

    results = {}
    for mandate in mandates:
        mandate_id = getattr(mandate, "id")
        stored = extract_maps_from_mandate(mandate_id, db)
        text = _read_attr(mandate, ["text", "content", "document_text", "raw_text"], "")
        for map_obj in extract_maps_from_text(text, include_scores=False):
            print(infer_canara_wing_hint(map_obj.get("obligation_text", "")))
        results[str(mandate_id)] = stored
    return {"processed_mandates": len(results), "stored_map_ids": results}


if __name__ == "__main__":
    sample_circulars = [
        {
            "title": "RBI Master Direction on KYC — CKYCR Upload Directions",
            "ref_number": "RBI/2026-27/DOR.AML.REC.01",
            "source": "RBI",
            "text": """
            All banks shall upload pending customer KYC documents to Central KYC Registry within 45 days.
            Canara Bank shall rectify rejected CKYCR uploads within 7 days of rejection report receipt.
            Banks may consider customer awareness messages for digital safety.
            """,
        },
        {
            "title": "RBI Priority Sector Lending Master Direction",
            "ref_number": "RBI/2026-27/FIDD.PSL.REC.02",
            "source": "RBI",
            "text": """
            Banks must achieve prescribed priority sector lending targets by September 30, 2026.
            The penalty exposure for shortfall may be ₹1.63 crore based on supervisory assessment.
            Branches are required to maintain sector-wise lending portfolio reports.
            """,
        },
        {
            "title": "Credit Information Companies Data Rectification",
            "ref_number": "RBI/2026-27/CIC.REC.03",
            "source": "RBI",
            "text": """
            Banks are required to upload corrected records to Credit Information Companies within 7 days of receipt of rejection report.
            Canara Bank shall ensure zero CIC rejection reports pending beyond 7 days.
            Non-compliance may attract penalty of Rs.32 lakh.
            """,
        },
    ]

    all_maps: List[Dict[str, Any]] = []
    for circular in sample_circulars:
        maps = extract_maps_from_text(
            circular["text"],
            title=circular["title"],
            ref_number=circular["ref_number"],
            source=circular["source"],
            include_scores=True,
        )
        all_maps.extend(maps)

    print(json.dumps(all_maps, indent=2, ensure_ascii=False, default=str))
