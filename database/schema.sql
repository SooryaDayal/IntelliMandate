-- IntelliMandate Database Schema
-- Run this file once to initialize the database
-- psql -U postgres -d intellimandate -f schema.sql

-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ============================================================
-- TABLE 1: mandates
-- Stores raw regulatory documents fetched by the Monitor Agent
-- ============================================================

CREATE TABLE IF NOT EXISTS mandates (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          VARCHAR(50) NOT NULL,
    -- RBI, SEBI, IRDAI, FIU_IND, MCA, GAZETTE
    signal_type     VARCHAR(30) NOT NULL,
    -- MANDATORY_IMMEDIATE, MANDATORY_FUTURE, CIRCULAR_AMENDMENT,
    -- CONSULTATION_PAPER, ADVISORY
    title           TEXT NOT NULL,
    raw_text        TEXT,
    url             TEXT,
    date_issued     DATE,
    delta_summary   TEXT,
    -- Populated only for CIRCULAR_AMENDMENT signal type
    -- Stores the diff output showing what changed
    processed       BOOLEAN DEFAULT FALSE,
    -- FALSE until MAP Extraction Agent has processed it
    created_at      TIMESTAMP DEFAULT NOW()
);


-- ============================================================
-- TABLE 2: maps
-- Stores Measurable Action Points extracted from mandates
-- ============================================================

CREATE TABLE IF NOT EXISTS maps (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mandate_id              UUID NOT NULL REFERENCES mandates(id) ON DELETE CASCADE,
    obligation_text         TEXT NOT NULL,
    -- What the bank must do (plain language)
    measurable_condition    TEXT NOT NULL,
    -- Machine-verifiable definition of done
    -- e.g. "% dormant accounts with refreshed KYC >= 100"
    deadline                DATE,
    penalty_exposure        NUMERIC(15, 2) DEFAULT 0,
    -- Rupee value extracted from regulation text
    evidence_required       TEXT,
    -- Comma-separated list of required document types
    regulatory_reference    TEXT,
    -- Exact clause citation e.g. "Master Direction Clause 38(ii)"
    map_type                VARCHAR(30),
    -- PROCESS_CHANGE, POLICY_UPDATE, SYSTEM_CHANGE, REPORTING_OBLIGATION
    mpi_score               NUMERIC(5, 2) DEFAULT 0,
    -- MAP Priority Index score 0-100
    priority_tier           VARCHAR(20) DEFAULT 'LOW',
    -- CRITICAL, HIGH, MEDIUM, LOW
    status                  VARCHAR(20) DEFAULT 'OPEN',
    -- OPEN, IN_PROGRESS, PENDING_EVIDENCE, CLOSED, BREACHED
    created_at              TIMESTAMP DEFAULT NOW()
);


-- ============================================================
-- TABLE 3: assignments
-- Stores 3-LoD routing assignments per MAP
-- Each MAP generates exactly 3 assignment rows (one per line)
-- ============================================================

CREATE TABLE IF NOT EXISTS assignments (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    map_id              UUID NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    line_number         SMALLINT NOT NULL CHECK (line_number IN (1, 2, 3)),
    -- 1 = Business Unit (1st LoD)
    -- 2 = Compliance Officer (2nd LoD)
    -- 3 = Internal Audit (3rd LoD)
    role                VARCHAR(100) NOT NULL,
    -- e.g. "Compliance Officer", "Retail Banking Head", "Internal Audit"
    department          VARCHAR(100) NOT NULL,
    -- e.g. "Compliance", "Retail Banking", "IT", "Risk Management"
    assignment_text     TEXT NOT NULL,
    -- Role-specific instruction tailored to that line's responsibility
    acknowledged        BOOLEAN DEFAULT FALSE,
    -- Tracks whether the assignee has seen the MAP
    assigned_at         TIMESTAMP DEFAULT NOW()
);


