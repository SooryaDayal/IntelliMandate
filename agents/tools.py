"""
IntelliMandate v3 — Tool Registry
File: agents/tools.py

June 17 Member B Task
No LLMs. Pure Python tool functions used by the ReAct orchestrator.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import uuid
from datetime import datetime

from .obligation_extractor import extract_obligation_sentences as _extract_obligations
from .finbert_classifier import classify_sentences
from .entity_extractor import extract_entities as _extract_entities
from .extraction_agent import extract_maps_from_text, infer_canara_wing_hint
from .mpi_engine import score_maps_batch

try:
    from .vector_store import search_maps, add_map_embedding
except Exception:
    search_maps = None
    add_map_embedding = None


def classify_signal_type(text: str, title: str = "") -> Dict[str, Any]:
    combined = f"{title}\n{text}".lower()

    if any(word in combined for word in ["amendment", "modify", "revised", "updated"]):
        signal_type = "CIRCULAR_AMENDMENT"
    elif any(word in combined for word in ["penalty", "monetary penalty", "fine"]):
        signal_type = "PENALTY_ORDER"
    elif any(word in combined for word in ["master direction", "direction", "guidelines"]):
        signal_type = "MASTER_DIRECTION"
    else:
        signal_type = "REGULATORY_UPDATE"

    return {
        "signal_type": signal_type,
        "confidence": 0.85,
        "reason": "Keyword-based signal classification without LLM.",
    }


def extract_obligation_sentences(text: str) -> Dict[str, Any]:
    obligations = _extract_obligations(text)
    return {
        "count": len(obligations),
        "obligations": obligations,
    }


def finbert_classify(sentences: List[str]) -> Dict[str, Any]:
    classified = classify_sentences(sentences)
    return {
        "count": len(classified),
        "classified_sentences": classified,
    }


def extract_entities(sentence: str) -> Dict[str, Any]:
    entities = _extract_entities(sentence)
    return {
        "sentence": sentence,
        "entities": entities,
    }


def run_delta_analysis(current_text: str, previous_text: Optional[str] = None) -> Dict[str, Any]:
    if not previous_text:
        return {
            "delta_type": "NEW_MANDATE",
            "summary": "No previous version found. Treating this as a new regulatory mandate.",
            "changed": True,
        }

    current_words = set(current_text.lower().split())
    previous_words = set(previous_text.lower().split())

    added = sorted(list(current_words - previous_words))[:25]
    removed = sorted(list(previous_words - current_words))[:25]

    return {
        "delta_type": "AMENDMENT",
        "summary": f"Detected {len(added)} added terms and {len(removed)} removed terms.",
        "changed": bool(added or removed),
        "added_terms": added,
        "removed_terms": removed,
    }


def compute_mpi_score(map_obj: Dict[str, Any], source: str = "RBI") -> Dict[str, Any]:
    scored = score_maps_batch([map_obj], source=source)
    if not scored:
        return map_obj
    return scored[0]


def query_knowledge_graph(query: str) -> Dict[str, Any]:
    """
    Placeholder until Member A knowledge graph is connected.
    Keeps orchestrator stable.
    """
    return {
        "query": query,
        "matches": [],
        "note": "Knowledge graph lookup placeholder. Backend graph integration can be connected later.",
    }


def route_to_wings(map_obj: Dict[str, Any]) -> Dict[str, Any]:
    obligation_text = str(map_obj.get("obligation_text", ""))
    hint = infer_canara_wing_hint(obligation_text)

    text = obligation_text.lower()
    wings: List[str]

    if any(term in text for term in ["kyc", "ckycr", "aml", "pmla"]):
        wings = ["Compliance Wing", "Retail Banking Wing"]
    elif "priority sector" in text or "psl" in text:
        wings = ["Commercial Banking Wing", "Compliance Wing"]
    elif "credit information" in text or "cic" in text:
        wings = ["Operations Wing", "Compliance Wing"]
    elif "inoperative" in text:
        wings = ["Retail Banking Wing", "Operations Wing"]
    elif "interest" in text and "deposit" in text:
        wings = ["Retail Banking Wing", "Financial Management Wing"]
    elif "bsbda" in text or "basic savings" in text:
        wings = ["Retail Banking Wing", "Compliance Wing"]
    elif "crr" in text or "slr" in text:
        wings = ["Integrated Treasury Wing", "Risk Management Wing"]
    else:
        wings = ["Compliance Wing"]

    return {
        "wings": wings,
        "routing_hint": hint,
    }


def store_maps(maps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Stores MAP embeddings in ChromaDB if vector_store is available.
    This does not replace backend DB storage.
    """
    stored_ids: List[str] = []

    for map_obj in maps:
        map_id = str(map_obj.get("id") or uuid.uuid4())
        map_obj["id"] = map_id

        if add_map_embedding is not None:
            add_map_embedding(
                map_id=map_id,
                obligation_text=str(map_obj.get("obligation_text", "")),
                measurable_condition=str(map_obj.get("measurable_condition", "")),
            )

        stored_ids.append(map_id)

    return {
        "stored_count": len(stored_ids),
        "stored_ids": stored_ids,
        "stored_at": datetime.utcnow().isoformat(),
    }


