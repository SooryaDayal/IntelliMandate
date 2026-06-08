import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Boolean, Date,
    Numeric, SmallInteger, TIMESTAMP, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.database import Base


# ============================================================
# MODEL 1: Mandate
# Maps to the mandates table
# Stores raw regulatory documents fetched by Monitor Agent
# ============================================================

class Mandate(Base):
    __tablename__ = "mandates"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    source = Column(
        String(50),
        nullable=False
        # RBI, SEBI, IRDAI, FIU_IND, MCA, GAZETTE
    )
    signal_type = Column(
        String(30),
        nullable=False
        # MANDATORY_IMMEDIATE, MANDATORY_FUTURE,
        # CIRCULAR_AMENDMENT, CONSULTATION_PAPER, ADVISORY
    )
    title = Column(
        Text,
        nullable=False
    )
    raw_text = Column(
        Text,
        nullable=True
    )
    url = Column(
        Text,
        nullable=True
    )
    date_issued = Column(
        Date,
        nullable=True
    )
    delta_summary = Column(
        Text,
        nullable=True
        # Only populated for CIRCULAR_AMENDMENT signal type
        # Stores the diff showing what changed from previous version
    )
    processed = Column(
        Boolean,
        default=False
        # FALSE until MAP Extraction Agent has processed this mandate
        # Member B's agent queries WHERE processed = FALSE
    )
    created_at = Column(
        TIMESTAMP,
        default=datetime.utcnow
    )

    # Relationship: one mandate produces many MAPs
    maps = relationship(
        "Map",
        back_populates="mandate",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"<Mandate id={self.id} "
            f"source={self.source} "
            f"signal_type={self.signal_type} "
            f"processed={self.processed}>"
        )


# ============================================================
# MODEL 2: Map
# Maps to the maps table
# Stores Measurable Action Points extracted from mandates
# ============================================================

class Map(Base):
    __tablename__ = "maps"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    mandate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mandates.id", ondelete="CASCADE"),
        nullable=False
    )
    obligation_text = Column(
        Text,
        nullable=False
        # What the bank must do — plain language
    )
    measurable_condition = Column(
        Text,
        nullable=False
        # Machine-verifiable definition of done
        # e.g. "% dormant accounts with refreshed KYC >= 100"
        # This field powers autonomous validation in Gate 4
    )
    deadline = Column(
        Date,
        nullable=True
    )
    penalty_exposure = Column(
        Numeric(15, 2),
        default=0
        # Rupee value extracted directly from regulation text
        # Used as the dominant term in MPI scoring
    )
    evidence_required = Column(
        Text,
        nullable=True
        # Comma-separated list of required document types
        # e.g. "Board approval note, Updated KYC records, System audit report"
    )
    regulatory_reference = Column(
        Text,
        nullable=True
        # Exact clause citation
        # e.g. "RBI Master Direction on KYC, April 2026, Clause 38(ii)"
    )
    map_type = Column(
        String(30),
        nullable=True
        # PROCESS_CHANGE, POLICY_UPDATE, SYSTEM_CHANGE, REPORTING_OBLIGATION
    )
    mpi_score = Column(
        Numeric(5, 2),
        default=0
        # MAP Priority Index score 0-100
        # Higher score = higher financial risk = higher priority
    )
    priority_tier = Column(
        String(20),
        default="LOW"
        # CRITICAL (>=80), HIGH (60-79), MEDIUM (40-59), LOW (<40)
    )
    status = Column(
        String(20),
        default="OPEN"
        # OPEN, IN_PROGRESS, PENDING_EVIDENCE, CLOSED, BREACHED
    )
    created_at = Column(
        TIMESTAMP,
        default=datetime.utcnow
    )

    # Relationships
    mandate = relationship(
        "Mandate",
        back_populates="maps"
    )
    assignments = relationship(
        "Assignment",
        back_populates="map",
        cascade="all, delete-orphan"
    )
    evidence_submissions = relationship(
        "Evidence",
        back_populates="map",
        cascade="all, delete-orphan"
    )
    audit_entry = relationship(
        "AuditLog",
        back_populates="map",
        uselist=False
        # One-to-one: a MAP has at most one compliance certificate
    )

    def __repr__(self):
        return (
            f"<Map id={self.id} "
            f"priority_tier={self.priority_tier} "
            f"mpi_score={self.mpi_score} "
            f"status={self.status}>"
        )