-- ============================================================
-- TABLE 4: evidence
-- Stores uploaded proof documents submitted against a MAP
-- Multiple evidence submissions allowed per MAP (for resubmissions)
-- ============================================================

CREATE TABLE IF NOT EXISTS evidence (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    map_id              UUID NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    file_name           VARCHAR(255) NOT NULL,
    file_hash           VARCHAR(64) NOT NULL,
    -- SHA-256 hex digest of the uploaded file (Gate 2)
    upload_date         TIMESTAMP DEFAULT NOW(),
    document_date       DATE,
    -- Extracted from the document content (Gate 3)
    semantic_score      NUMERIC(4, 3),
    -- Gemini match score 0.000 to 1.000 (Gate 4)
    gate_1_status       VARCHAR(20) DEFAULT 'PENDING',
    -- PASSED, FAILED, PENDING
    gate_2_status       VARCHAR(20) DEFAULT 'PENDING',
    gate_3_status       VARCHAR(20) DEFAULT 'PENDING',
    gate_4_status       VARCHAR(20) DEFAULT 'PENDING',
    gate_status         VARCHAR(20) DEFAULT 'PENDING',
    -- Overall: PASSED, FAILED, PARTIAL, PENDING
    failure_reason      TEXT,
    -- Populated when gate_status is FAILED or PARTIAL
    created_at          TIMESTAMP DEFAULT NOW()
);


-- ============================================================
-- TABLE 5: audit_log
-- Stores compliance certificates for every closed MAP
-- One record per successfully closed MAP
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    map_id              UUID NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    evidence_id         UUID NOT NULL REFERENCES evidence(id),
    closed_at           TIMESTAMP DEFAULT NOW(),
    semantic_score      NUMERIC(4, 3) NOT NULL,
    certificate_json    JSONB NOT NULL,
    -- Full compliance certificate stored as structured JSON:
    -- {
    --   "map_id": "...",
    --   "regulation_reference": "...",
    --   "closed_at": "...",
    --   "evidence_file_hash": "...",
    --   "semantic_score": 0.91,
    --   "gate_results": {
    --     "gate_1": "PASSED",
    --     "gate_2": "PASSED",
    --     "gate_3": "PASSED",
    --     "gate_4": "PASSED"
    --   },
    --   "validator": "IntelliMandate v1.0"
    -- }
    created_at          TIMESTAMP DEFAULT NOW()
);


-- ============================================================
-- INDEXES
-- Speed up the most frequent query patterns
-- ============================================================

-- MAPs sorted by MPI score (dashboard default view)
CREATE INDEX IF NOT EXISTS idx_maps_mpi_score
    ON maps (mpi_score DESC);

-- MAPs filtered by priority tier
CREATE INDEX IF NOT EXISTS idx_maps_priority_tier
    ON maps (priority_tier);

-- MAPs filtered by status (OPEN, CLOSED, etc.)
CREATE INDEX IF NOT EXISTS idx_maps_status
    ON maps (status);

-- MAPs belonging to a specific mandate
CREATE INDEX IF NOT EXISTS idx_maps_mandate_id
    ON maps (mandate_id);

-- Assignments for a specific MAP
CREATE INDEX IF NOT EXISTS idx_assignments_map_id
    ON assignments (map_id);

-- Evidence submissions for a specific MAP
CREATE INDEX IF NOT EXISTS idx_evidence_map_id
    ON evidence (map_id);

-- Audit log lookup by MAP
CREATE INDEX IF NOT EXISTS idx_audit_log_map_id
    ON audit_log (map_id);

-- Mandates filtered by source regulator
CREATE INDEX IF NOT EXISTS idx_mandates_source
    ON mandates (source);

-- Mandates filtered by signal type
CREATE INDEX IF NOT EXISTS idx_mandates_signal_type
    ON mandates (signal_type);

-- Unprocessed mandates (Monitor Agent queue)
CREATE INDEX IF NOT EXISTS idx_mandates_processed
    ON mandates (processed)
    WHERE processed = FALSE;