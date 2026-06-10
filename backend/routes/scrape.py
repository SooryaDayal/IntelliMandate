"""
Scraper Routes
File: backend/routes/scrape.py

Exposes all scraper components as FastAPI background tasks.
Triggers are HTTP POST calls — results stored in PostgreSQL.

Endpoints:
    POST /scrape/rbi          → Full pipeline: scrape → classify → delta → store
    POST /scrape/rbi/quick    → Scrape titles and metadata only (no PDF download)
    GET  /scrape/status       → Returns status of last scrape run
    GET  /scrape/history      → Returns list of all mandates stored so far
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models import Mandate

# Scraper components
from backend.scrapers.rbi_scraper   import fetch_rbi_circulars
from backend.scrapers.pdf_extractor import extract_circular_text
from backend.scrapers.classifier    import classify_circular
from backend.scrapers.delta_engine  import (
    run_delta_analysis,
    get_previous_version_text,
    format_delta_summary,
)

router = APIRouter(prefix="/scrape", tags=["Scraper"])


# ============================================================
# SCRAPE STATE
# Tracks the status of the most recent scrape run
# Simple in-memory state — resets on server restart
# For production, move this to Redis
# ============================================================

scrape_state = {
    "status":       "idle",          # idle | running | complete | error
    "started_at":   None,
    "completed_at": None,
    "circulars_found":    0,
    "circulars_stored":   0,
    "circulars_skipped":  0,
    "last_error":   None,
    "source":       None,
}


# ============================================================
# BACKGROUND TASK: FULL PIPELINE
# scrape → extract text → classify → delta → store in DB
# ============================================================

def run_full_scrape_pipeline(
    db: Session,
    max_circulars: int = 20,
    source: str = "RBI"
) -> None:
    """
    Full scraping pipeline run as a FastAPI background task.

    Steps for each circular:
        1. Fetch circular list from RBI index page
        2. Extract full text from PDF or HTML
        3. Classify signal type using classifier
        4. Run delta analysis if CIRCULAR_AMENDMENT
        5. Store in mandates table
        6. Skip duplicates (same URL already in DB)
    """
    global scrape_state

    scrape_state["status"]       = "running"
    scrape_state["started_at"]   = datetime.now(timezone.utc).isoformat()
    scrape_state["completed_at"] = None
    scrape_state["circulars_found"]   = 0
    scrape_state["circulars_stored"]  = 0
    scrape_state["circulars_skipped"] = 0
    scrape_state["last_error"]   = None
    scrape_state["source"]       = source

    print(f"\n[Scrape Pipeline] Starting full pipeline. Max: {max_circulars}")

    try:
        # ── Step 1: Fetch circular list ──
        circulars = fetch_rbi_circulars(max_circulars=max_circulars)
        scrape_state["circulars_found"] = len(circulars)

        if not circulars:
            print("[Scrape Pipeline] No circulars returned from scraper.")
            scrape_state["status"] = "complete"
            scrape_state["completed_at"] = datetime.now(timezone.utc).isoformat()
            return

        print(f"[Scrape Pipeline] Processing {len(circulars)} circulars...")

        for i, circular in enumerate(circulars, 1):
            title      = circular.get("title", "")
            url        = circular.get("url", "")
            ref_number = circular.get("ref_number", "")

            print(f"\n[Scrape Pipeline] [{i}/{len(circulars)}] {title[:60]}...")

            # ── Skip duplicates ──
            # Check if this URL is already stored
            existing = db.query(Mandate).filter(
                Mandate.url == url
            ).first()

            if existing:
                print(f"[Scrape Pipeline] Already in DB. Skipping.")
                scrape_state["circulars_skipped"] += 1
                continue

            # ── Step 2: Extract full text ──
            raw_text = extract_circular_text(circular) or ""

            # ── Step 3: Classify signal type ──
            classification = classify_circular(
                title      = title,
                text       = raw_text,
                ref_number = ref_number,
            )

            signal_type = classification["signal_type"]
            print(
                f"[Scrape Pipeline] Classified as: {signal_type} "
                f"({classification['confidence']} confidence)"
            )

            # ── Step 4: Delta analysis for amendments ──
            delta_summary_text = None

            if signal_type == "CIRCULAR_AMENDMENT" and raw_text:
                print("[Scrape Pipeline] Running delta analysis...")

                # Look for previous version of this circular series in DB
                previous_text = get_previous_version_text(
                    db         = db,
                    ref_number = ref_number,
                    current_mandate_id = str(uuid.uuid4()),
                    # Placeholder ID — mandate not saved yet
                )

                delta_result = run_delta_analysis(
                    current_text  = raw_text,
                    previous_text = previous_text,
                    ref_number    = ref_number,
                )

                if delta_result.get("has_changes"):
                    delta_summary_text = format_delta_summary(delta_result)
                    print(
                        f"[Scrape Pipeline] Delta: "
                        f"{delta_result['added_count']} added, "
                        f"{delta_result['removed_count']} removed, "
                        f"significance: {delta_result['significance']}"
                    )

            # ── Step 5: Store in database ──
            mandate = Mandate(
                source       = circular.get("source", "RBI").upper(),
                signal_type  = signal_type,
                title        = title,
                raw_text     = raw_text if raw_text else None,
                url          = url,
                date_issued  = circular.get("date"),
                delta_summary = delta_summary_text,
                processed    = False,
                # Member B's extraction agent will flip this to True
                # after creating MAPs from this mandate
            )

            db.add(mandate)
            db.commit()
            db.refresh(mandate)

            scrape_state["circulars_stored"] += 1
            print(f"[Scrape Pipeline] Stored mandate ID: {mandate.id}")

        # ── Complete ──
        scrape_state["status"]       = "complete"
        scrape_state["completed_at"] = datetime.now(timezone.utc).isoformat()

        print(
            f"\n[Scrape Pipeline] Done. "
            f"Stored: {scrape_state['circulars_stored']} | "
            f"Skipped: {scrape_state['circulars_skipped']} | "
            f"Total found: {scrape_state['circulars_found']}"
        )

    except Exception as e:
        scrape_state["status"]     = "error"
        scrape_state["last_error"] = str(e)
        scrape_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Scrape Pipeline] ERROR: {e}")
        db.rollback()


# ============================================================
# BACKGROUND TASK: QUICK SCRAPE (metadata only, no PDFs)
# ============================================================

def run_quick_scrape(
    db: Session,
    max_circulars: int = 50
) -> None:
    """
    Quick scrape — fetches titles, dates, URLs, ref numbers only.
    Does NOT download PDFs or extract text.
    Useful for getting a fast overview of new circulars.
    Classification uses title-only (no body text scoring).
    """
    global scrape_state

    scrape_state["status"]     = "running"
    scrape_state["started_at"] = datetime.now(timezone.utc).isoformat()
    scrape_state["last_error"] = None
    scrape_state["source"]     = "RBI_QUICK"

    print(f"\n[Quick Scrape] Starting quick scrape. Max: {max_circulars}")

    try:
        circulars = fetch_rbi_circulars(max_circulars=max_circulars)
        scrape_state["circulars_found"]  = len(circulars)
        scrape_state["circulars_stored"] = 0
        scrape_state["circulars_skipped"] = 0

        for circular in circulars:
            url = circular.get("url", "")

            # Skip duplicates
            existing = db.query(Mandate).filter(Mandate.url == url).first()
            if existing:
                scrape_state["circulars_skipped"] += 1
                continue

            # Classify by title only — no PDF download
            classification = classify_circular(
                title      = circular.get("title", ""),
                ref_number = circular.get("ref_number", ""),
            )

            mandate = Mandate(
                source      = "RBI",
                signal_type = classification["signal_type"],
                title       = circular.get("title", ""),
                raw_text    = None,
                # Text not extracted in quick mode
                url         = url,
                date_issued = circular.get("date"),
                processed   = False,
            )

            db.add(mandate)
            db.commit()
            scrape_state["circulars_stored"] += 1

        scrape_state["status"]       = "complete"
        scrape_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Quick Scrape] Done. Stored: {scrape_state['circulars_stored']}")

    except Exception as e:
        scrape_state["status"]     = "error"
        scrape_state["last_error"] = str(e)
        scrape_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"[Quick Scrape] ERROR: {e}")
        db.rollback()


# ============================================================
# ROUTE 1: POST /scrape/rbi
# Triggers full pipeline as a background task
# Returns immediately — pipeline runs in background
# ============================================================

@router.post("/rbi")
def trigger_rbi_scrape(
    background_tasks: BackgroundTasks,
    max_circulars: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of circulars to process"
    ),
    db: Session = Depends(get_db)
):
    """
    Triggers the full RBI scraping pipeline as a background task.

    Pipeline:
        fetch circulars → extract PDF text → classify → delta → store in DB

    Returns immediately with a confirmation message.
    Poll GET /scrape/status to check progress.
    """
    if scrape_state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=(
                "A scrape is already running. "
                "Poll GET /scrape/status to check progress."
            )
        )

    background_tasks.add_task(
        run_full_scrape_pipeline,
        db=db,
        max_circulars=max_circulars,
        source="RBI"
    )

    return {
        "message":       "RBI scrape pipeline started in background.",
        "max_circulars": max_circulars,
        "status":        "running",
        "poll_url":      "/scrape/status",
        "started_at":    datetime.now(timezone.utc).isoformat(),
        "note": (
            "Full pipeline: fetch → extract PDF → classify → delta → store. "
            "This may take several minutes depending on max_circulars."
        )
    }


# ============================================================
# ROUTE 2: POST /scrape/rbi/quick
# Quick metadata-only scrape — no PDF downloads
# ============================================================

@router.post("/rbi/quick")
def trigger_quick_scrape(
    background_tasks: BackgroundTasks,
    max_circulars: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of circulars to scan"
    ),
    db: Session = Depends(get_db)
):
    """
    Quick scrape — titles, dates, URLs only. No PDF extraction.
    Much faster than the full pipeline.
    Classification uses title patterns only.
    """
    if scrape_state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="A scrape is already running. Check GET /scrape/status."
        )

    background_tasks.add_task(
        run_quick_scrape,
        db=db,
        max_circulars=max_circulars
    )

    return {
        "message":       "Quick RBI scrape started in background.",
        "max_circulars": max_circulars,
        "status":        "running",
        "poll_url":      "/scrape/status",
        "started_at":    datetime.now(timezone.utc).isoformat(),
        "note":          "Metadata only — no PDF extraction. Fast scan."
    }


# ============================================================
# ROUTE 3: GET /scrape/status
# Returns current state of the scrape pipeline
# ============================================================

@router.get("/status")
def get_scrape_status():
    """
    Returns the current status of the scraping pipeline.

    Poll this endpoint after triggering POST /scrape/rbi.
    Status transitions: idle → running → complete | error
    """
    return {
        "status":             scrape_state["status"],
        "source":             scrape_state["source"],
        "started_at":         scrape_state["started_at"],
        "completed_at":       scrape_state["completed_at"],
        "circulars_found":    scrape_state["circulars_found"],
        "circulars_stored":   scrape_state["circulars_stored"],
        "circulars_skipped":  scrape_state["circulars_skipped"],
        "last_error":         scrape_state["last_error"],
    }


# ============================================================
# ROUTE 4: GET /scrape/history
# Returns all mandates stored in the database
# ============================================================

@router.get("/history")
def get_scrape_history(
    signal_type: Optional[str] = Query(None),
    source:      Optional[str] = Query(None),
    limit:       int = Query(default=50, le=200),
    offset:      int = Query(default=0),
    db: Session = Depends(get_db)
):
    """
    Returns all mandates stored in the database.
    Useful for Member C's Streamlit dashboard to show
    the history of all scraped circulars.
    """
    query = db.query(Mandate)

    if signal_type:
        query = query.filter(
            Mandate.signal_type == signal_type.upper()
        )
    if source:
        query = query.filter(
            Mandate.source == source.upper()
        )

    total     = query.count()
    mandates  = query.order_by(
        desc(Mandate.date_issued)
    ).offset(offset).limit(limit).all()

    return {
        "total":  total,
        "limit":  limit,
        "offset": offset,
        "mandates": [
            {
                "id":            str(m.id),
                "source":        m.source,
                "signal_type":   m.signal_type,
                "title":         m.title,
                "url":           m.url,
                "date_issued":   str(m.date_issued) if m.date_issued else None,
                "delta_summary": m.delta_summary,
                "processed":     m.processed,
                "has_raw_text":  bool(m.raw_text),
                "created_at":    str(m.created_at),
            }
            for m in mandates
        ]
    }