# ============================================================
# MODEL 3: Assignment
# Maps to the assignments table
# Stores 3-LoD routing assignments — 3 rows per MAP
# ============================================================

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    map_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maps.id", ondelete="CASCADE"),
        nullable=False
    )
    line_number = Column(
        SmallInteger,
        nullable=False
        # 1 = Business Unit Owner     (1st Line of Defense)
        # 2 = Compliance Officer      (2nd Line of Defense)
        # 3 = Internal Audit          (3rd Line of Defense)
    )
    role = Column(
        String(100),
        nullable=False
        # e.g. "Retail Banking Head", "Compliance Officer", "Internal Audit"
    )
    department = Column(
        String(100),
        nullable=False
        # e.g. "Retail Banking", "Compliance", "Internal Audit"
    )
    assignment_text = Column(
        Text,
        nullable=False
        # Role-specific instruction:
        # Line 1: "Action: Update KYC process for dormant accounts by Sept 30"
        # Line 2: "Monitor: Track 1st LoD progress, MPI score 7.8, 130 days remaining"
        # Line 3: "Audit Queue: Schedule evidence audit post-completion for MAP-003"
    )
    acknowledged = Column(
        Boolean,
        default=False
        # Tracks whether the assignee has opened and acknowledged the MAP
    )
    assigned_at = Column(
        TIMESTAMP,
        default=datetime.utcnow
    )

    # Relationship
    map = relationship(
        "Map",
        back_populates="assignments"
    )

    def __repr__(self):
        return (
            f"<Assignment id={self.id} "
            f"map_id={self.map_id} "
            f"line_number={self.line_number} "
            f"department={self.department}>"
        )


# ============================================================
# MODEL 4: Evidence
# Maps to the evidence table
# Stores uploaded proof documents submitted against a MAP
# Multiple submissions allowed per MAP (for resubmissions)
# ============================================================

class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    map_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maps.id", ondelete="CASCADE"),
        nullable=False
    )
    file_name = Column(
        String(255),
        nullable=False
    )
    file_hash = Column(
        String(64),
        nullable=False
        # SHA-256 hex digest of the uploaded file
        # 64 characters exactly for SHA-256
        # Populated by Gate 2 of the Validation Engine
    )
    upload_date = Column(
        TIMESTAMP,
        default=datetime.utcnow
        # Used by Gate 1: must be before MAP deadline
    )
    document_date = Column(
        Date,
        nullable=True
        # Extracted from document content by spaCy
        # Used by Gate 3: must be after regulation date_issued
    )
    semantic_score = Column(
        Numeric(4, 3),
        nullable=True
        # Gemini 1.5 Flash match score: 0.000 to 1.000
        # >= 0.85  -> MAP auto-closed
        # 0.60-0.84 -> Flagged for human review
        # < 0.60   -> Rejected, resubmission requested
    )
    gate_1_status = Column(String(20), default="PENDING")
    gate_2_status = Column(String(20), default="PENDING")
    gate_3_status = Column(String(20), default="PENDING")
    gate_4_status = Column(String(20), default="PENDING")
    # Individual gate results: PASSED, FAILED, PENDING

    gate_status = Column(
        String(20),
        default="PENDING"
        # Overall result: PASSED, FAILED, PARTIAL, PENDING
    )
    failure_reason = Column(
        Text,
        nullable=True
        # Populated when gate_status is FAILED or PARTIAL
        # Tells the submitter exactly what is missing or wrong
    )
    created_at = Column(
        TIMESTAMP,
        default=datetime.utcnow
    )

    # Relationships
    map = relationship(
        "Map",
        back_populates="evidence_submissions"
    )
    audit_entry = relationship(
        "AuditLog",
        back_populates="evidence",
        uselist=False
    )

    def __repr__(self):
        return (
            f"<Evidence id={self.id} "
            f"map_id={self.map_id} "
            f"gate_status={self.gate_status} "
            f"semantic_score={self.semantic_score}>"
        )


# ============================================================
# MODEL 5: AuditLog
# Maps to the audit_log table
# Stores compliance certificates for every closed MAP
# One record per successfully closed MAP
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    map_id = Column(
        UUID(as_uuid=True),
        ForeignKey("maps.id", ondelete="CASCADE"),
        nullable=False
    )
    evidence_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence.id"),
        nullable=False
    )
    closed_at = Column(
        TIMESTAMP,
        default=datetime.utcnow
    )
    semantic_score = Column(
        Numeric(4, 3),
        nullable=False
        # Final semantic score that triggered closure
    )
    certificate_json = Column(
        JSONB,
        nullable=False
        # Full compliance certificate stored as structured JSON:
        # {
        #   "map_id": "...",
        #   "regulation_reference": "...",
        #   "obligation_text": "...",
        #   "closed_at": "...",
        #   "evidence_file_name": "...",
        #   "evidence_file_hash": "...",
        #   "semantic_score": 0.91,
        #   "gate_results": {
        #     "gate_1": "PASSED",
        #     "gate_2": "PASSED",
        #     "gate_3": "PASSED",
        #     "gate_4": "PASSED"
        #   },
        #   "validator": "IntelliMandate v1.0"
        # }
    )
    created_at = Column(
        TIMESTAMP,
        default=datetime.utcnow
    )

    # Relationships
    map = relationship(
        "Map",
        back_populates="audit_entry"
    )
    evidence = relationship(
        "Evidence",
        back_populates="audit_entry"
    )

    def __repr__(self):
        return (
            f"<AuditLog id={self.id} "
            f"map_id={self.map_id} "
            f"semantic_score={self.semantic_score} "
            f"closed_at={self.closed_at}>"
        )