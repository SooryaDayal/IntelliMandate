"""Offline validation engine for IntelliMandate.

Gate 1: Deadline Gate
Gate 2: Integrity Gate using hashlib.sha256
Gate 3: Temporal Gate using spaCy date entity recognition + simple parsing
Gate 4: Semantic Match Gate using local sentence-transformers cosine similarity

Run from project root:
    python -m agents.validation_engine
"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import date, datetime
from typing import Any, Dict, Optional

import spacy
from sentence_transformers import SentenceTransformer, util

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

_nlp = None
_model = None


def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError as exc:
            raise RuntimeError("spaCy model missing. Run: python -m spacy download en_core_web_sm") from exc
    return _nlp


def get_embedding_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def parse_date(text: Any) -> Optional[date]:
    if not text:
        return None
    s = str(text).strip()
    if s.lower() in {"not specified", "none", "null"}:
        return None

    # Common direct formats
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    # Relative deadline like "within 30 days" cannot be converted without issue date.
    return None


def deadline_gate(map_deadline: Any, upload_timestamp: Optional[datetime] = None) -> Dict[str, Any]:
    upload_timestamp = upload_timestamp or datetime.now()
    deadline_date = parse_date(map_deadline)

    if deadline_date is None:
        return {
            "gate": "Deadline Gate",
            "status": "UNKNOWN",
            "escalation_required": False,
            "reason": "No exact deadline date was found.",
        }

    passed = upload_timestamp.date() <= deadline_date
    return {
        "gate": "Deadline Gate",
        "status": "PASSED" if passed else "BREACHED",
        "escalation_required": not passed,
        "deadline": deadline_date.isoformat(),
        "uploaded_at": upload_timestamp.isoformat(),
    }


def integrity_gate(file_bytes: bytes) -> Dict[str, Any]:
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    return {
        "gate": "Integrity Gate",
        "status": "PASSED",
        "evidence_file_hash": file_hash,
        "hash_algorithm": "sha256",
    }


def extract_dates_from_text(text: str) -> list[date]:
    dates: list[date] = []

    # First catch strict numeric dates.
    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
        r"\b\d{2}-\d{2}-\d{4}\b",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text):
            parsed = parse_date(match)
            if parsed:
                dates.append(parsed)

    # Then use spaCy DATE entities for written dates.
    nlp = get_nlp()
    doc = nlp(text[:5000])
    for ent in doc.ents:
        if ent.label_ == "DATE":
            parsed = parse_date(ent.text)
            if parsed:
                dates.append(parsed)

    # De-duplicate while preserving order.
    seen = set()
    unique_dates = []
    for d in dates:
        if d not in seen:
            unique_dates.append(d)
            seen.add(d)
    return unique_dates


def temporal_gate(evidence_text: str, mandate_date_issued: Any) -> Dict[str, Any]:
    mandate_date = parse_date(mandate_date_issued)
    if mandate_date is None:
        return {
            "gate": "Temporal Gate",
            "status": "UNKNOWN",
            "reason": "Mandate issue date not available or not parseable.",
        }

    evidence_dates = extract_dates_from_text(evidence_text)
    if not evidence_dates:
        return {
            "gate": "Temporal Gate",
            "status": "UNKNOWN",
            "mandate_date_issued": mandate_date.isoformat(),
            "reason": "No evidence creation date found in evidence text.",
        }

    earliest_evidence_date = min(evidence_dates)
    passed = earliest_evidence_date >= mandate_date
    return {
        "gate": "Temporal Gate",
        "status": "PASSED" if passed else "REJECTED",
        "mandate_date_issued": mandate_date.isoformat(),
        "evidence_dates_found": [d.isoformat() for d in evidence_dates],
        "reason": "Evidence appears after regulation date." if passed else "Evidence appears to predate the regulation.",
    }


def semantic_match_gate(evidence_text: str, measurable_condition: str) -> Dict[str, Any]:
    model = get_embedding_model()
    embeddings = model.encode([evidence_text, measurable_condition], convert_to_tensor=True)
    score = float(util.cos_sim(embeddings[0], embeddings[1]).item())

    if score >= 0.75:
        status = "PASSED_AUTO_CLOSE"
    elif score >= 0.55:
        status = "HUMAN_REVIEW"
    else:
        status = "REJECTED"

    return {
        "gate": "Semantic Match Gate",
        "status": status,
        "semantic_score": round(score, 4),
        "thresholds": {
            "auto_close": 0.75,
            "human_review_min": 0.55,
            "reject_below": 0.55,
        },
    }


def _read_attr(obj: Any, names: list[str], default: Any = None) -> Any:
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _model_to_map_obj(map_record: Any) -> Dict[str, Any]:
    if map_record is None:
        return {}

    return {
        "id": str(_read_attr(map_record, ["id"], "sample_map")),
        "deadline": _read_attr(map_record, ["deadline"], None),
        "date_issued": _read_attr(map_record, ["date_issued"], None),
        "measurable_condition": _read_attr(map_record, ["measurable_condition"], ""),
        "regulatory_reference": _read_attr(map_record, ["regulatory_reference"], "Not specified"),
        "obligation_text": _read_attr(map_record, ["obligation_text"], ""),
        "evidence_required": _read_attr(map_record, ["evidence_required"], ""),
        "map_type": _read_attr(map_record, ["map_type"], ""),
    }


def validate_evidence(
    map_obj: Optional[Dict[str, Any]] = None,
    evidence_text: str = "",
    evidence_file_bytes: Optional[bytes] = None,
    upload_timestamp: Optional[datetime] = None,
    mandate_date_issued: Any = None,
    evidence_id: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    db: Any = None,
) -> Dict[str, Any]:
    """
    Supports both:
    1. Direct validation:
       validate_evidence(map_obj, evidence_text, evidence_file_bytes)

    2. Backend route validation:
       validate_evidence(evidence_id=evidence_id, evidence_text="", file_bytes=b"", db=db)
    """

    if evidence_file_bytes is None:
        evidence_file_bytes = file_bytes or b""

    evidence_record = None

    if map_obj is None and evidence_id and db is not None:
        try:
            import backend.models as models

            EvidenceModel = getattr(models, "Evidence", None)
            MapModel = getattr(models, "Map", None) or getattr(models, "MAP", None) or getattr(models, "Maps", None)

            if EvidenceModel is not None:
                evidence_uuid = uuid.UUID(str(evidence_id))
                evidence_record = (
                    db.query(EvidenceModel)
                    .filter(getattr(EvidenceModel, "id") == evidence_uuid)
                    .first()
                )

            if evidence_record is not None:
                evidence_text = (
                    evidence_text
                    or _read_attr(evidence_record, ["evidence_text", "text", "content", "description", "notes"], "")
                    or ""
                )

                upload_timestamp = (
                    upload_timestamp
                    or _read_attr(evidence_record, ["uploaded_at", "created_at", "submitted_at"], None)
                )

                linked_map_id = _read_attr(evidence_record, ["map_id", "mapId", "mandate_map_id"], None)

                map_record = None
                if linked_map_id is not None and MapModel is not None:
                    map_record = (
                        db.query(MapModel)
                        .filter(getattr(MapModel, "id") == linked_map_id)
                        .first()
                    )

                map_obj = _model_to_map_obj(map_record)

        except Exception as exc:
            return {
                "evidence_id": evidence_id,
                "final_status": "VALIDATION_ERROR",
                "error": str(exc),
                "validator": "IntelliMandate v1.0",
            }

    if map_obj is None:
        map_obj = {
            "id": evidence_id or "sample_map",
            "deadline": None,
            "date_issued": None,
            "measurable_condition": "",
            "regulatory_reference": "Not specified",
        }

    gate1 = deadline_gate(map_obj.get("deadline"), upload_timestamp)
    gate2 = integrity_gate(evidence_file_bytes)
    gate3 = temporal_gate(evidence_text, mandate_date_issued or map_obj.get("date_issued"))
    gate4 = semantic_match_gate(evidence_text, map_obj.get("measurable_condition", ""))

    gate_results = [gate1, gate2, gate3, gate4]

    if gate1["status"] == "BREACHED" or gate3["status"] == "REJECTED" or gate4["status"] == "REJECTED":
        final_status = "REJECTED_OR_ESCALATED"
    elif gate4["status"] == "HUMAN_REVIEW" or gate1["status"] == "UNKNOWN" or gate3["status"] == "UNKNOWN":
        final_status = "HUMAN_REVIEW"
    else:
        final_status = "AUTO_CLOSED"

    result = {
        "evidence_id": evidence_id,
        "map_id": map_obj.get("id", "sample_map"),
        "final_status": final_status,
        "gate_results": gate_results,
        "semantic_score": gate4["semantic_score"],
        "evidence_file_hash": gate2["evidence_file_hash"],
        "validator": "IntelliMandate v1.0",
    }

    if final_status == "AUTO_CLOSED":
        result["certificate"] = generate_certificate(result, map_obj)

    return result

def generate_certificate(validation_result: Dict[str, Any], map_obj: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a simple compliance certificate JSON after MAP closure."""
    return {
        "map_id": validation_result.get("map_id"),
        "regulation_reference": map_obj.get("regulatory_reference", "Not specified"),
        "closed_at": datetime.now().isoformat(),
        "evidence_file_hash": validation_result.get("evidence_file_hash"),
        "semantic_score": validation_result.get("semantic_score"),
        "gate_results": validation_result.get("gate_results", []),
        "validator": "IntelliMandate v1.0",
    }


if __name__ == "__main__":
    sample_map = {
        "id": "map_001",
        "measurable_condition": "All customer KYC records are updated and a completion report is maintained.",
        "deadline": "2099-12-31",
        "date_issued": "2026-06-01",
        "regulatory_reference": "RBI Sample Circular",
    }

    sample_evidence = """
    KYC Update Completion Report
    Created on 2026-06-10.
    This report confirms that all customer KYC records were updated and verified.
    A completion report has been maintained by the Compliance Department.
    """

    result = validate_evidence(
        sample_map,
        evidence_text=sample_evidence,
        evidence_file_bytes=sample_evidence.encode("utf-8"),
        mandate_date_issued="2026-06-01",
    )
    print(result)
    if result["final_status"] == "AUTO_CLOSED":
        print(generate_certificate(result, sample_map))
