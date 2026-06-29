"""
MAP Extraction Agent
File: agents/extraction_agent.py

Extracts Measurable Action Points from RBI circular text
using spaCy dependency parsing and regex pattern matching.

No FinBERT required. No external API. No internet.
Works with spaCy en_core_web_sm which is already installed.

Run: python -m agents.extraction_agent
"""

import re
import uuid
from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
import spacy

from backend.models import Mandate, Map
from agents.mpi_engine import compute_mpi_score

# ============================================================
# LOAD spaCy MODEL
# ============================================================

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise OSError(
        "spaCy model not found. Run: python -m spacy download en_core_web_sm"
    )


# ============================================================
# OBLIGATION KEYWORDS
# Sentences containing these words are likely obligations
# ============================================================

OBLIGATION_TRIGGERS = [
    "shall", "must", "required to", "are required",
    "is required", "should", "will ensure", "shall ensure",
    "mandated", "obligated", "comply", "compliance",
    "submit", "maintain", "report", "upload", "implement",
    "achieve", "ensure", "adhere", "follow", "furnish",
    "provide", "disclose", "notify", "rectify", "update",
]

# Sentences with these words are likely informational — skip them
SKIP_TRIGGERS = [
    "it is clarified", "it may be noted", "it is observed",
    "this circular", "dated", "reference is invited",
    "as you are aware", "it is informed", "is pleased to",
    "with a view to", "background", "preamble",
    "in this regard", "it may be recalled",
]

# ============================================================
# MONEY EXTRACTION
# Converts strings like ₹1 crore, Rs.25 lakh to float
# ============================================================

def extract_money(text: str) -> float:
    """Extract the largest penalty amount mentioned in text."""
    text_lower = text.lower().replace(",", "")
    pattern = re.compile(
        r"(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)\s*"
        r"(crore|cr|lakh|lac|lakhs|lacs|million|thousand)?",
        re.I,
    )
    values = []
    for amount_str, unit in pattern.findall(text_lower):
        try:
            amount = float(amount_str)
            unit = (unit or "").lower()
            if unit in ("crore", "cr"):
                values.append(amount * 10_000_000)
            elif unit in ("lakh", "lac", "lakhs", "lacs"):
                values.append(amount * 100_000)
            elif unit == "million":
                values.append(amount * 1_000_000)
            elif unit == "thousand":
                values.append(amount * 1_000)
            elif amount > 1000:
                values.append(amount)
        except ValueError:
            continue
    return max(values) if values else 0.0


# ============================================================
# DATE EXTRACTION
# Finds deadlines in text like "by September 30, 2026"
# ============================================================

def extract_deadline(text: str) -> Optional[date]:
    """Extract the most relevant deadline date from text."""
    doc = nlp(text[:1000])

    date_entities = [
        ent.text for ent in doc.ents
        if ent.label_ == "DATE"
    ]

    date_formats = [
        "%B %d, %Y", "%B %d %Y", "%d %B %Y",
        "%b %d, %Y", "%b %d %Y", "%d %b %Y",
        "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y",
    ]

    for date_str in date_entities:
        date_str = date_str.strip()
        for fmt in date_formats:
            try:
                parsed = datetime.strptime(date_str, fmt).date()
                if parsed.year >= 2024:
                    return parsed
            except ValueError:
                continue

    # Check for relative deadlines
    relative = re.search(
        r"within\s+(\d+)\s+(day|week|month)",
        text.lower()
    )
    if relative:
        n = int(relative.group(1))
        unit = relative.group(2)
        from datetime import timedelta
        today = datetime.now(timezone.utc).date()
        if unit == "day":
            return today + timedelta(days=n)
        elif unit == "week":
            return today + timedelta(weeks=n)
        elif unit == "month":
            return today + timedelta(days=n * 30)

    return None


# ============================================================
# CLAUSE REFERENCE EXTRACTION
# ============================================================

