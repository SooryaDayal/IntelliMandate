"""
Regulation Delta Engine
File: backend/scrapers/delta_engine.py

Compares the current version of a circular against
the previous version stored in the database.

Returns only what changed — added lines, removed lines,
and a human-readable change summary.

This is only triggered for CIRCULAR_AMENDMENT signal type.
For all other signal types, no diff is needed.

Uses Python's built-in difflib — no external dependencies.
"""

import difflib
import re
from typing import Optional
from datetime import datetime, timezone


# ============================================================
# TEXT CLEANING
# Normalizes extracted PDF text before diffing
# Removes noise that creates false positives in diffs
# ============================================================

def clean_text_for_diff(text: str) -> list[str]:
    """
    Cleans and normalizes circular text into a list of lines
    ready for comparison.

    Steps:
        1. Remove page break markers (--- Page N ---)
        2. Normalize whitespace — collapse multiple spaces/newlines
        3. Remove purely numeric lines (page numbers)
        4. Remove very short lines under 10 chars (headers, footers)
        5. Strip leading/trailing whitespace per line
        6. Remove empty lines
        7. Lowercase for comparison only — original preserved separately

    Returns:
        List of cleaned, non-empty lines
    """
    if not text:
        return []

    # Remove page break markers added by pdf_extractor
    text = re.sub(r"--- Page \d+ ---", "", text)

    # Normalize multiple spaces to single space
    text = re.sub(r"[ \t]+", " ", text)

    # Split into lines
    lines = text.splitlines()

    cleaned = []
    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Skip pure page numbers (1, 2, 3, etc.)
        if re.match(r"^\d{1,3}$", line):
            continue

        # Skip spaced page number patterns: "1 | P a g e"
        if re.search(r"[Pp]\s*[Aa]\s*[Gg]\s*[Ee]", line) and len(line) < 20:
            continue

        # Skip very short lines (likely headers/footers/page markers)
        if len(line) < 10:
            continue

        # Skip lines that are purely punctuation or symbols
        if re.match(r"^[\W_]+$", line):
            continue

        # Skip standard RBI boilerplate identical across all circulars
        boilerplate = [
            "reserve bank of india",
            "madam/ dear sir",
            "madam / dear sir",
            "dear sir / madam",
            "yours faithfully",
            "yours sincerely",
        ]
        if line.lower().strip() in boilerplate:
            continue

        cleaned.append(line)

    return cleaned


# ============================================================
# CORE DIFF FUNCTION
# ============================================================

def compute_diff(
    old_text: str,
    new_text: str,
    context_lines: int = 2
) -> dict:
    """
    Computes the difference between old and new circular text.

    Args:
        old_text:      Full text of the previous circular version
        new_text:      Full text of the current circular version
        context_lines: Number of unchanged lines to show around changes

    Returns:
        {
            "added":          list[str] — lines present in new, absent in old
            "removed":        list[str] — lines present in old, absent in new
            "added_count":    int
            "removed_count":  int
            "change_ratio":   float — 0.0 (identical) to 1.0 (completely different)
            "has_changes":    bool
            "unified_diff":   str  — full unified diff output for storage
            "summary":        str  — human-readable plain English summary
        }
    """
    old_lines = clean_text_for_diff(old_text)
    new_lines = clean_text_for_diff(new_text)

    if not old_lines and not new_lines:
        return _empty_result("Both old and new text are empty.")

    if not old_lines:
        return _empty_result("No previous version available for comparison.")

    if not new_lines:
        return _empty_result("New version text is empty.")

    # ── Compute unified diff ──
    unified = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="previous_version",
        tofile="current_version",
        lineterm="",
        n=context_lines
    ))

    # ── Separate added and removed lines ──
    added   = [line[1:].strip() for line in unified if line.startswith("+") and not line.startswith("+++")]
    removed = [line[1:].strip() for line in unified if line.startswith("-") and not line.startswith("---")]

    # Filter out trivial changes (whitespace-only diffs)
    added   = [line for line in added   if len(line.strip()) > 5]
    removed = [line for line in removed if len(line.strip()) > 5]

    # ── Compute similarity ratio ──
    matcher       = difflib.SequenceMatcher(None, old_lines, new_lines)
    similarity    = matcher.ratio()
    change_ratio  = round(1.0 - similarity, 4)

    has_changes = len(added) > 0 or len(removed) > 0

    # ── Generate human-readable summary ──
    summary = _generate_summary(added, removed, change_ratio)

    return {
        "added":          added,
        "removed":        removed,
        "added_count":    len(added),
        "removed_count":  len(removed),
        "change_ratio":   change_ratio,
        "has_changes":    has_changes,
        "unified_diff":   "\n".join(unified),
        "summary":        summary,
    }


