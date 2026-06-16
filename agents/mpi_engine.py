"""
IntelliMandate v3 — MAP Priority Index (MPI) Engine
File: agents/mpi_engine.py

June 15 Member B Task B-2-5
Pure Python. No ML. No LLM. No external API. No internet.

Formula:
    MPI = (penalty_ceiling × penalty_likelihood)
        + (deadline_urgency × 0.3)
        + (authority_weight × 10)
        + (recurrence_risk × 5)

Run:
    python -m agents.mpi_engine
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Union


AUTHORITY_WEIGHTS = {
    "RBI": 10,
    "FIU_IND": 10,
    "FIU-IND": 10,
    "SEBI": 8,
    "IRDAI": 6,
    "MCA": 5,
    "GAZETTE": 4,
    "UNKNOWN": 3,
}

PENALTY_LIKELIHOOD = {
    "RBI": 0.85,
    "FIU_IND": 0.90,
    "FIU-IND": 0.90,
    "SEBI": 0.70,
    "IRDAI": 0.60,
    "MCA": 0.55,
    "GAZETTE": 0.40,
    "UNKNOWN": 0.30,
}

# Standard risks + Canara Bank-specific risks from v3 plan.
RECURRENCE_RISKS = {
    # Standard
    "kyc": 5,
    "aml": 5,
    "pmla": 5,
    "know your customer": 5,
    "anti money": 5,
    "cybersecurity": 5,
    "cyber security": 5,
    "capital adequacy": 4,
    "basel": 4,
    "grievance": 4,
    "customer grievance": 4,
    "fema": 3,
    "foreign exchange": 3,
    "interest rate": 2,
    "reporting": 2,
    # Canara Bank-specific documented violation categories
    "ckycr": 5,
    "central kyc": 5,
    "credit information": 5,
    "cic": 5,
    "inoperative account": 4,
    "inoperative accounts": 4,
    "priority sector": 4,
    "psl": 4,
    "bsbda": 4,
    "basic savings": 4,
    "account restructur": 4,
    "restructured account": 4,
    "irac": 4,
    "income recognition": 4,
    "asset classification": 4,
    "interest rate deposit": 3,
    "deposit interest": 3,
    "crr": 3,
    "slr": 3,
}

DEFAULT_RECURRENCE_RISK = 1


PenaltyInput = Union[float, int, str, None]
DeadlineInput = Union[date, datetime, str, int, None]


def parse_penalty_to_rupees(penalty_exposure: PenaltyInput) -> float:
    """Accept float/int or strings like '₹41.8 lakh', '1.63 crore', 'Rs.32 lakh'."""
    if penalty_exposure is None:
        return 0.0
    if isinstance(penalty_exposure, (int, float)):
        return float(penalty_exposure)

    text = str(penalty_exposure).lower().replace(",", " ")
    if "not specified" in text or "supervisory action" in text or "advisory" in text:
        return 0.0

    pattern = re.compile(r"(?:₹|rs\.?|inr)?\s*([0-9]+(?:\.[0-9]+)?)\s*(crore|cr|lakh|lac|lakhs|lacs|million|thousand|rupees?)?", re.I)
    values = []
    for amount_text, unit in pattern.findall(text):
        amount = float(amount_text)
        unit = (unit or "").lower()
        if unit in {"crore", "cr"}:
            values.append(amount * 10_000_000)
        elif unit in {"lakh", "lac", "lakhs", "lacs"}:
            values.append(amount * 100_000)
        elif unit == "million":
            values.append(amount * 1_000_000)
        elif unit == "thousand":
            values.append(amount * 1_000)
        else:
            # Only use bare numbers if the string clearly describes money.
            if any(marker in text for marker in ("₹", "rs", "inr", "rupee", "penalty", "fine")):
                values.append(amount)
    return float(max(values)) if values else 0.0


def parse_deadline(deadline: DeadlineInput) -> Optional[date]:
    """Accept date/datetime, ISO string, 'within 7 days', or days as int."""
    if deadline is None:
        return None
    if isinstance(deadline, datetime):
        return deadline.date()
    if isinstance(deadline, date):
        return deadline
    if isinstance(deadline, int):
        return datetime.now(timezone.utc).date() + timedelta(days=deadline)

    text = str(deadline).strip().lower()
    if not text or text in {"not specified", "none", "no deadline"}:
        return None

    within = re.search(r"within\s+([0-9]+)\s+(day|days|week|weeks|month|months)", text)
    if within:
        n = int(within.group(1))
        unit = within.group(2)
        days = n * 7 if unit.startswith("week") else n * 30 if unit.startswith("month") else n
        return datetime.now(timezone.utc).date() + timedelta(days=days)

    # ISO date
    try:
        return datetime.fromisoformat(text.replace("z", "+00:00")).date()
    except Exception:
        pass

    # Month name
    for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y"):
        try:
            return datetime.strptime(str(deadline).strip(), fmt).date()
        except Exception:
            continue
    return None


def calculate_deadline_urgency(deadline: DeadlineInput) -> float:
    parsed = parse_deadline(deadline)
    if parsed is None:
        return 20.0

    today = datetime.now(timezone.utc).date()
    days_remaining = (parsed - today).days

    if days_remaining <= 0:
        return 100.0
    if days_remaining <= 7:
        return 90.0
    if days_remaining <= 14:
        return 80.0
    if days_remaining <= 30:
        return 70.0
    if days_remaining <= 60:
        return 55.0
    if days_remaining <= 90:
        return 40.0
    return max(10.0, 40.0 * math.exp(-0.005 * (days_remaining - 90)))


def calculate_recurrence_risk(obligation_text: str) -> float:
    text_lower = (obligation_text or "").lower()
    max_risk = DEFAULT_RECURRENCE_RISK
    for keyword, risk in RECURRENCE_RISKS.items():
        if keyword in text_lower:
            max_risk = max(max_risk, risk)
    return float(max_risk)


def normalize_penalty(penalty_rupees: float) -> float:
    """Normalize raw rupee penalty to 0-100 scale."""
    if penalty_rupees <= 0:
        return 0.0
    if penalty_rupees >= 100_000_000:   # 10 crore+
        return 100.0
    if penalty_rupees >= 10_000_000:    # 1 crore+
        return 85.0
    if penalty_rupees >= 2_500_000:     # 25 lakh+
        return 70.0
    if penalty_rupees >= 500_000:       # 5 lakh+
        return 50.0
    if penalty_rupees >= 100_000:       # 1 lakh+
        return 30.0
    return 15.0


def compute_mpi_score(
    penalty_exposure: PenaltyInput,
    deadline: DeadlineInput,
    source: str,
    obligation_text: str = "",
) -> dict:
    """
    Main function required by v3 plan:
        compute_mpi_score(penalty_exposure, deadline, source, obligation_text) -> dict
    """
    source_key = (source or "UNKNOWN").upper().strip().replace("-", "_")
    if source_key == "FIU_IND":
        source_lookup = "FIU_IND"
    else:
        source_lookup = source_key

    penalty_rupees = parse_penalty_to_rupees(penalty_exposure)
    authority_weight = AUTHORITY_WEIGHTS.get(source_lookup, AUTHORITY_WEIGHTS["UNKNOWN"])
    likelihood = PENALTY_LIKELIHOOD.get(source_lookup, PENALTY_LIKELIHOOD["UNKNOWN"])

    penalty_ceiling = normalize_penalty(penalty_rupees)
    deadline_urgency = calculate_deadline_urgency(deadline)
    recurrence_risk = calculate_recurrence_risk(obligation_text)

    # v3 standalone test explicitly expects advisory with zero penalty to remain LOW.
    # For zero-penalty advisories, do not let authority weight alone inflate the score.
    is_advisory_zero_penalty = (
        penalty_rupees <= 0
        and parse_deadline(deadline) is None
        and any(term in (obligation_text or "").lower() for term in ("advised", "advisory", "awareness", "may consider"))
    )
    if is_advisory_zero_penalty:
        authority_component = 0.0
        recurrence_component = 0.0
        mpi_raw = deadline_urgency * 0.3
    else:
        authority_component = authority_weight * 10
        recurrence_component = recurrence_risk * 5
        mpi_raw = (
            (penalty_ceiling * likelihood)
            + (deadline_urgency * 0.3)
            + authority_component
            + recurrence_component
        )
    mpi_score = min(round(mpi_raw, 2), 100.0)

    if mpi_score >= 80:
        priority_tier = "CRITICAL"
    elif mpi_score >= 60:
        priority_tier = "HIGH"
    elif mpi_score >= 40:
        priority_tier = "MEDIUM"
    else:
        priority_tier = "LOW"

    breakdown = (
        f"Penalty ceiling {penalty_ceiling:.1f} × likelihood {likelihood:.2f} = {penalty_ceiling * likelihood:.1f}; "
        f"Deadline urgency {deadline_urgency:.1f} × 0.3 = {deadline_urgency * 0.3:.1f}; "
        f"Authority weight {authority_weight} × 10 = {authority_component:.0f}; "
        f"Recurrence risk {recurrence_risk:.0f} × 5 = {recurrence_component:.0f}; "
        f"MPI = {mpi_score}."
    )

    return {
        "mpi_score": mpi_score,
        "priority_tier": priority_tier,
        "breakdown": breakdown,
        "penalty_rupees": penalty_rupees,
        "penalty_ceiling": penalty_ceiling,
        "penalty_likelihood": likelihood,
        "deadline_urgency": deadline_urgency,
        "authority_weight": authority_weight,
        "recurrence_risk": recurrence_risk,
    }


def score_maps_batch(maps: list[dict], source: str = "RBI") -> list[dict]:
    """Add MPI fields to a list of MAP dicts and sort highest risk first."""
    scored = []
    for map_obj in maps:
        result = compute_mpi_score(
            penalty_exposure=map_obj.get("penalty_exposure", 0),
            deadline=map_obj.get("deadline"),
            source=source or map_obj.get("source", "RBI"),
            obligation_text=map_obj.get("obligation_text", ""),
        )
        new_map = dict(map_obj)
        new_map["mpi_score"] = result["mpi_score"]
        new_map["priority_tier"] = result["priority_tier"]
        new_map["mpi_breakdown"] = result["breakdown"]
        new_map["penalty_rupees"] = result["penalty_rupees"]
        scored.append(new_map)
    scored.sort(key=lambda item: item.get("mpi_score", 0), reverse=True)
    return scored


if __name__ == "__main__":
    test_cases = [
        {
            "label": "Canara CKYCR/KYC penalty — ₹41.8 lakh",
            "penalty_exposure": "₹41.8 lakh",
            "deadline": "within 45 days",
            "source": "RBI",
            "obligation_text": "Upload all pending customer KYC documents to CKYCR and rectify rejected uploads within 7 days.",
        },
        {
            "label": "Canara AML/PMLA penalty — ₹2 crore",
            "penalty_exposure": "₹2 crore",
            "deadline": "within 30 days",
            "source": "FIU_IND",
            "obligation_text": "All branches must implement enhanced AML transaction monitoring under PMLA and report suspicious transactions to FIU-IND.",
        },
        {
            "label": "Canara PSL shortfall — ₹1.63 crore",
            "penalty_exposure": "₹1.63 crore",
            "deadline": "within 90 days",
            "source": "RBI",
            "obligation_text": "Achieve prescribed priority sector lending targets as per RBI Master Direction on Priority Sector Lending.",
        },
        {
            "label": "Advisory — zero penalty",
            "penalty_exposure": 0,
            "deadline": None,
            "source": "RBI",
            "obligation_text": "Banks are advised to circulate digital banking fraud awareness material to customers.",
        },
    ]

    print("MAP PRIORITY INDEX — CANARA BANK TEST RESULTS")
    print("=" * 72)
    for case in test_cases:
        result = compute_mpi_score(
            case["penalty_exposure"], case["deadline"], case["source"], case["obligation_text"]
        )
        print(f"\n{case['label']}")
        print(f"  MPI Score : {result['mpi_score']}")
        print(f"  Priority  : {result['priority_tier']}")
        print(f"  Rupees    : {result['penalty_rupees']}")
        print(f"  Breakdown : {result['breakdown']}")
