"""MAP Priority Index (MPI) scoring engine for IntelliMandate.

Run from project root:
    python -m agents.mpi_engine
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Dict, Optional

AUTHORITY_WEIGHTS = {
    "RBI": 10,
    "FIU": 10,
    "FIU-IND": 10,
    "SEBI": 8,
    "IRDAI": 6,
    "MCA": 5,
}

RECURRENCE_RISKS = {
    "KYC_AML": 5,
    "Cybersecurity": 5,
    "Capital_Adequacy": 4,
    "Grievance": 4,
    "FEMA": 3,
    "General_Compliance": 2,
}

PRIORITY_TIERS = [
    (80, "Critical"),
    (60, "High"),
    (40, "Medium"),
    (0, "Low"),
]


def assign_priority_tier(mpi_score: float) -> str:
    """Assign priority tier from MPI score."""
    for threshold, tier in PRIORITY_TIERS:
        if mpi_score >= threshold:
            return tier
    return "Low"


def parse_rupee_amount(text: Any) -> float:
    """Extract an approximate rupee value from penalty text.

    Returns rupee amount as float. If no numeric penalty is found, returns 0.
    Supports examples like "₹1 crore", "Rs. 10 lakh", "500000".
    """
    if not text:
        return 0.0

    s = str(text).lower().replace(",", "")
    if "not specified" in s or "none" in s:
        return 0.0

    match = re.search(r"(₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(crore|cr|lakh|lac|lakhs|lacs|million)?", s)
    if not match:
        return 0.0

    value = float(match.group(2))
    unit = match.group(3) or ""

    if unit in {"crore", "cr"}:
        value *= 10_000_000
    elif unit in {"lakh", "lac", "lakhs", "lacs"}:
        value *= 100_000
    elif unit == "million":
        value *= 1_000_000

    return value


def penalty_ceiling_score(penalty_exposure: Any) -> float:
    """Convert raw rupee exposure into a 0-100 risk score.

    The plan's formula needs a 0-100 penalty value, otherwise raw rupee values
    would explode the final score. This keeps MPI interpretable for dashboard tiers.
    """
    rupees = parse_rupee_amount(penalty_exposure)
    if rupees <= 0:
        return 10
    if rupees < 100_000:      # below 1 lakh
        return 30
    if rupees < 1_000_000:    # below 10 lakh
        return 50
    if rupees < 10_000_000:   # below 1 crore
        return 70
    return 100


def penalty_likelihood(authority: str, map_type: str) -> float:
    """Simple likelihood estimate from regulator and risk type."""
    authority = (authority or "RBI").upper()
    map_type = map_type or "General_Compliance"

    base = 0.65
    if authority in {"RBI", "FIU", "FIU-IND"}:
        base += 0.15
    if map_type in {"KYC_AML", "Cybersecurity", "Capital_Adequacy"}:
        base += 0.10
    return min(base, 1.0)


def _parse_deadline_date(deadline: str) -> Optional[date]:
    if not deadline or str(deadline).lower() in {"not specified", "none", "null"}:
        return None

    s = str(deadline).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y", "%b %d, %Y", "%d %b %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def deadline_urgency(deadline: Any, today: Optional[date] = None) -> float:
    """Return deadline urgency score.

    Rules from plan:
    - 0 days = 100
    - 7 days = 90
    - 30 days = 70
    - 90+ days = exponential decay
    Also supports relative text like "within 30 days".
    """
    today = today or date.today()
    deadline_text = str(deadline or "").lower()

    rel = re.search(r"within\s+(\d+)\s+days?", deadline_text)
    if rel:
        days_left = int(rel.group(1))
    else:
        parsed = _parse_deadline_date(str(deadline or ""))
        if parsed is None:
            return 50
        days_left = (parsed - today).days

    if days_left <= 0:
        return 100
    if days_left <= 7:
        return 90
    if days_left <= 30:
        return 70
    if days_left <= 90:
        return max(35, 70 * math.exp(-(days_left - 30) / 90))
    return max(10, 40 * math.exp(-(days_left - 90) / 180))


def score_map(map_obj: Dict[str, Any], authority: str = "RBI") -> Dict[str, Any]:
    """Calculate MPI score and priority tier for one MAP dictionary."""
    map_type = map_obj.get("map_type", "General_Compliance")

    penalty_score = penalty_ceiling_score(map_obj.get("penalty_exposure"))
    likelihood = penalty_likelihood(authority, map_type)
    urgency = deadline_urgency(map_obj.get("deadline"))
    authority_weight = AUTHORITY_WEIGHTS.get((authority or "RBI").upper(), 5)
    recurrence_risk = RECURRENCE_RISKS.get(map_type, 2)

    raw_mpi = (
        (penalty_score * likelihood)
        + (urgency * 0.3)
        + (authority_weight * 10)
        + (recurrence_risk * 5)
    )

    mpi_score = round(min(raw_mpi, 100), 2)

    scored = dict(map_obj)
    scored["mpi_score"] = mpi_score
    scored["priority_tier"] = assign_priority_tier(mpi_score)
    scored["mpi_breakdown"] = {
        "penalty_ceiling_score": penalty_score,
        "penalty_likelihood": likelihood,
        "deadline_urgency": round(urgency, 2),
        "authority_weight": authority_weight,
        "recurrence_risk": recurrence_risk,
        "raw_mpi_before_cap": round(raw_mpi, 2),
    }
    return scored


if __name__ == "__main__":
    sample_map = {
        "obligation_text": "Banks shall update all customer KYC records within 30 days.",
        "measurable_condition": "All customer KYC records are updated and documented.",
        "deadline": "within 30 days",
        "penalty_exposure": "₹1 crore",
        "evidence_required": "KYC update completion report",
        "regulatory_reference": "RBI KYC circular sample",
        "map_type": "KYC_AML",
    }
    print(score_map(sample_map, authority="RBI"))
