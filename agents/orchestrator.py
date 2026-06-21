"""
IntelliMandate v3 — ReAct Orchestrator
File: agents/orchestrator.py

June 17 Member B Task
No LLMs. Pure Python ReAct loop:
Reason -> Act -> Observe -> Final
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from .tools import call_tool


def _step(
    reasoning_log: List[Dict[str, Any]],
    reason: str,
    action: str,
    observation: Any,
) -> None:
    reasoning_log.append(
        {
            "reason": reason,
            "action": action,
            "observation": observation,
            "timestamp": datetime.utcnow().isoformat(),
        }
    )


def run_react_on_text(
    text: str,
    title: str = "",
    ref_number: str = "",
    source: str = "RBI",
    store_embeddings: bool = False,
) -> Dict[str, Any]:
    """
    Main ReAct orchestration loop for one regulatory circular.
    No LLM is used.
    """

    reasoning_log: List[Dict[str, Any]] = []

    # 1. Reason: identify signal type
    signal_result = call_tool("classify_signal_type", text=text, title=title)
    _step(
        reasoning_log,
        reason="Identify what kind of regulatory signal this document represents.",
        action="classify_signal_type",
        observation=signal_result,
    )

    # 2. Reason: check whether previous version exists
    previous_result = call_tool("get_previous_version", reference=ref_number or title)
    _step(
        reasoning_log,
        reason="Check whether this circular has a previous version for delta comparison.",
        action="get_previous_version",
        observation=previous_result,
    )

    # 3. Reason: compare current document with previous version
    delta_result = call_tool(
        "run_delta_analysis",
        current_text=text,
        previous_text=previous_result.get("previous_text"),
    )
    _step(
        reasoning_log,
        reason="Determine whether the document creates a new mandate or amends an existing one.",
        action="run_delta_analysis",
        observation=delta_result,
    )

    # 4. Reason: extract obligation sentences
    obligation_result = call_tool("extract_obligation_sentences", text=text)
    obligations = obligation_result.get("obligations", [])
    _step(
        reasoning_log,
        reason="Find sentences that contain regulatory obligations.",
        action="extract_obligation_sentences",
        observation={
            "count": len(obligations),
            "sample": obligations[:3],
        },
    )

    # 5. Reason: classify obligation sentences using FinBERT
    finbert_result = call_tool("finbert_classify", sentences=obligations)
    _step(
        reasoning_log,
        reason="Classify extracted sentences as obligation, advisory, or informational.",
        action="finbert_classify",
        observation={
            "count": finbert_result.get("count", 0),
            "sample": finbert_result.get("classified_sentences", [])[:3],
        },
    )

    # 6. Reason: extract MAPs, score them, and route to Wings
    maps_result = call_tool(
        "extract_maps_tool",
        text=text,
        title=title,
        ref_number=ref_number,
        source=source,
    )
    maps = maps_result.get("maps", [])
    _step(
        reasoning_log,
        reason="Convert obligations into Measurable Action Points with MPI score and Wing routing.",
        action="extract_maps_tool",
        observation={
            "maps_created": len(maps),
            "sample": maps[:2],
        },
    )

    # 7. Reason: flag affected MAPs and escalation status
    final_maps: List[Dict[str, Any]] = []

    for map_obj in maps:
        flag_result = call_tool("flag_affected_maps", map_obj=map_obj)
        escalation_result = call_tool("escalate_critical", map_obj=map_obj)

        map_obj["affected"] = flag_result.get("affected", False)
        map_obj["affected_reason"] = flag_result.get("reason")
        map_obj["escalation"] = escalation_result

        final_maps.append(map_obj)

    _step(
        reasoning_log,
        reason="Check which MAPs need operational attention or escalation.",
        action="flag_affected_maps + escalate_critical",
        observation={
            "affected_maps": sum(1 for item in final_maps if item.get("affected")),
            "critical_escalations": sum(
                1 for item in final_maps if item.get("escalation", {}).get("escalate")
            ),
        },
    )

    # 8. Optional: store embeddings
    storage_result: Optional[Dict[str, Any]] = None

    if store_embeddings and final_maps:
        storage_result = call_tool("store_maps", maps=final_maps)
        _step(
            reasoning_log,
            reason="Store MAP embeddings in vector database for semantic search.",
            action="store_maps",
            observation=storage_result,
        )

    return {
        "status": "complete",
        "orchestrator": "IntelliMandate v3 ReAct Orchestrator",
        "llm_used": False,
        "source": source,
        "title": title,
        "ref_number": ref_number,
        "signal_type": signal_result.get("signal_type"),
        "delta": delta_result,
        "maps_created": len(final_maps),
        "maps": final_maps,
        "storage": storage_result,
        "reasoning_log": reasoning_log,
        "completed_at": datetime.utcnow().isoformat(),
    }


def summarize_orchestration(result: Dict[str, Any]) -> Dict[str, Any]:
    maps = result.get("maps", [])

    return {
        "status": result.get("status"),
        "signal_type": result.get("signal_type"),
        "maps_created": len(maps),
        "critical": sum(1 for item in maps if item.get("priority_tier") == "CRITICAL"),
        "high": sum(1 for item in maps if item.get("priority_tier") == "HIGH"),
        "medium": sum(1 for item in maps if item.get("priority_tier") == "MEDIUM"),
        "low": sum(1 for item in maps if item.get("priority_tier") == "LOW"),
        "assigned_wings": sorted(
            {
                wing
                for item in maps
                for wing in item.get("assigned_wings", [])
            }
        ),
        "llm_used": result.get("llm_used"),
    }


def orchestrate_mandate(mandate_id: Any, db, store_embeddings: bool = False) -> Dict[str, Any]:
    """
    DB helper for backend integration.
    Fetches mandate text from database and runs ReAct orchestration.
    This does not directly write MAPs to PostgreSQL.
    Existing extraction_agent.extract_maps_from_mandate handles DB insertion.
    """

    try:
        import backend.models as models
    except Exception as exc:
        raise RuntimeError("Could not import backend.models. Run from project root.") from exc

    Mandate = getattr(models, "Mandate", None) or getattr(models, "Mandates", None)
    if Mandate is None:
        raise RuntimeError("Could not find Mandate model in backend.models.")

    mandate = db.query(Mandate).filter(getattr(Mandate, "id") == mandate_id).first()
    if not mandate:
        raise ValueError(f"Mandate not found: {mandate_id}")

    text = (
        getattr(mandate, "raw_text", None)
        or getattr(mandate, "text", None)
        or getattr(mandate, "content", None)
        or getattr(mandate, "document_text", None)
        or ""
    )

    title = getattr(mandate, "title", "") or ""
    source = getattr(mandate, "source", "RBI") or "RBI"
    ref_number = getattr(mandate, "ref_number", "") or ""

    return run_react_on_text(
        text=text,
        title=title,
        ref_number=ref_number,
        source=source,
        store_embeddings=store_embeddings,
    )


if __name__ == "__main__":
    sample_text = """
    RBI has issued revised directions on deposit interest rates.
    Banks shall ensure that interest rates on NRE and NRO deposits are not higher than comparable domestic rupee term deposits.
    Canara Bank must update internal deposit policy and publish revised rates on its website.
    Branches are required to maintain evidence of published deposit rates.
    """

    result = run_react_on_text(
        text=sample_text,
        title="RBI Interest Rate on Deposits Amendment Directions 2026",
        ref_number="RBI/2026/Deposit/01",
        source="RBI",
        store_embeddings=False,
    )

    print("Summary:")
    print(json.dumps(summarize_orchestration(result), indent=2, ensure_ascii=False))

    print("\nReasoning Log:")
    for step in result["reasoning_log"]:
        print(f"\nReason: {step['reason']}")
        print(f"Act: {step['action']}")
        print(f"Observe: {step['observation']}")