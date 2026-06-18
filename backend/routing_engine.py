"""
3-LoD Routing Engine
File: backend/routing_engine.py

Routes every MAP simultaneously across Canara Bank's
Three Lines of Defense using spaCy keyword matching
against the Canara Bank org chart.

All assignment text says Wing — never Department.
"""

import json
import os
from typing import Optional
from sqlalchemy.orm import Session
import spacy

from backend.models import Map, Assignment

# ============================================================
# LOAD RESOURCES
# ============================================================

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise OSError(
        "spaCy model not found. Run: python -m spacy download en_core_web_sm"
    )

# Load Canara Bank org chart
ORG_CHART_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "backend", "org_chart.json"
)

# Try multiple path resolutions
for path_attempt in [
    ORG_CHART_PATH,
    os.path.join(os.path.dirname(__file__), "org_chart.json"),
    "backend/org_chart.json",
    "org_chart.json",
]:
    if os.path.exists(path_attempt):
        with open(path_attempt, "r", encoding="utf-8") as f:
            ORG_CHART = json.load(f)
        break
else:
    raise FileNotFoundError(
        "org_chart.json not found. "
        "Ensure backend/org_chart.json exists."
    )

DOMAIN_MAPPING  = ORG_CHART["domain_mapping"]
FIRST_LOD_WINGS = ORG_CHART["lines_of_defense"]["first"]["wings"]
BANK_NAME       = ORG_CHART["bank_name"]

# Fixed 2nd and 3rd LoD for Canara Bank
SECOND_LOD_WING = "Compliance Wing"
THIRD_LOD_WING  = "Internal Audit Wing"


# ============================================================
# DOMAIN KEYWORD EXTRACTOR
# Uses spaCy to find regulatory domain keywords
# in the obligation text and matches to Canara Bank Wings
# ============================================================

def find_first_lod_wing(obligation_text: str) -> tuple[str, str]:
    """
    Matches obligation text against org_chart domain_mapping
    to find the responsible 1st LoD Wing.

    Returns:
        tuple: (primary_wing, domain_matched)
    """
    if not obligation_text:
        return "Operations Wing", "General"

    text_lower = obligation_text.lower()

    # Check each domain keyword against obligation text
    # Priority order matches Canara Bank penalty history
    priority_domains = [
        "CKYCR",
        "AML",
        "KYC",
        "Inoperative Account",
        "Priority Sector",
        "BSBDA",
        "Capital Adequacy",
        "NPA",
        "Cybersecurity",
        "Data Localization",
        "Credit Information",
        "FEMA",
        "CRR",
        "SLR",
        "Forex",
        "Basel",
        "Interest Rate",
        "Lending",
        "Customer Grievance",
        "Reporting",
    ]

    for domain in priority_domains:
        if domain.lower() in text_lower:
            wings = DOMAIN_MAPPING.get(domain, [])
            if wings:
                return wings[0], domain

    # spaCy NLP fallback — extract noun chunks
    doc = nlp(obligation_text[:500])

    banking_keywords = {
        "kyc":              ("Compliance Wing",          "KYC"),
        "aml":              ("Compliance Wing",          "AML"),
        "ckycr":            ("Compliance Wing",          "CKYCR"),
        "inoperative":      ("Retail Banking Wing",      "Inoperative Account"),
        "dormant":          ("Retail Banking Wing",      "Inoperative Account"),
        "capital":          ("Risk Management Wing",     "Capital Adequacy"),
        "adequacy":         ("Risk Management Wing",     "Capital Adequacy"),
        "npa":              ("Risk Management Wing",     "NPA"),
        "cyber":            ("CISO Office",              "Cybersecurity"),
        "security":         ("CISO Office",              "Cybersecurity"),
        "priority sector":  ("Commercial Banking Wing",  "Priority Sector"),
        "bsbda":            ("Retail Banking Wing",      "BSBDA"),
        "treasury":         ("Integrated Treasury Wing", "Treasury"),
        "crr":              ("Integrated Treasury Wing", "CRR"),
        "slr":              ("Integrated Treasury Wing", "SLR"),
        "forex":            ("International Banking Wing","Forex"),
        "fema":             ("International Banking Wing","FEMA"),
        "grievance":        ("Operations Wing",          "Customer Grievance"),
        "lending":          ("Retail Banking Wing",      "Lending"),
        "interest rate":    ("Financial Management Wing","Interest Rate"),
        "reporting":        ("Compliance Wing",          "Reporting"),
    }

    text_lower = obligation_text.lower()
    for keyword, (wing, domain) in banking_keywords.items():
        if keyword in text_lower:
            return wing, domain

    # Default fallback
    return "Compliance Wing", "General Compliance"


