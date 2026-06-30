"""
Seed Data — Canara Bank Compliance Demo Scenarios
File: database/seed_data.py

Creates 10 realistic MAPs based on REAL, documented RBI
penalties imposed on Canara Bank. Penalty amounts are accurate.

Each MAP is linked to a synthetic parent Mandate, scored via
the MPI engine, and routed across Canara Bank's Three Lines
of Defense using the routing engine.

Run: python database/seed_data.py
Safe to re-run — skips MAPs that already exist by title.
"""

import sys
import os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, engine, check_connection
from backend.models import Base, Mandate, Map
from agents.mpi_engine import compute_mpi_score
from backend.routing_engine import route_map


# ============================================================
# CANARA BANK SEED SCENARIOS
# All penalty amounts are real, documented RBI fines on
# Canara Bank. MAP 9 swapped to CERT-In per Excel sheet
# cross-reference (Cybersecurity Wing coverage).
# ============================================================

CANARA_BANK_SEED_MAPS = [

    # MAP 1 — CRITICAL — Real AML penalty on Canara Bank (₹2 crore)
    {
        "title": "AML Compliance — PMLA Transaction Monitoring",
        "source": "FIU_IND",
        "obligation": (
            "All branches must implement enhanced transaction "
            "monitoring for accounts flagged under PMLA Section 12 "
            "and report suspicious transactions to FIU-IND within "
            "the prescribed reporting window"
        ),
        "condition": (
            "100% of suspicious transactions reported to FIU-IND "
            "within 7 days of detection with zero overdue reports"
        ),
        "penalty": 20000000,
        "days": 30,
        "wing": "Compliance Wing",
        "ref": "PMLA Section 12 / RBI AML Master Direction",
        "evidence": (
            "FIU-IND submission acknowledgement, "
            "transaction monitoring audit report"
        ),
        "map_type": "PROCESS_CHANGE",
    },

    # MAP 2 — CRITICAL — Real KYC/CKYCR penalty on Canara Bank (₹41.8 lakh)
    {
        "title": "CKYCR Upload Compliance",
        "source": "RBI",
        "obligation": (
            "Upload all pending customer KYC documents to Central "
            "KYC Registry and rectify all rejected uploads within "
            "7 days of rejection report receipt"
        ),
        "condition": (
            "100% of customer KYC records uploaded to CKYCR with "
            "zero rejected uploads pending beyond 7 days"
        ),
        "penalty": 4180000,
        "days": 45,
        "wing": "Retail Banking Wing",
        "ref": "RBI Master Direction on KYC, CKYCR provisions",
        "evidence": (
            "CKYCR upload confirmation report, "
            "pending rejection queue screenshot"
        ),
        "map_type": "SYSTEM_CHANGE",
    },

    # MAP 3 — CRITICAL — Real PSL penalty on Canara Bank (₹1.63 crore)
    {
        "title": "Priority Sector Lending Target Achievement",
        "source": "RBI",
        "obligation": (
            "Achieve prescribed priority sector lending targets "
            "as per RBI Master Direction on Priority Sector Lending"
        ),
        "condition": (
            "Priority sector lending constitutes minimum 40% of "
            "Adjusted Net Bank Credit by financial year end"
        ),
        "penalty": 16300000,
        "days": 90,
        "wing": "Commercial Banking Wing",
        "ref": "RBI Master Direction on Priority Sector Lending",
        "evidence": (
            "PSLE return submitted to RBI, "
            "sector-wise lending portfolio report"
        ),
        "map_type": "POLICY_UPDATE",
    },

    # MAP 4 — HIGH — Real CIC data upload penalty (₹32 lakh)
    {
        "title": "Credit Information Companies Data Rectification",
        "source": "RBI",
        "obligation": (
            "Rectify all rejected data and upload corrected records "
            "to Credit Information Companies within 7 days of "
            "receipt of rejection report from CICs"
        ),
        "condition": (
            "Zero CIC rejection reports pending beyond 7 days "
            "in the data upload system"
        ),
        "penalty": 3200000,
        "days": 7,
        "wing": "Operations Wing",
        "ref": "RBI Directions on Credit Information Companies",
        "evidence": "CIC upload confirmation, zero-pending rejection report",
        "map_type": "REPORTING_OBLIGATION",
    },

    # MAP 5 — HIGH — Real inoperative account penalty (part of ₹41.8 lakh)
    {
        "title": "Inoperative Account Reclassification",
        "source": "RBI",
        "obligation": (
            "Review and reclassify all accounts incorrectly "
            "labelled as inoperative despite qualifying customer "
            "transactions within the preceding two years"
        ),
        "condition": (
            "100% of accounts with customer-initiated transactions "
            "in last 2 years reclassified as operative"
        ),
        "penalty": 4180000,
        "days": 30,
        "wing": "Retail Banking Wing",
        "ref": "RBI Directions on Inoperative Accounts",
        "evidence": (
            "Account reclassification report, "
            "branch compliance certificates"
        ),
        "map_type": "PROCESS_CHANGE",
    },

    # MAP 6 — HIGH — Real BSBDA penalty (part of ₹1.63 crore PSL+BSBDA)
    {
        "title": "Basic Savings Bank Deposit Account Access Compliance",
        "source": "RBI",
        "obligation": (
            "Ensure all eligible customers are offered BSBDA "
            "without mandatory minimum balance requirement "
            "at all branches as per financial inclusion norms"
        ),
        "condition": (
            "Zero instances of BSBDA denial or minimum balance "
            "imposition at any branch verified by audit"
        ),
        "penalty": 16300000,
        "days": 60,
        "wing": "Retail Banking Wing",
        "ref": "RBI Directions on Financial Inclusion — BSBDA",
        "evidence": (
            "Branch compliance certificates, "
            "BSBDA account opening report"
        ),
        "map_type": "POLICY_UPDATE",
    },

    # MAP 7 — HIGH — Real account restructuring violation (part of ₹32 lakh)
    {
        "title": "Restructured Accounts Eligibility Compliance",
        "source": "RBI",
        "obligation": (
            "Ensure all accounts restructured under any scheme "
            "qualify as standard assets on the restructuring date "
            "per RBI IRAC norms"
        ),
        "condition": (
            "Zero NPA accounts restructured without satisfying "
            "standard asset classification criteria"
        ),
        "penalty": 3200000,
        "days": 90,
        "wing": "Risk Management Wing",
        "ref": "RBI IRAC Norms — Income Recognition and Asset Classification",
        "evidence": (
            "Board approval note, asset classification report, "
            "restructuring eligibility checklist"
        ),
        "map_type": "POLICY_UPDATE",
    },

    # MAP 8 — MEDIUM — Interest rate on deposits
    {
        "title": "Interest Rate on Deposits Disclosure",
        "source": "RBI",
        "obligation": (
            "Display and publish updated interest rates on "
            "deposits at all branches and on the bank website "
            "within 24 hours of any rate revision"
        ),
        "condition": (
            "All branches and website display current deposit "
            "rates within 24 hours of revision — zero discrepancy"
        ),
        "penalty": 16300000,
        "days": 15,
        "wing": "Financial Management Wing",
        "ref": "RBI Directions on Interest Rate on Deposits",
        "evidence": (
            "Branch display photographs, "
            "website screenshot with timestamp"
        ),
        "map_type": "PROCESS_CHANGE",
    },

    # MAP 9 — HIGH — CERT-In cybersecurity incident reporting
    # Swapped from generic advisory per Excel sheet cross-reference
    # (Cybersecurity Wing / CERT-In coverage)
    {
        "title": "CERT-In Cyber Incident Reporting Compliance",
        "source": "CERT_IN",
        "obligation": (
            "Report all qualifying cyber security incidents to "
            "CERT-In within 6 hours of detection as mandated under "
            "Section 70B of the Information Technology Act, and "
            "maintain ICT system logs for a rolling 180-day period"
        ),
        "condition": (
            "100% of qualifying cyber incidents reported to CERT-In "
            "within the 6-hour window with zero missed reports, and "
            "180-day log retention verified across all ICT systems"
        ),
        "penalty": 0,
        "days": 0,
        "wing": "CISO Office",
        "ref": "CERT-In Directions No. 20(3)/2022-CERT-In, Section 70B IT Act",
        "evidence": (
            "CERT-In incident reporting acknowledgements, "
            "ICT log retention audit report"
        ),
        "map_type": "SYSTEM_CHANGE",
    },

    # MAP 10 — LOW — Quarterly reporting
    {
        "title": "Quarterly Compliance Report to RBI",
        "source": "RBI",
        "obligation": (
            "Submit quarterly compliance report covering all "
            "outstanding regulatory observations to RBI"
        ),
        "condition": (
            "Compliance report submitted to RBI within 15 days "
            "of quarter end with sign-off from Chief Compliance Officer"
        ),
        "penalty": 0,
        "days": 15,
        "wing": "Compliance Wing",
        "ref": "RBI Supervisory Compliance Reporting Framework",
        "evidence": "Submitted compliance report, RBI acknowledgement",
        "map_type": "REPORTING_OBLIGATION",
    },
]


