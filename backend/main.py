import uuid
from pathlib import Path
from datetime import date, datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from backend.database import get_db, check_connection, Base, engine
from backend.models import Mandate, Map, Assignment, Evidence, AuditLog

from backend.routes.scrape import router as scrape_router


# ============================================================
# APP INITIALIZATION
# ============================================================

app = FastAPI(
    title="IntelliMandate API",
    description="Agentic Regulatory Intelligence & Autonomous Compliance Resolution Platform",
    version="1.0.0"
)

app.include_router(scrape_router)

# Allow Streamlit frontend to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STARTUP EVENT
# Verify database connection when server starts
# Server refuses to start if DB is unreachable
# ============================================================

@app.on_event("startup")
def on_startup():
    check_connection()
    Base.metadata.create_all(bind=engine)
    print("IntelliMandate — Canara Bank Compliance Platform — Ready.")


# ============================================================
# PYDANTIC SCHEMAS
# Request body validation for POST routes
# ============================================================

class MandateCreate(BaseModel):
    source: str
    # RBI, SEBI, IRDAI, FIU_IND, MCA, GAZETTE
    signal_type: str
    # MANDATORY_IMMEDIATE, MANDATORY_FUTURE,
    # CIRCULAR_AMENDMENT, CONSULTATION_PAPER, ADVISORY
    title: str
    raw_text: Optional[str] = None
    url: Optional[str] = None
    date_issued: Optional[date] = None
    delta_summary: Optional[str] = None


class MapCreate(BaseModel):
    mandate_id: str
    obligation_text: str
    measurable_condition: str
    deadline: Optional[date] = None
    penalty_exposure: Optional[float] = 0
    evidence_required: Optional[str] = None
    regulatory_reference: Optional[str] = None
    map_type: Optional[str] = None
    # PROCESS_CHANGE, POLICY_UPDATE, SYSTEM_CHANGE, REPORTING_OBLIGATION
    mpi_score: Optional[float] = 0
    priority_tier: Optional[str] = "LOW"
    # CRITICAL, HIGH, MEDIUM, LOW


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "running",
        "project": "IntelliMandate",
        "version": "1.0.0",
        "message": "Agentic Regulatory Intelligence Platform"
    }


@app.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Database unreachable: {str(e)}"
        )


# ============================================================
# ROUTE 1: GET /mandates
# List all mandates sorted by date_issued descending
# Optional filter by source and signal_type
# ============================================================