def get_previous_version(reference: str) -> Dict[str, Any]:
    """
    Placeholder for previous circular lookup.
    """
    return {
        "reference": reference,
        "found": False,
        "previous_text": None,
        "note": "Previous version lookup placeholder.",
    }


def flag_affected_maps(map_obj: Dict[str, Any]) -> Dict[str, Any]:
    tier = str(map_obj.get("priority_tier", "")).upper()
    score = float(map_obj.get("mpi_score", 0) or 0)

    affected = tier in {"CRITICAL", "HIGH"} or score >= 70

    return {
        "affected": affected,
        "reason": f"MAP priority tier={tier}, mpi_score={score}",
    }


def escalate_critical(map_obj: Dict[str, Any]) -> Dict[str, Any]:
    tier = str(map_obj.get("priority_tier", "")).upper()

    if tier == "CRITICAL":
        return {
            "escalate": True,
            "level": "Immediate Compliance Escalation",
            "message": "Critical MAP should be escalated to Compliance Wing and senior owner.",
        }

    return {
        "escalate": False,
        "level": "Normal Tracking",
        "message": "MAP does not require immediate critical escalation.",
    }


def extract_maps_tool(
    text: str,
    title: str = "",
    ref_number: str = "",
    source: str = "RBI",
) -> Dict[str, Any]:
    maps = extract_maps_from_text(
        text=text,
        title=title,
        ref_number=ref_number,
        source=source,
        include_scores=True,
    )

    for map_obj in maps:
        routing = route_to_wings(map_obj)
        map_obj["assigned_wings"] = routing["wings"]
        map_obj["routing_hint"] = routing["routing_hint"]

    return {
        "count": len(maps),
        "maps": maps,
    }


TOOL_REGISTRY: Dict[str, Callable[..., Any]] = {
    "classify_signal_type": classify_signal_type,
    "extract_obligation_sentences": extract_obligation_sentences,
    "finbert_classify": finbert_classify,
    "extract_entities": extract_entities,
    "run_delta_analysis": run_delta_analysis,
    "compute_mpi_score": compute_mpi_score,
    "query_knowledge_graph": query_knowledge_graph,
    "route_to_wings": route_to_wings,
    "store_maps": store_maps,
    "get_previous_version": get_previous_version,
    "flag_affected_maps": flag_affected_maps,
    "escalate_critical": escalate_critical,
    "extract_maps_tool": extract_maps_tool,
}


def call_tool(tool_name: str, **kwargs) -> Any:
    if tool_name not in TOOL_REGISTRY:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOL_REGISTRY[tool_name](**kwargs)


if __name__ == "__main__":
    sample_text = """
    Banks shall ensure that interest rates on NRE and NRO deposits are not higher than comparable domestic rupee term deposits.
    Canara Bank must update internal deposit policy and publish revised rates on its website.
    """

    print("Available tools:")
    for name in TOOL_REGISTRY:
        print("-", name)

    print("\nSample extraction:")
    result = call_tool(
        "extract_maps_tool",
        text=sample_text,
        title="RBI Interest Rate on Deposits Amendment Directions 2026",
        ref_number="RBI/2026/Deposit/01",
        source="RBI",
    )
    print(result)