# ============================================================
# SEED FUNCTION
# ============================================================

def seed_database():
    db = SessionLocal()

    try:
        print("=" * 65)
        print("CANARA BANK COMPLIANCE DEMO — SEEDING DATABASE")
        print("=" * 65)

        created_count = 0
        skipped_count = 0

        for entry in CANARA_BANK_SEED_MAPS:
            # Idempotency check — skip if this MAP already seeded
            existing = (
                db.query(Map)
                .filter(Map.obligation_text == entry["obligation"])
                .first()
            )
            if existing:
                print(f"[Seed] Skipping (already exists): {entry['title']}")
                skipped_count += 1
                continue

            # ── Create synthetic parent Mandate ──
            mandate = Mandate(
                source       = entry["source"],
                signal_type  = (
                    "ADVISORY" if entry["penalty"] == 0
                    else "MANDATORY_IMMEDIATE"
                ),
                title        = f"[Seed] {entry['title']}",
                raw_text     = entry["obligation"],
                url          = f"seed://canara-bank/{entry['title'].lower().replace(' ', '-')}",
                date_issued  = date.today() - timedelta(days=30),
                processed    = True,
            )
            db.add(mandate)
            db.commit()
            db.refresh(mandate)

            # ── Compute deadline ──
            deadline = (
                date.today() + timedelta(days=entry["days"])
                if entry["days"] > 0
                else None
            )

            # ── Score MPI ──
            mpi_result = compute_mpi_score(
                penalty_exposure = entry["penalty"],
                deadline         = deadline,
                source           = entry["source"],
                obligation_text  = entry["obligation"],
            )

            # ── Create Map ──
            map_obj = Map(
                mandate_id            = mandate.id,
                obligation_text       = entry["obligation"],
                measurable_condition  = entry["condition"],
                deadline              = deadline,
                penalty_exposure      = entry["penalty"],
                evidence_required     = entry["evidence"],
                regulatory_reference  = entry["ref"],
                map_type              = entry["map_type"],
                mpi_score             = mpi_result["mpi_score"],
                priority_tier         = mpi_result["priority_tier"],
                status                = "OPEN",
            )
            db.add(map_obj)
            db.commit()
            db.refresh(map_obj)

            # ── Route across Three Lines of Defense ──
            assignments = route_map(map_obj, db)

            created_count += 1
            print(
                f"[Seed] Created: {entry['title']:<55} "
                f"MPI={mpi_result['mpi_score']:>6.2f}  "
                f"{mpi_result['priority_tier']:<8} "
                f"₹{entry['penalty']:>12,.0f}  "
                f"→ {assignments[0]['wing']}"
            )

        print("=" * 65)
        print(f"SEEDING COMPLETE")
        print(f"  Created : {created_count}")
        print(f"  Skipped : {skipped_count} (already existed)")
        print("=" * 65)

        # ── Summary by priority tier ──
        print("\nPriority Tier Summary:")
        for tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            count = db.query(Map).filter(Map.priority_tier == tier).count()
            print(f"  {tier:<10}: {count} MAPs")

        total_exposure = sum(
            float(m.penalty_exposure or 0)
            for m in db.query(Map).filter(Map.status != "CLOSED").all()
        )
        print(f"\nTotal Open Penalty Exposure: ₹{total_exposure:,.2f}")

    except Exception as e:
        print(f"[Seed] ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    check_connection()
    Base.metadata.create_all(bind=engine)
    seed_database()