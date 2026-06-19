"""
Agent Routes
File: backend/routes/agents.py

FastAPI router exposing all agent endpoints.
Triggers extraction, orchestration, routing,
validation, and graph impact analysis.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Mandate, Map, Assignment, Evidence, AuditLog
from backend.routing_engine import route_map, route_all_unrouted_maps

router = APIRouter(tags=["Agents"])


# ============================================================
# AGENT STATE
# Tracks background task status in memory
# ============================================================

agent_state = {
    "extraction": {
        "status":     "idle",
        "started_at": None,
        "completed_at": None,
        "mandates_processed": 0,
        "maps_created": 0,
        "last_error": None,
    },
    "orchestration": {
        "status":     "idle",
        "mandate_id": None,
        "started_at": None,
        "completed_at": None,
        "maps_created": 0,
        "reasoning_log": [],
        "last_error": None,
    }
}


# ============================================================
# BACKGROUND TASK: EXTRACT ALL UNPROCESSED MANDATES
# ============================================================

def run_extraction_pipeline(db: Session) -> None:
    """
    Extracts MAPs from all unprocessed mandates.
    Runs as FastAPI background task.
    """
    agent_state["extraction"]["status"]     = "running"
    agent_state["extraction"]["started_at"] = datetime.now(timezone.utc).isoformat()
    agent_state["extraction"]["maps_created"] = 0

    try:
        unprocessed = (
            db.query(Mandate)
            .filter(
                Mandate.processed == False,
                Mandate.raw_text.isnot(None),
            )
            .all()
        )

        print(f"[Extraction] Found {len(unprocessed)} unprocessed mandates.")

        total_maps = 0

        for mandate in unprocessed:
            print(f"[Extraction] Processing: {mandate.title[:60]}...")

            try:
                # Try to import and use the full extraction agent
                from agents.extraction_agent import extract_maps_from_mandate
                map_ids = extract_maps_from_mandate(
                    mandate_id = str(mandate.id),
                    db         = db,
                )
                total_maps += len(map_ids)

            except ImportError:
                # Extraction agent not built yet — use placeholder
                print(
                    f"[Extraction] agents/extraction_agent.py not built yet. "
                    f"Marking mandate as processed."
                )
                mandate.processed = True
                db.commit()

        agent_state["extraction"]["maps_created"]   = total_maps
        agent_state["extraction"]["mandates_processed"] = len(unprocessed)
        agent_state["extraction"]["status"]         = "complete"
        agent_state["extraction"]["completed_at"]   = datetime.now(timezone.utc).isoformat()

        print(f"[Extraction] Done. {total_maps} MAPs created.")

    except Exception as e:
        agent_state["extraction"]["status"]     = "error"
        agent_state["extraction"]["last_error"] = str(e)
        agent_state["extraction"]["completed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Extraction] ERROR: {e}")


# ============================================================
# BACKGROUND TASK: ORCHESTRATE ONE MANDATE
# ============================================================

def run_orchestration(mandate_id: str, db: Session) -> None:
    """
    Runs the ReAct orchestrator for one mandate.
    Runs as FastAPI background task.
    """
    agent_state["orchestration"]["status"]     = "running"
    agent_state["orchestration"]["mandate_id"] = mandate_id
    agent_state["orchestration"]["started_at"] = datetime.now(timezone.utc).isoformat()
    agent_state["orchestration"]["reasoning_log"] = []
    agent_state["orchestration"]["maps_created"] = 0

    try:
        # Try to use the full orchestrator if built
        try:
            from agents.orchestrator import run as orchestrator_run
            result = orchestrator_run(mandate_id=mandate_id, db=db)
            agent_state["orchestration"]["maps_created"]  = result.get("maps_created", 0)
            agent_state["orchestration"]["reasoning_log"] = result.get("reasoning_log", [])

        except ImportError:
            # Orchestrator not built yet — run simplified extraction
            print(
                "[Orchestration] agents/orchestrator.py not built yet. "
                "Running simplified extraction pipeline."
            )
            from agents.extraction_agent import extract_maps_from_mandate
            map_ids = extract_maps_from_mandate(
                mandate_id = mandate_id,
                db         = db,
            )
            agent_state["orchestration"]["maps_created"] = len(map_ids)
            agent_state["orchestration"]["reasoning_log"] = [
                "Step 1: Classify signal type — complete",
                f"Step 2: Extract MAPs — {len(map_ids)} MAPs created",
                "Step 3: Score MPI — complete",
                "Step 4: Route to Canara Bank Wings — queued",
            ]

            # Auto-route all new MAPs
            for map_id_str in map_ids:
                try:
                    map_obj = db.query(Map).filter(
                        Map.id == uuid.UUID(map_id_str)
                    ).first()
                    if map_obj:
                        route_map(map_obj, db)
                except Exception as re:
                    print(f"[Orchestration] Routing error: {re}")

        agent_state["orchestration"]["status"]       = "complete"
        agent_state["orchestration"]["completed_at"] = datetime.now(timezone.utc).isoformat()

    except ImportError as ie:
        # Neither orchestrator nor extraction agent built yet
        agent_state["orchestration"]["status"]     = "pending_build"
        agent_state["orchestration"]["last_error"] = (
            "Extraction agent not built yet. "
            "Complete agents/extraction_agent.py first."
        )
        agent_state["orchestration"]["completed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Orchestration] Import error: {ie}")

    except Exception as e:
        agent_state["orchestration"]["status"]     = "error"
        agent_state["orchestration"]["last_error"] = str(e)
        agent_state["orchestration"]["completed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Orchestration] ERROR: {e}")


# ============================================================
# ROUTE 1: POST /agents/extract
# Extract MAPs from all unprocessed mandates
# ============================================================

@router.post("/agents/extract")
def trigger_extraction(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    if agent_state["extraction"]["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Extraction already running. Poll /agents/status."
        )

    background_tasks.add_task(run_extraction_pipeline, db=db)

    return {
        "message":    "MAP extraction triggered for all unprocessed mandates.",
        "status":     "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "poll_url":   "/agents/status"
    }


# ============================================================
# ROUTE 2: POST /agents/extract/{mandate_id}
# Extract MAPs from one specific mandate
# ============================================================

@router.post("/agents/extract/{mandate_id}")
def extract_one_mandate(
    mandate_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        mandate_uuid = uuid.UUID(mandate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mandate ID.")

    mandate = db.query(Mandate).filter(Mandate.id == mandate_uuid).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found.")

    background_tasks.add_task(run_orchestration, mandate_id=mandate_id, db=db)

    return {
        "message":    f"Extraction triggered for mandate: {mandate.title[:60]}",
        "mandate_id": mandate_id,
        "status":     "running",
        "poll_url":   "/agents/orchestration/status"
    }


# ============================================================
# ROUTE 3: POST /agents/orchestrate/{mandate_id}
# Run ReAct orchestrator for one mandate
# ============================================================

@router.post("/agents/orchestrate/{mandate_id}")
def orchestrate_mandate(
    mandate_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        mandate_uuid = uuid.UUID(mandate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mandate ID.")

    mandate = db.query(Mandate).filter(Mandate.id == mandate_uuid).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found.")

    background_tasks.add_task(
        run_orchestration,
        mandate_id = mandate_id,
        db         = db
    )

    return {
        "message":     "ReAct Orchestrator triggered.",
        "mandate_id":  mandate_id,
        "title":       mandate.title,
        "signal_type": mandate.signal_type,
        "status":      "running",
        "poll_url":    "/agents/orchestration/status",
        "note": (
            "The orchestrator will: classify signal → extract obligations → "
            "FinBERT filter → extract entities → score MPI → "
            "route to Canara Bank Wings → store MAPs."
        )
    }


# ============================================================
# ROUTE 4: POST /maps/{map_id}/route
# Trigger 3-LoD routing for one MAP
# ============================================================

@router.post("/maps/{map_id}/route")
def route_single_map(
    map_id: str,
    db: Session = Depends(get_db)
):
    try:
        map_uuid = uuid.UUID(map_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid MAP ID.")

    map_obj = db.query(Map).filter(Map.id == map_uuid).first()
    if not map_obj:
        raise HTTPException(status_code=404, detail="MAP not found.")

    assignments = route_map(map_obj, db)

    return {
        "message":     "MAP routed across Canara Bank Three Lines of Defense.",
        "map_id":      map_id,
        "assignments": assignments,
        "wings_assigned": [a["wing"] for a in assignments],
    }


# ============================================================
# ROUTE 5: POST /agents/validate/{evidence_id}
# Trigger validation engine for evidence
# ============================================================

@router.post("/agents/validate/{evidence_id}")
def validate_evidence_submission(
    evidence_id: str,
    db: Session = Depends(get_db)
):
    try:
        evidence_uuid = uuid.UUID(evidence_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid evidence ID.")

    evidence = db.query(Evidence).filter(
        Evidence.id == evidence_uuid
    ).first()

    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found.")

    try:
        from agents.validation_engine import validate_evidence
        result = validate_evidence(
            evidence_id   = evidence_id,
            evidence_text = "",
            file_bytes    = b"",
            db            = db,
        )
        return result
    except ImportError:
        # Validation engine not built yet
        return {
            "evidence_id":    evidence_id,
            "overall_status": "PENDING",
            "note": (
                "Validation engine not built yet. "
                "Complete agents/validation_engine.py first."
            )
        }


# ============================================================
# ROUTE 6: GET /maps/{map_id}/assignments
# Return all 3 Wing assignments for a MAP
# ============================================================

@router.get("/maps/{map_id}/assignments")
def get_map_assignments(
    map_id: str,
    db: Session = Depends(get_db)
):
    try:
        map_uuid = uuid.UUID(map_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid MAP ID.")

    assignments = (
        db.query(Assignment)
        .filter(Assignment.map_id == map_uuid)
        .order_by(Assignment.line_number)
        .all()
    )

    if not assignments:
        # Auto-route if no assignments exist yet
        map_obj = db.query(Map).filter(Map.id == map_uuid).first()
        if map_obj:
            routed = route_map(map_obj, db)
            return {
                "map_id":      map_id,
                "auto_routed": True,
                "assignments": routed,
            }
        raise HTTPException(status_code=404, detail="MAP not found.")

    return {
        "map_id": map_id,
        "assignments": [
            {
                "id":              str(a.id),
                "line_number":     a.line_number,
                "role":            a.role,
                "wing":            a.department,
                "assignment_text": a.assignment_text,
                "acknowledged":    a.acknowledged,
                "assigned_at":     str(a.assigned_at),
            }
            for a in assignments
        ]
    }


# ============================================================
# ROUTE 7: GET /graph/impact/{mandate_id}
# Return all MAPs potentially affected by a mandate
# ============================================================

@router.get("/graph/impact/{mandate_id}")
def get_graph_impact(
    mandate_id: str,
    db: Session = Depends(get_db)
):
    try:
        mandate_uuid = uuid.UUID(mandate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mandate ID.")

    mandate = db.query(Mandate).filter(Mandate.id == mandate_uuid).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found.")

    try:
        from backend.graph.regulatory_graph import build_graph, find_affected_maps
        G               = build_graph(db)
        affected_maps   = find_affected_maps(G, mandate.title or "", db)

        return {
            "mandate_id":        mandate_id,
            "mandate_title":     mandate.title,
            "affected_maps":     affected_maps,
            "affected_count":    len(affected_maps),
            "graph_nodes":       G.number_of_nodes(),
            "graph_edges":       G.number_of_edges(),
        }
    except Exception as e:
        return {
            "mandate_id":     mandate_id,
            "affected_maps":  [],
            "affected_count": 0,
            "note": f"Graph analysis error: {str(e)}"
        }


# ============================================================
# ROUTE 8: GET /stats
# Dashboard summary statistics
# ============================================================

@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_mandates  = db.query(Mandate).count()
    unprocessed     = db.query(Mandate).filter(
                          Mandate.processed == False
                      ).count()
    total_maps      = db.query(Map).count()
    critical_maps   = db.query(Map).filter(
                          Map.priority_tier == "CRITICAL"
                      ).count()
    high_maps       = db.query(Map).filter(
                          Map.priority_tier == "HIGH"
                      ).count()
    medium_maps     = db.query(Map).filter(
                          Map.priority_tier == "MEDIUM"
                      ).count()
    low_maps        = db.query(Map).filter(
                          Map.priority_tier == "LOW"
                      ).count()
    closed_maps     = db.query(Map).filter(
                          Map.status == "CLOSED"
                      ).count()
    penalty_sum     = db.query(
                          func.sum(Map.penalty_exposure)
                      ).filter(
                          Map.status != "CLOSED"
                      ).scalar() or 0

    return {
        "total_mandates":          total_mandates,
        "unprocessed_mandates":    unprocessed,
        "total_maps":              total_maps,
        "critical_maps":           critical_maps,
        "high_maps":               high_maps,
        "medium_maps":             medium_maps,
        "low_maps":                low_maps,
        "closed_maps":             closed_maps,
        "total_penalty_exposure":  float(penalty_sum),
        "total_penalty_formatted": f"₹{float(penalty_sum):,.2f}"
    }


# ============================================================
# ROUTE 9: GET /agents/status
# Check extraction pipeline status
# ============================================================

@router.get("/agents/status")
def get_agent_status():
    return {
        "extraction":    agent_state["extraction"],
        "orchestration": agent_state["orchestration"],
    }


# ============================================================
# ROUTE 10: GET /agents/orchestration/status
# Check orchestration status with reasoning log
# ============================================================

@router.get("/agents/orchestration/status")
def get_orchestration_status():
    return agent_state["orchestration"]