# ============================================================
# SUMMARY GENERATOR
# Converts raw diff output into plain English
# ============================================================

def _generate_summary(
    added: list[str],
    removed: list[str],
    change_ratio: float
) -> str:
    """
    Generates a plain English summary of what changed.
    This is what the compliance officer actually reads.
    """
    if not added and not removed:
        return "No substantive changes detected between versions."

    parts = []

    # Overall change magnitude
    if change_ratio < 0.05:
        parts.append("Minor update.")
    elif change_ratio < 0.20:
        parts.append("Moderate revision.")
    elif change_ratio < 0.50:
        parts.append("Significant revision.")
    else:
        parts.append("Major overhaul.")

    # Added content summary
    if added:
        parts.append(
            f"{len(added)} new clause(s) or requirement(s) introduced."
        )
        # Show first added line as example
        if added[0]:
            preview = added[0][:120]
            parts.append(f"New content includes: \"{preview}...\"" if len(added[0]) > 120 else f"New content: \"{preview}\"")

    # Removed content summary
    if removed:
        parts.append(
            f"{len(removed)} clause(s) or requirement(s) removed or replaced."
        )
        if removed[0]:
            preview = removed[0][:120]
            parts.append(f"Removed content includes: \"{preview}...\"" if len(removed[0]) > 120 else f"Removed: \"{preview}\"")

    # Compliance implication
    if added and not removed:
        parts.append("Action required: review new requirements and assess compliance impact.")
    elif removed and not added:
        parts.append("Note: previous requirements have been relaxed or removed.")
    elif added and removed:
        parts.append("Action required: review both new requirements and removed clauses.")

    return " ".join(parts)


# ============================================================
# CHANGE SIGNIFICANCE CLASSIFIER
# Tells the MPI engine how much extra urgency to add
# ============================================================

def classify_change_significance(diff_result: dict) -> str:
    """
    Classifies how significant the detected changes are.

    Returns:
        "MAJOR"    → change_ratio > 0.30 or > 10 additions
        "MODERATE" → change_ratio > 0.10 or > 5 additions
        "MINOR"    → anything smaller
        "NONE"     → no changes detected
    """
    if not diff_result.get("has_changes"):
        return "NONE"

    ratio   = diff_result.get("change_ratio", 0)
    added   = diff_result.get("added_count", 0)
    removed = diff_result.get("removed_count", 0)
    total   = added + removed

    if ratio > 0.30 or total > 10:
        return "MAJOR"
    elif ratio > 0.10 or total > 5:
        return "MODERATE"
    else:
        return "MINOR"


# ============================================================
# DATABASE INTEGRATION HELPER
# Retrieves previous circular text from PostgreSQL
# Called before computing diff
# ============================================================