# ============================================================
# ASSIGNMENT TEXT GENERATORS
# All text says Wing — never Department
# ============================================================

def generate_line1_text(
    obligation_text:    str,
    deadline:           str,
    evidence_required:  str,
    regulatory_reference: str,
    wing_name:          str,
) -> str:
    """
    Generates 1st Line of Defense assignment text.
    Recipient: Business Wing Owner — must take action.
    """
    return (
        f"Action required — {obligation_text} "
        f"Deadline: {deadline or 'As per regulation'}. "
        f"Evidence required: {evidence_required or 'Documentary proof of compliance'}. "
        f"Reference: {regulatory_reference or 'Refer circular'}. "
        f"Assigned Wing: {wing_name}."
    )


def generate_line2_text(
    wing_name:      str,
    map_id:         str,
    mpi_score:      float,
    priority_tier:  str,
    penalty_exposure: float,
    deadline:       str,
) -> str:
    """
    Generates 2nd Line of Defense assignment text.
    Recipient: Compliance Wing — must monitor and track.
    """
    penalty_formatted = f"₹{penalty_exposure:,.2f}" if penalty_exposure else "₹0.00"
    return (
        f"Compliance Wing Monitor — MAP {map_id[:8]}... "
        f"assigned to {wing_name}. "
        f"MPI Score: {mpi_score} ({priority_tier}). "
        f"Penalty exposure: {penalty_formatted}. "
        f"Deadline: {deadline or 'As per regulation'}. "
        f"Track completion and escalate if delayed."
    )


def generate_line3_text(
    map_id:               str,
    evidence_required:    str,
    measurable_condition: str,
) -> str:
    """
    Generates 3rd Line of Defense assignment text.
    Recipient: Internal Audit Wing — must verify post-completion.
    """
    return (
        f"Internal Audit Wing — Audit queue entry for MAP {map_id[:8]}... "
        f"Schedule evidence verification post-completion. "
        f"Evidence types required: {evidence_required or 'Documentary proof'}. "
        f"Verify against measurable condition: {measurable_condition}."
    )


# ============================================================
# MAIN ROUTING FUNCTION
# ============================================================

