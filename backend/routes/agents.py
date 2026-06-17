from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
import uuid

router = APIRouter(prefix="/agents", tags=["Agents"])

@router.post("/orchestrate/{mandate_id}")
def orchestrate_mandate(
    mandate_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    try:
        uuid.UUID(mandate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mandate ID.")

    from backend.models import Mandate
    mandate = db.query(Mandate).filter(
        Mandate.id == uuid.UUID(mandate_id)
    ).first()

    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found.")

    # Placeholder response until orchestrator.py is built
    return {
        "message":     "Orchestrator triggered.",
        "mandate_id":  mandate_id,
        "title":       mandate.title,
        "status":      "queued",
        "note":        "Full ReAct pipeline will process this mandate."
    }

@router.post("/extract")
def extract_all(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    return {
        "message": "Extraction triggered for all unprocessed mandates.",
        "status":  "queued"
    }

@router.post("/extract/{mandate_id}")
def extract_one(
    mandate_id: str,
    db: Session = Depends(get_db)
):
    return {
        "message":    "Extraction triggered.",
        "mandate_id": mandate_id,
        "status":     "queued"
    }

@router.get("/validate/{evidence_id}")
def validate_evidence(evidence_id: str):
    return {
        "evidence_id": evidence_id,
        "status":      "pending"
    }