def extract_clause_reference(text: str) -> str:
    """Extract regulatory clause references from text."""
    patterns = [
        r"(Clause\s+[\d]+[\w().-]*)",
        r"(Section\s+[\d]+[\w().-]*)",
        r"(Paragraph\s+[\d]+[\w().-]*)",
        r"(Rule\s+[\d]+[\w().-]*)",
        r"(Article\s+[\d]+[\w().-]*)",
        r"(Para\s+[\d]+[\w().-]*)",
        r"(RBI/\d{4}-\d{4}/[\w./]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


# ============================================================
# MAP TYPE DETECTION
# ============================================================

def detect_map_type(text: str) -> str:
    """Detect the type of compliance change required."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["report", "submit", "furnish", "notify", "disclose"]):
        return "REPORTING_OBLIGATION"
    if any(w in text_lower for w in ["system", "software", "platform", "portal", "upload", "digital"]):
        return "SYSTEM_CHANGE"
    if any(w in text_lower for w in ["policy", "board", "approval", "framework", "directive"]):
        return "POLICY_UPDATE"
    return "PROCESS_CHANGE"


# ============================================================
# MEASURABLE CONDITION GENERATOR
# Creates a verifiable completion condition from obligation text
# ============================================================

def generate_measurable_condition(obligation: str, title: str) -> str:
    """
    Derives a machine-verifiable measurable condition
    from the obligation sentence and circular title.
    """
    ob_lower = obligation.lower()
    title_lower = title.lower()

    # KYC / CKYCR
    if "ckycr" in ob_lower or "central kyc" in ob_lower:
        return "100% of customer KYC records uploaded to CKYCR with zero rejected uploads pending beyond 7 days"

    if "kyc" in ob_lower:
        return "100% of accounts have valid, updated KYC records as per RBI Master Direction"

    # Priority Sector
    if "priority sector" in ob_lower or "psl" in ob_lower:
        return "Priority sector lending constitutes minimum 40% of Adjusted Net Bank Credit"

    # CRR/SLR
    if "crr" in ob_lower or "cash reserve ratio" in ob_lower:
        return "CRR maintained at prescribed rate with zero shortfall on any reporting day"
    if "slr" in ob_lower or "statutory liquidity" in ob_lower:
        return "SLR maintained at prescribed level with zero shortfall"

    # AML/PMLA
    if "aml" in ob_lower or "pmla" in ob_lower or "suspicious transaction" in ob_lower:
        return "100% of suspicious transactions reported to FIU-IND within 7 days of detection"

    # Credit Information / CIC
    if "credit information" in ob_lower or "cic" in ob_lower or "cibil" in ob_lower:
        return "Zero CIC rejection reports pending beyond 7 days in the data upload system"

    # Inoperative accounts
    if "inoperative" in ob_lower or "dormant" in ob_lower:
        return "100% of accounts with customer transactions in last 2 years reclassified as operative"

    # BSBDA
    if "bsbda" in ob_lower or "basic savings" in ob_lower:
        return "Zero instances of BSBDA denial or minimum balance imposition at any branch"

    # Interest rate
    if "interest rate" in ob_lower:
        return "Updated interest rates displayed at all branches and website within 24 hours of revision"

    # Reporting obligation
    if "report" in ob_lower or "submit" in ob_lower or "furnish" in ob_lower:
        return f"Report submitted to regulator within prescribed timeline with zero overdue submissions"

    # Cybersecurity
    if "cyber" in ob_lower or "cert-in" in ob_lower or "incident" in ob_lower:
        return "100% of qualifying cyber incidents reported to CERT-In within 6 hours with 180-day log retention"

    # FEMA / Forex
    if "fema" in ob_lower or "forex" in ob_lower or "foreign exchange" in ob_lower:
        return "All FEMA reporting obligations fulfilled within prescribed timelines with zero overdue submissions"

    # Generic fallback — use the obligation text itself as the condition
    condition = obligation.strip()
    if len(condition) > 200:
        condition = condition[:200] + "..."
    return f"Full compliance achieved: {condition}"


# ============================================================
# EVIDENCE REQUIRED GENERATOR
# ============================================================

def generate_evidence_required(map_type: str, obligation: str) -> str:
    """Suggests what evidence is needed to prove compliance."""
    ob_lower = obligation.lower()

    if "ckycr" in ob_lower or "kyc" in ob_lower:
        return "CKYCR upload confirmation report, pending rejection queue screenshot"
    if "priority sector" in ob_lower:
        return "PSLE return submitted to RBI, sector-wise lending portfolio report"
    if "crr" in ob_lower or "slr" in ob_lower:
        return "Reserve maintenance certificate, RBI fortnightly return acknowledgement"
    if "aml" in ob_lower or "suspicious" in ob_lower:
        return "FIU-IND submission acknowledgement, transaction monitoring audit report"
    if "credit information" in ob_lower:
        return "CIC upload confirmation, zero-pending rejection report"
    if "inoperative" in ob_lower:
        return "Account reclassification report, branch compliance certificates"
    if "interest rate" in ob_lower:
        return "Branch display photographs, website screenshot with timestamp"
    if "cyber" in ob_lower:
        return "CERT-In incident reporting acknowledgements, ICT log retention audit report"
    if "report" in ob_lower or "submit" in ob_lower:
        return "Submitted report copy, regulator acknowledgement receipt"

    if map_type == "POLICY_UPDATE":
        return "Board approved policy document, implementation circular"
    if map_type == "SYSTEM_CHANGE":
        return "System implementation report, UAT sign-off, go-live confirmation"
    if map_type == "REPORTING_OBLIGATION":
        return "Submitted report copy, regulator acknowledgement"
    return "Documentary proof of compliance, authorized sign-off"


# ============================================================
# SENTENCE SPLITTER
# Splits circular text into clean sentences
# ============================================================

def split_into_sentences(text: str) -> list[str]:
    """
    Splits circular text into sentences using spaCy.
    Filters out very short or very long sentences.
    """
    # Process first 10000 chars — enough for obligation extraction
    doc = nlp(text[:10000])
    sentences = []

    for sent in doc.sents:
        sent_text = sent.text.strip()

        # Skip too short
        if len(sent_text) < 30:
            continue

        # Skip too long (likely a table or list dump)
        if len(sent_text) > 800:
            continue

        # Skip pure numbers/dates/headers
        if re.match(r"^[\d\s.,:;-]+$", sent_text):
            continue

        sentences.append(sent_text)

    return sentences


# ============================================================
# OBLIGATION SENTENCE DETECTOR
# ============================================================

def is_obligation_sentence(sentence: str) -> bool:
    """
    Returns True if the sentence likely contains
    a compliance obligation.
    Uses keyword matching — fast and reliable.
    """
    sent_lower = sentence.lower()

    # Skip sentences with informational markers
    for skip in SKIP_TRIGGERS:
        if skip in sent_lower:
            return False

    # Accept sentences with obligation markers
    for trigger in OBLIGATION_TRIGGERS:
        if trigger in sent_lower:
            return True

    return False


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_maps_from_text(
    title: str,
    text: str,
    ref_number: str = "",
    source: str = "RBI",
) -> list[dict]:
    """
    Extracts MAP objects from circular text using spaCy.
    No FinBERT. No external API. Fully offline.

    Returns list of MAP dicts ready for DB storage.
    """
    if not text or len(text.strip()) < 100:
        print("[Extraction] Text too short to extract MAPs.")
        return []

    print(f"[Extraction] Processing: {title[:60]}...")

    sentences = split_into_sentences(text)
    print(f"[Extraction] Found {len(sentences)} sentences.")

    # Extract global context from full text
    global_penalty = extract_money(text)
    global_deadline = extract_deadline(text)
    global_clause = extract_clause_reference(text)

    maps = []
    seen_obligations = set()

    for sentence in sentences:
        if not is_obligation_sentence(sentence):
            continue

        # Deduplicate by first 80 chars
        key = sentence[:80].lower()
        if key in seen_obligations:
            continue
        seen_obligations.add(key)

        # Extract sentence-level entities
        sentence_penalty  = extract_money(sentence) or global_penalty
        sentence_deadline = extract_deadline(sentence) or global_deadline
        sentence_clause   = extract_clause_reference(sentence) or global_clause
        map_type          = detect_map_type(sentence)
        condition         = generate_measurable_condition(sentence, title)
        evidence          = generate_evidence_required(map_type, sentence)

        maps.append({
            "obligation_text":      sentence.strip(),
            "measurable_condition": condition,
            "deadline":             sentence_deadline,
            "penalty_exposure":     sentence_penalty,
            "evidence_required":    evidence,
            "regulatory_reference": sentence_clause or ref_number,
            "map_type":             map_type,
        })

    # Cap at 5 MAPs per circular to avoid noise
    maps = maps[:5]

    print(f"[Extraction] Extracted {len(maps)} obligation sentences as MAPs.")
    return maps


# ============================================================
# DATABASE STORAGE
# Called by the orchestrator after extraction
# ============================================================

def extract_maps_from_mandate(
    mandate_id: str,
    db: Session,
) -> list[str]:
    """
    Full pipeline: fetch mandate → extract MAPs → score MPI → store.

    Args:
        mandate_id: UUID string of the mandate
        db:         SQLAlchemy session

    Returns:
        List of created MAP UUIDs as strings
    """
    try:
        mandate_uuid = uuid.UUID(mandate_id)
    except ValueError:
        print(f"[Extraction] Invalid mandate_id: {mandate_id}")
        return []

    mandate = db.query(Mandate).filter(Mandate.id == mandate_uuid).first()

    if not mandate:
        print(f"[Extraction] Mandate not found: {mandate_id}")
        return []

    if not mandate.raw_text:
        print(f"[Extraction] Mandate has no text: {mandate_id}")
        # Mark as processed so it doesn't get retried endlessly
        mandate.processed = True
        db.commit()
        return []

    if mandate.processed:
        print(f"[Extraction] Already processed: {mandate_id}")
        return []

    raw_maps = extract_maps_from_text(
        title      = mandate.title or "",
        text       = mandate.raw_text,
        ref_number = "",
        source     = mandate.source or "RBI",
    )

    if not raw_maps:
        print("[Extraction] No MAPs extracted. Marking mandate as processed.")
        mandate.processed = True
        db.commit()
        return []

    created_ids = []

    for raw_map in raw_maps:
        mpi_result = compute_mpi_score(
            penalty_exposure = raw_map["penalty_exposure"],
            deadline         = raw_map["deadline"],
            source           = mandate.source or "RBI",
            obligation_text  = raw_map["obligation_text"],
        )

        new_map = Map(
            mandate_id           = mandate_uuid,
            obligation_text      = raw_map["obligation_text"],
            measurable_condition = raw_map["measurable_condition"],
            deadline             = raw_map["deadline"],
            penalty_exposure     = raw_map["penalty_exposure"],
            evidence_required    = raw_map["evidence_required"],
            regulatory_reference = raw_map["regulatory_reference"],
            map_type             = raw_map["map_type"],
            mpi_score            = mpi_result["mpi_score"],
            priority_tier        = mpi_result["priority_tier"],
            status               = "OPEN",
        )

        db.add(new_map)
        db.commit()
        db.refresh(new_map)

        # Auto-route to Canara Bank Wings
        try:
            from backend.routing_engine import route_map
            route_map(new_map, db)
        except Exception as e:
            print(f"[Extraction] Routing error: {e}")

        created_ids.append(str(new_map.id))
        print(
            f"[Extraction] MAP created: {str(new_map.id)[:8]}... "
            f"Priority: {new_map.priority_tier} "
            f"MPI: {new_map.mpi_score}"
        )

    # Mark mandate as processed
    mandate.processed = True
    db.commit()

    print(f"[Extraction] Done. {len(created_ids)} MAPs created.")
    return created_ids


# ============================================================
# BATCH PROCESSOR
# ============================================================

def process_unprocessed_mandates(db: Session) -> dict:
    """
    Finds all unprocessed mandates and extracts MAPs from each.
    Called by POST /agents/extract.
    """
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
    processed  = 0
    failed     = 0

    for mandate in unprocessed:
        ids = extract_maps_from_mandate(str(mandate.id), db)
        if ids:
            total_maps += len(ids)
            processed  += 1
        else:
            failed += 1

    return {
        "mandates_processed": processed,
        "mandates_failed":    failed,
        "total_maps_created": total_maps,
    }


# ============================================================
# STANDALONE TEST
# Run: python -m agents.extraction_agent
# ============================================================

if __name__ == "__main__":
    sample_text = """
    Reserve Bank of India has issued this circular to all Scheduled Commercial Banks.

    All banks shall ensure that KYC documents for all existing customers are uploaded
    to the Central KYC Registry (CKYCR) within 30 days of the date of this circular.

    Banks must rectify all rejected KYC data and re-upload corrected records to CKYCR
    within 7 days of receipt of the rejection report from the registry.

    Banks are required to submit a compliance certificate to the respective Regional
    Office of RBI by September 30, 2026 confirming full compliance with these directions.

    Banks shall maintain a log of all CKYCR upload attempts and rejection rectifications
    for a period of five years for supervisory review.

    The penalty for non-compliance shall be as prescribed under Section 47A of the
    RBI Act, 1934. Banks failing to comply may be liable for a fine of up to
    Rs. 1 crore per instance of non-compliance.
    """

    maps = extract_maps_from_text(
        title      = "Master Direction on KYC — CKYCR Upload Requirements",
        text       = sample_text,
        ref_number = "RBI/2026-27/001",
        source     = "RBI",
    )

    print(f"\n{'='*60}")
    print(f"EXTRACTED {len(maps)} MAPs")
    print("=" * 60)

    for i, m in enumerate(maps, 1):
        print(f"\n[MAP {i}]")
        print(f"  Obligation  : {m['obligation_text'][:80]}...")
        print(f"  Condition   : {m['measurable_condition'][:80]}")
        print(f"  Deadline    : {m['deadline']}")
        print(f"  Penalty     : ₹{m['penalty_exposure']:,.0f}")
        print(f"  Type        : {m['map_type']}")
        print(f"  Reference   : {m['regulatory_reference']}")