@app.get("/mandates", tags=["Mandates"])
def get_mandates(
    source: Optional[str] = Query(None, description="Filter by regulator: RBI, SEBI, IRDAI"),
    signal_type: Optional[str] = Query(None, description="Filter by signal type"),
    processed: Optional[bool] = Query(None, description="Filter by processed status"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    query = db.query(Mandate)

    if source:
        query = query.filter(Mandate.source == source.upper())
    if signal_type:
        query = query.filter(Mandate.signal_type == signal_type.upper())
    if processed is not None:
        query = query.filter(Mandate.processed == processed)

    mandates = query.order_by(
        desc(Mandate.date_issued)
    ).offset(offset).limit(limit).all()

    return {
        "total": query.count(),
        "limit": limit,
        "offset": offset,
        "mandates": [
            {
                "id": str(m.id),
                "source": m.source,
                "signal_type": m.signal_type,
                "title": m.title,
                "url": m.url,
                "date_issued": str(m.date_issued) if m.date_issued else None,
                "delta_summary": m.delta_summary,
                "processed": m.processed,
                "created_at": str(m.created_at)
            }
            for m in mandates
        ]
    }


# ============================================================
# ROUTE 2: POST /mandates
# Add a new mandate — called by the Monitor Agent (Member B)
# ============================================================

@app.post("/mandates", tags=["Mandates"], status_code=201)
def create_mandate(
    payload: MandateCreate,
    db: Session = Depends(get_db)
):
    mandate = Mandate(
        source=payload.source.upper(),
        signal_type=payload.signal_type.upper(),
        title=payload.title,
        raw_text=payload.raw_text,
        url=payload.url,
        date_issued=payload.date_issued,
        delta_summary=payload.delta_summary,
        processed=False
    )

    db.add(mandate)
    db.commit()
    db.refresh(mandate)

    return {
        "message": "Mandate created successfully.",
        "mandate_id": str(mandate.id),
        "source": mandate.source,
        "signal_type": mandate.signal_type,
        "title": mandate.title,
        "processed": mandate.processed,
        "created_at": str(mandate.created_at)
    }


# ============================================================
# ROUTE 3: GET /maps
# List all MAPs sorted by mpi_score descending
# This is the main compliance dashboard feed
# ============================================================

@app.get("/maps", tags=["MAPs"])
def get_maps(
    priority_tier: Optional[str] = Query(None, description="CRITICAL, HIGH, MEDIUM, LOW"),
    status: Optional[str] = Query(None, description="OPEN, IN_PROGRESS, CLOSED, BREACHED"),
    map_type: Optional[str] = Query(None, description="PROCESS_CHANGE, POLICY_UPDATE, etc."),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    query = db.query(Map)

    if priority_tier:
        query = query.filter(Map.priority_tier == priority_tier.upper())
    if status:
        query = query.filter(Map.status == status.upper())
    if map_type:
        query = query.filter(Map.map_type == map_type.upper())

    # Always sorted by MPI score descending
    # Highest rupee exposure always at the top
    maps = query.order_by(
        desc(Map.mpi_score)
    ).offset(offset).limit(limit).all()

    return {
        "total": query.count(),
        "limit": limit,
        "offset": offset,
        "maps": [
            {
                "id": str(m.id),
                "mandate_id": str(m.mandate_id),
                "obligation_text": m.obligation_text,
                "mandate_title": db.query(Mandate)
                                   .filter(Mandate.id == m.mandate_id)
                                   .first().title if m.mandate_id else None,

                "mandate_source": db.query(Mandate)
                                    .filter(Mandate.id == m.mandate_id)
                                    .first().source if m.mandate_id else None,

                "measurable_condition": m.measurable_condition,
                "deadline": str(m.deadline) if m.deadline else None,
                "penalty_exposure": float(m.penalty_exposure),
                "penalty_exposure_formatted": f"₹{float(m.penalty_exposure):,.2f}",
                "evidence_required": m.evidence_required,
                "regulatory_reference": m.regulatory_reference,
                "map_type": m.map_type,
                "mpi_score": float(m.mpi_score),
                "priority_tier": m.priority_tier,
                "status": m.status,
                "created_at": str(m.created_at)
            }
            for m in maps
        ]
    }


# ============================================================
# ROUTE 4: GET /maps/{id}
# Single MAP detail with all assignments
# ============================================================

@app.get("/maps/{map_id}", tags=["MAPs"])
def get_map(
    map_id: str,
    db: Session = Depends(get_db)
):
    try:
        map_uuid = uuid.UUID(map_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid MAP ID format.")

    m = db.query(Map).filter(Map.id == map_uuid).first()

    if not m:
        raise HTTPException(status_code=404, detail="MAP not found.")

    # Fetch the parent mandate for context
    mandate = db.query(Mandate).filter(
        Mandate.id == m.mandate_id
    ).first()

    # Fetch all three line assignments
    assignments = db.query(Assignment).filter(
        Assignment.map_id == map_uuid
    ).order_by(Assignment.line_number).all()

    # Fetch all evidence submissions
    evidence_list = db.query(Evidence).filter(
        Evidence.map_id == map_uuid
    ).order_by(desc(Evidence.upload_date)).all()

    return {
        "id": str(m.id),
        "obligation_text": m.obligation_text,
        "measurable_condition": m.measurable_condition,
        "deadline": str(m.deadline) if m.deadline else None,
        "penalty_exposure": float(m.penalty_exposure),
        "penalty_exposure_formatted": f"₹{float(m.penalty_exposure):,.2f}",
        "evidence_required": m.evidence_required,
        "regulatory_reference": m.regulatory_reference,
        "map_type": m.map_type,
        "mpi_score": float(m.mpi_score),
        "priority_tier": m.priority_tier,
        "status": m.status,
        "created_at": str(m.created_at),
        "mandate": {
            "id": str(mandate.id),
            "source": mandate.source,
            "signal_type": mandate.signal_type,
            "title": mandate.title,
            "url": mandate.url,
            "date_issued": str(mandate.date_issued) if mandate.date_issued else None
        } if mandate else None,
        "assignments": [
            {
                "id": str(a.id),
                "mandate_id":    str(m.mandate_id) if m.mandate_id else None,
                "mandate_title": mandate.title if mandate else None,
                "line_number": a.line_number,
                "role": a.role,
                "department": a.department,
                "assignment_text": a.assignment_text,
                "acknowledged": a.acknowledged,
                "assigned_at": str(a.assigned_at)
            }
            for a in assignments
        ],
        "evidence_submissions": [
            {
                "id": str(e.id),
                "file_name": e.file_name,
                "file_hash": e.file_hash,
                "upload_date": str(e.upload_date),
                "document_date": str(e.document_date) if e.document_date else None,
                "semantic_score": float(e.semantic_score) if e.semantic_score else None,
                "gate_1_status": e.gate_1_status,
                "gate_2_status": e.gate_2_status,
                "gate_3_status": e.gate_3_status,
                "gate_4_status": e.gate_4_status,
                "gate_status": e.gate_status,
                "failure_reason": e.failure_reason
            }
            for e in evidence_list
        ]
    }


# ============================================================
# ROUTE 5: POST /maps/{id}/evidence
# Upload evidence document against a MAP
# File is received and stored — validation gates run separately
# via the Validation Agent (Member B)
# ============================================================

@app.post("/maps/{map_id}/evidence", tags=["Evidence"], status_code=201)
async def upload_evidence(
    map_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        map_uuid = uuid.UUID(map_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid MAP ID format.")

    m = db.query(Map).filter(Map.id == map_uuid).first()
    if not m:
        raise HTTPException(status_code=404, detail="MAP not found.")

    if m.status == "CLOSED":
        raise HTTPException(status_code=400, detail="This MAP is already closed.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    import hashlib
    file_hash = hashlib.sha256(file_bytes).hexdigest()

    # Extract text from evidence document
    evidence_text = ""
    if file.filename.lower().endswith(".pdf"):
        try:
            import fitz
            import io
            doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
            evidence_text = "\n".join(p.get_text("text") for p in doc)
            doc.close()
        except Exception as e:
            print(f"[Evidence] PDF extraction error: {e}")
    else:
        try:
            evidence_text = file_bytes.decode("utf-8", errors="ignore")
        except Exception:
            evidence_text = ""

    # Create evidence record
    evidence = Evidence(
        map_id      = map_uuid,
        file_name   = file.filename,
        file_hash   = file_hash,
        gate_status = "PENDING",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    # Run all four gates synchronously — using the REAL extracted text
    from agents.validation_engine import validate_evidence
    result = validate_evidence(
        evidence_id   = str(evidence.id),
        evidence_text = evidence_text,
        file_bytes    = file_bytes,
        db            = db,
    )

    return {
        "message":       "Evidence uploaded and validated.",
        "evidence_id":   str(evidence.id),
        "map_id":        map_id,
        "file_name":     file.filename,
        "file_hash":     file_hash,
        **result,
    }

# ============================================================
# ROUTE 6: GET /audit
# List all closed MAPs with their compliance certificates
# ============================================================

@app.get("/audit", tags=["Audit"])
def get_audit_log(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)

    audit_entries = query.order_by(
        desc(AuditLog.closed_at)
    ).offset(offset).limit(limit).all()

    return {
        "total": query.count(),
        "limit": limit,
        "offset": offset,
        "audit_log": [
            {
                "id": str(a.id),
                "map_id": str(a.map_id),
                "evidence_id": str(a.evidence_id),
                "closed_at": str(a.closed_at),
                "semantic_score": float(a.semantic_score),
                "certificate": a.certificate_json,
                "created_at": str(a.created_at)
            }
            for a in audit_entries
        ]
    }


# ============================================================
# ROUTE 7: PATCH /maps/{id}/status
# Update MAP status — called by Validation Agent after gates pass
# ============================================================

@app.patch("/maps/{map_id}/status", tags=["MAPs"])
def update_map_status(
    map_id: str,
    status: str = Query(..., description="OPEN, IN_PROGRESS, PENDING_EVIDENCE, CLOSED, BREACHED"),
    db: Session = Depends(get_db)
):
    valid_statuses = ["OPEN", "IN_PROGRESS", "PENDING_EVIDENCE", "CLOSED", "BREACHED"]

    if status.upper() not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    try:
        map_uuid = uuid.UUID(map_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid MAP ID format.")

    m = db.query(Map).filter(Map.id == map_uuid).first()
    if not m:
        raise HTTPException(status_code=404, detail="MAP not found.")

    m.status = status.upper()
    db.commit()

    return {
        "message": f"MAP status updated to {status.upper()}",
        "map_id": map_id,
        "status": m.status
    }


# ============================================================
# ROUTE 8: POST /maps
# Create a MAP directly — called by Extraction Agent (Member B)
# ============================================================

@app.post("/maps", tags=["MAPs"], status_code=201)
def create_map(
    payload: MapCreate,
    db: Session = Depends(get_db)
):
    try:
        mandate_uuid = uuid.UUID(payload.mandate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid mandate_id format.")

    mandate = db.query(Mandate).filter(
        Mandate.id == mandate_uuid
    ).first()
    if not mandate:
        raise HTTPException(status_code=404, detail="Mandate not found.")

    m = Map(
        mandate_id=mandate_uuid,
        obligation_text=payload.obligation_text,
        measurable_condition=payload.measurable_condition,
        deadline=payload.deadline,
        penalty_exposure=payload.penalty_exposure or 0,
        evidence_required=payload.evidence_required,
        regulatory_reference=payload.regulatory_reference,
        map_type=payload.map_type,
        mpi_score=payload.mpi_score or 0,
        priority_tier=payload.priority_tier or "LOW",
        status="OPEN"
    )

    db.add(m)

    # Mark the parent mandate as processed
    mandate.processed = True
    db.commit()
    db.refresh(m)

    return {
        "message": "MAP created successfully.",
        "map_id": str(m.id),
        "mandate_id": str(m.mandate_id),
        "priority_tier": m.priority_tier,
        "mpi_score": float(m.mpi_score),
        "status": m.status,
        "created_at": str(m.created_at)
    }

from backend.routes.scrape import router as scrape_router
app.include_router(scrape_router)

@app.get("/stats", tags=["Stats"])
def get_stats(db: Session = Depends(get_db)):
    from sqlalchemy import func
    from backend.models import Mandate, Map

    total_mandates = db.query(Mandate).count()
    unprocessed    = db.query(Mandate).filter(
                         Mandate.processed == False
                     ).count()
    total_maps     = db.query(Map).count()
    critical_maps  = db.query(Map).filter(
                         Map.priority_tier == "CRITICAL"
                     ).count()
    high_maps      = db.query(Map).filter(
                         Map.priority_tier == "HIGH"
                     ).count()
    medium_maps    = db.query(Map).filter(
                         Map.priority_tier == "MEDIUM"
                     ).count()
    low_maps       = db.query(Map).filter(
                         Map.priority_tier == "LOW"
                     ).count()
    closed_maps    = db.query(Map).filter(
                         Map.status == "CLOSED"
                     ).count()
    penalty_sum    = db.query(
                         func.sum(Map.penalty_exposure)
                     ).filter(
                         Map.status != "CLOSED"
                     ).scalar() or 0

    return {
        "total_mandates":       total_mandates,
        "unprocessed_mandates": unprocessed,
        "total_maps":           total_maps,
        "critical_maps":        critical_maps,
        "high_maps":            high_maps,
        "medium_maps":          medium_maps,
        "low_maps":             low_maps,
        "closed_maps":          closed_maps,
        "total_penalty_exposure": float(penalty_sum),
        "total_penalty_formatted": f"₹{float(penalty_sum):,.2f}"
    }

from backend.routes.agents import router as agents_router
app.include_router(agents_router)