def get_previous_version_text(
    db,
    ref_number: str,
    current_mandate_id: str
) -> Optional[str]:
    """
    Fetches the raw_text of the most recent previous version
    of a circular from the mandates table.

    Matches by ref_number pattern — strips the version suffix
    to find related circulars.
    e.g. "RBI/2026-2027/106DOR.RET.REC.88" matches
         "RBI/2025-2026/047DOR.RET.REC.12" (same series)

    Args:
        db:                  SQLAlchemy session
        ref_number:          Reference number of the current circular
        current_mandate_id:  UUID of current mandate (excluded from search)

    Returns:
        raw_text of the previous version, or None if not found.
    """
    from backend.models import Mandate
    from sqlalchemy import desc

    if not ref_number:
        return None

    # Extract the department code from ref_number
    # e.g. "RBI/2026-2027/106DOR.RET.REC.88/12.01.001/2026-27"
    # Department code: "DOR.RET.REC" — the regulatory series identifier
    dept_code = _extract_dept_code(ref_number)

    if not dept_code:
        return None

    try:
        # Find the most recent previous circular with the same department code
        previous = (
            db.query(Mandate)
            .filter(
                Mandate.ref_number.ilike(f"%{dept_code}%"),
                Mandate.id != current_mandate_id,
                Mandate.signal_type == "CIRCULAR_AMENDMENT",
                Mandate.raw_text.isnot(None)
            )
            .order_by(desc(Mandate.date_issued))
            .first()
        )

        if previous:
            print(
                f"[Delta Engine] Found previous version: "
                f"{previous.ref_number} dated {previous.date_issued}"
            )
            return previous.raw_text

    except Exception as e:
        print(f"[Delta Engine] Database query error: {e}")

    return None


def _extract_dept_code(ref_number: str) -> Optional[str]:
    """
    Extracts the department/series code from an RBI reference number.

    Examples:
        "RBI/2026-2027/106DOR.RET.REC.88/12.01.001/2026-27"
        → "DOR.RET.REC"

        "RBI/2026-2027/107DCM(Plg) No.S736/10.02.060/2026-27"
        → "DCM"

        "RBI/2026-2027/101A.P. (DIR Series) Circular No. 13"
        → "DIR"
    """
    if not ref_number:
        return None

    # Common RBI department codes
    dept_patterns = [
        r"(DOR\.[A-Z.]+)",        # Department of Regulation series
        r"(DCM[A-Z().]*)",        # Department of Currency Management
        r"(DIR\s+Series)",        # Foreign Exchange (FEMA)
        r"(FMOD\.[A-Z.]+)",       # Financial Markets Operations
        r"(DGBA\.[A-Z.]+)",       # Government and Bank Accounts
        r"(DBS\.[A-Z.]+)",        # Department of Banking Supervision
        r"(DNBS\.[A-Z.]+)",       # Department of Non-Banking Supervision
        r"(DPSS\.[A-Z.]+)",       # Payment Systems
        r"(DIT\.[A-Z.]+)",        # Information Technology
    ]

    for pattern in dept_patterns:
        match = re.search(pattern, ref_number, re.IGNORECASE)
        if match:
            return match.group(1)

    # Fallback: extract anything between the circular number and first slash
    # e.g. from "106DOR.RET" extract "DOR"
    match = re.search(r"\d+([A-Z]+)", ref_number)
    if match:
        return match.group(1)

    return None


# ============================================================
# MAIN ENTRY POINT
# Called by the Monitor Agent for CIRCULAR_AMENDMENT documents
# ============================================================

def run_delta_analysis(
    current_text: str,
    previous_text: Optional[str],
    ref_number:    str = "",
) -> dict:
    """
    Main function called by the Monitor Agent.
    Runs full delta analysis and returns structured result.

    Args:
        current_text:  Extracted text of the new circular version
        previous_text: Extracted text of the previous version (from DB)
                       Pass None if no previous version exists
        ref_number:    Reference number for logging

    Returns:
        Full diff result dict from compute_diff(),
        plus "significance" and "timestamp" fields added.
        Returns a no-change result if previous_text is None.
    """
    print(f"[Delta Engine] Running delta analysis for: {ref_number or 'unknown'}")

    if not previous_text:
        print("[Delta Engine] No previous version found. First occurrence of this circular series.")
        return {
            "added":          [],
            "removed":        [],
            "added_count":    0,
            "removed_count":  0,
            "change_ratio":   0.0,
            "has_changes":    False,
            "unified_diff":   "",
            "summary":        "First version of this circular series. No previous version to compare.",
            "significance":   "NONE",
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }

    result = compute_diff(previous_text, current_text)
    result["significance"] = classify_change_significance(result)
    result["timestamp"]    = datetime.now(timezone.utc).isoformat()

    print(
        f"[Delta Engine] Analysis complete. "
        f"Added: {result['added_count']} | "
        f"Removed: {result['removed_count']} | "
        f"Significance: {result['significance']}"
    )

    return result