def route_map(
    map_obj: Map,
    db:      Session,
) -> list[dict]:
    """
    Routes a MAP across all Three Lines of Defense
    for Canara Bank simultaneously.

    Creates 3 Assignment rows in the database.

    Args:
        map_obj: SQLAlchemy Map object
        db:      SQLAlchemy session

    Returns:
        List of 3 dicts, one per line of defense:
        [{"line_number": 1, "role": str, "wing": str,
          "assignment_text": str}, ...]
    """
    map_id  = str(map_obj.id)
    penalty = float(map_obj.penalty_exposure or 0)

    deadline_str = (
        str(map_obj.deadline)
        if map_obj.deadline
        else "As per regulation"
    )

    # Find 1st LoD Wing from obligation text
    first_wing, domain_matched = find_first_lod_wing(
        map_obj.obligation_text or ""
    )

    print(
        f"[Routing Engine] MAP {map_id[:8]}... "
        f"Domain: {domain_matched} → "
        f"1st LoD: {first_wing}"
    )

    # Generate all three assignment texts
    text_line1 = generate_line1_text(
        obligation_text     = map_obj.obligation_text or "",
        deadline            = deadline_str,
        evidence_required   = map_obj.evidence_required or "",
        regulatory_reference= map_obj.regulatory_reference or "",
        wing_name           = first_wing,
    )

    text_line2 = generate_line2_text(
        wing_name       = first_wing,
        map_id          = map_id,
        mpi_score       = float(map_obj.mpi_score or 0),
        priority_tier   = map_obj.priority_tier or "LOW",
        penalty_exposure= penalty,
        deadline        = deadline_str,
    )

    text_line3 = generate_line3_text(
        map_id               = map_id,
        evidence_required    = map_obj.evidence_required or "",
        measurable_condition = map_obj.measurable_condition or "",
    )

    # Build assignment objects
    assignments_data = [
        {
            "line_number":     1,
            "role":            f"{first_wing} Owner",
            "wing":            first_wing,
            "assignment_text": text_line1,
        },
        {
            "line_number":     2,
            "role":            "Compliance Wing Officer",
            "wing":            SECOND_LOD_WING,
            "assignment_text": text_line2,
        },
        {
            "line_number":     3,
            "role":            "Internal Audit Wing Officer",
            "wing":            THIRD_LOD_WING,
            "assignment_text": text_line3,
        },
    ]

    # Delete existing assignments for this MAP
    # (in case of re-routing)
    db.query(Assignment).filter(
        Assignment.map_id == map_obj.id
    ).delete()

    # Store all 3 assignments in database
    stored = []
    for a in assignments_data:
        assignment = Assignment(
            map_id          = map_obj.id,
            line_number     = a["line_number"],
            role            = a["role"],
            department      = a["wing"],
            assignment_text = a["assignment_text"],
            acknowledged    = False,
        )
        db.add(assignment)
        stored.append(a)

    db.commit()
    print(f"[Routing Engine] 3 Wing assignments stored for MAP {map_id[:8]}...")
    return stored


# ============================================================
# BATCH ROUTER
# Routes all unrouted MAPs in the database
# ============================================================

def route_all_unrouted_maps(db: Session) -> dict:
    """
    Finds all MAPs with no assignments and routes them.
    Called by POST /agents/extract after MAP creation.
    """
    from sqlalchemy import func

    # Find MAPs that have no assignments yet
    assigned_map_ids = db.query(Assignment.map_id).distinct()
    unrouted_maps = (
        db.query(Map)
        .filter(Map.id.notin_(assigned_map_ids))
        .all()
    )

    print(f"[Routing Engine] Found {len(unrouted_maps)} unrouted MAPs.")

    routed = 0
    failed = 0

    for map_obj in unrouted_maps:
        try:
            route_map(map_obj, db)
            routed += 1
        except Exception as e:
            print(f"[Routing Engine] Failed to route MAP {map_obj.id}: {e}")
            failed += 1

    return {
        "routed": routed,
        "failed": failed,
        "total":  len(unrouted_maps),
    }


# ============================================================
# STANDALONE TEST
# Run: python -m backend.routing_engine
# ============================================================

if __name__ == "__main__":
    test_obligations = [
        "All banks shall upload KYC documents to CKYCR within 7 days",
        "Banks must maintain CRR at revised rate with effect from next fortnight",
        "Achieve priority sector lending targets as per RBI Master Direction",
        "Implement enhanced transaction monitoring for AML compliance",
        "Rectify rejected data submitted to Credit Information Companies",
        "Ensure BSBDA accounts are offered without minimum balance requirement",
    ]

    print(f"\n{'='*60}")
    print(f"CANARA BANK 3-LoD ROUTING TEST")
    print(f"{'='*60}\n")

    for obligation in test_obligations:
        wing, domain = find_first_lod_wing(obligation)
        print(f"Obligation : {obligation[:60]}...")
        print(f"Domain     : {domain}")
        print(f"1st LoD    : {wing}")
        print(f"2nd LoD    : {SECOND_LOD_WING}")
        print(f"3rd LoD    : {THIRD_LOD_WING}")
        print("-" * 60)