# ============================================================
# HELPER: FORMAT DELTA FOR STORAGE
# Converts diff result to a compact string for the
# mandates.delta_summary column in PostgreSQL
# ============================================================

def format_delta_summary(diff_result: dict) -> str:
    """
    Formats the diff result into a compact string
    for storage in the mandates.delta_summary column.

    Compliance officers and the dashboard read this field directly.
    """
    if not diff_result.get("has_changes"):
        return diff_result.get("summary", "No changes detected.")

    lines = [
        f"SIGNIFICANCE: {diff_result.get('significance', 'UNKNOWN')}",
        f"CHANGE RATIO: {diff_result.get('change_ratio', 0):.1%}",
        f"ADDED: {diff_result.get('added_count', 0)} clauses",
        f"REMOVED: {diff_result.get('removed_count', 0)} clauses",
        "",
        "SUMMARY:",
        diff_result.get("summary", ""),
        "",
        "NEW REQUIREMENTS:",
    ]

    for item in diff_result.get("added", [])[:5]:
        lines.append(f"  + {item[:200]}")

    if len(diff_result.get("added", [])) > 5:
        lines.append(f"  ... and {len(diff_result['added']) - 5} more.")

    lines.append("")
    lines.append("REMOVED REQUIREMENTS:")

    for item in diff_result.get("removed", [])[:5]:
        lines.append(f"  - {item[:200]}")

    if len(diff_result.get("removed", [])) > 5:
        lines.append(f"  ... and {len(diff_result['removed']) - 5} more.")

    return "\n".join(lines)


# ============================================================
# EMPTY RESULT HELPER
# ============================================================

def _empty_result(reason: str) -> dict:
    return {
        "added":          [],
        "removed":        [],
        "added_count":    0,
        "removed_count":  0,
        "change_ratio":   0.0,
        "has_changes":    False,
        "unified_diff":   "",
        "summary":        reason,
        "significance":   "NONE",
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# STANDALONE TEST
# Run: python -m backend.scrapers.delta_engine
# Simulates a diff between two versions of the same circular
# ============================================================

if __name__ == "__main__":
    from backend.scrapers.rbi_scraper   import fetch_rbi_circulars
    from backend.scrapers.pdf_extractor import extract_circular_text

    print("Fetching 2 circulars to simulate delta...")
    circulars = fetch_rbi_circulars(max_circulars=2)

    if len(circulars) < 2:
        print("Need at least 2 circulars to test delta engine.")
        exit(1)

    print("\nExtracting text from circular 1 (simulated OLD version)...")
    old_text = extract_circular_text(circulars[0]) or ""

    print("\nExtracting text from circular 2 (simulated NEW version)...")
    new_text = extract_circular_text(circulars[1]) or ""

    if not old_text or not new_text:
        print("Text extraction failed. Cannot test delta engine.")
        exit(1)

    print("\nRunning delta analysis...")
    result = run_delta_analysis(
        current_text  = new_text,
        previous_text = old_text,
        ref_number    = circulars[1].get("ref_number", "TEST")
    )

    print("\n" + "=" * 70)
    print("DELTA ANALYSIS RESULT")
    print("=" * 70)
    print(f"Has Changes    : {result['has_changes']}")
    print(f"Significance   : {result['significance']}")
    print(f"Change Ratio   : {result['change_ratio']:.1%}")
    print(f"Added Lines    : {result['added_count']}")
    print(f"Removed Lines  : {result['removed_count']}")
    print(f"\nSummary:\n{result['summary']}")

    if result["added"]:
        print(f"\nSample Added Lines (first 3):")
        for line in result["added"][:3]:
            print(f"  + {line[:120]}")

    if result["removed"]:
        print(f"\nSample Removed Lines (first 3):")
        for line in result["removed"][:3]:
            print(f"  - {line[:120]}")

    print("\n" + "=" * 70)
    print("FORMATTED DELTA SUMMARY (stored in DB):")
    print("=" * 70)
    print(format_delta_summary(result))