# IntelliMandate

> **Agentic Regulatory Intelligence Platform for Canara Bank**

IntelliMandate is an autonomous regulatory intelligence platform that transforms RBI circulars and regulatory mandates into actionable compliance tasks. Instead of relying on manual interpretation and tracking, the platform automatically identifies regulatory obligations, prioritizes them based on financial and operational risk, routes them to the appropriate Canara Bank Wings, and validates submitted compliance evidence.

Designed for the Canara Bank SuRaksha Hackathon, IntelliMandate demonstrates how an agentic AI workflow can reduce compliance risk, improve governance, and create a transparent audit trail while operating completely offline.

---

## Problem Statement

Banks receive hundreds of regulatory circulars every year from regulators such as RBI, SEBI, FIU-IND, IRDAI, and MCA. Compliance teams must manually:

* Read lengthy circulars
* Identify actionable obligations
* Assess financial risk
* Assign responsibilities
* Track deadlines
* Validate evidence
* Prepare audit documentation

This manual workflow is time-consuming, error-prone, and can lead to costly regulatory penalties.

---

# Solution

IntelliMandate automates the complete compliance lifecycle using an agentic Reason–Act–Observe (ReAct) workflow.

The platform:

* Ingests RBI circulars (online or offline)
* Classifies the regulatory signal
* Extracts regulatory obligations
* Identifies entities such as deadlines, penalties, clauses, and authorities
* Calculates a MAP Priority Index (MPI)
* Routes compliance actions using Canara Bank's Three Lines of Defense Wing structure
* Tracks compliance progress
* Validates submitted evidence using a multi-stage validation engine
* Generates tamper-proof compliance certificates and audit logs

---

# Designed for Canara Bank

IntelliMandate is specifically designed around Canara Bank's compliance landscape.

The system incorporates:

* Canara Bank's actual Wing-based organizational structure
* Three Lines of Defense governance model
* MAP Priority Index calibrated using documented RBI penalty categories
* Regulatory routing aligned with Compliance, Retail Banking, Commercial Banking, Risk Management, Operations, Treasury, Internal Audit, and other Wings

The project demonstrates how autonomous compliance intelligence could help reduce risks associated with regulatory observations involving areas such as:

* KYC & CKYCR
* AML / PMLA
* Priority Sector Lending
* Credit Information Companies
* BSBDA Compliance
* Inoperative Accounts
* Interest Rate Compliance

---

# Key Features

### Autonomous ReAct Orchestrator

Unlike a fixed pipeline, IntelliMandate continuously reasons about the current state before selecting the next tool.

Reason → Act → Observe → Repeat

---

### Regulatory Obligation Extraction

Automatically extracts:

* Mandatory obligations
* Deadlines
* Regulatory clauses
* Monetary penalties
* Regulatory authorities

---

### MAP Priority Index (MPI)

Every compliance obligation receives a dynamic priority score using:

* Penalty exposure
* Deadline urgency
* Regulatory authority weight
* Historical recurrence risk

Priority Levels

* 🔴 Critical
* 🟠 High
* 🟡 Medium
* 🟢 Low

---

### Intelligent Wing Routing

Automatically routes compliance actions according to Canara Bank's Three Lines of Defense:

**1st Line**

* Retail Banking Wing
* Commercial Banking Wing
* Operations Wing
* Treasury Wing
* International Banking Wing

**2nd Line**

* Compliance Wing
* Risk Management Wing

**3rd Line**

* Internal Audit Wing

---

### Knowledge Graph

Tracks relationships between:

* Regulatory mandates
* Amendments
* References
* Superseded circulars
* Existing compliance obligations

This enables impact analysis whenever a regulation changes.

---

### Evidence Validation Engine

Evidence passes through four validation gates:

1. Deadline Validation
2. File Integrity (SHA-256)
3. Temporal Validation
4. Semantic Similarity Validation

Successful validation automatically closes the compliance task and generates an audit certificate.

---

### Offline First

The platform works without cloud-based AI services.

Supported inputs:

* RBI website scraping
* Manual PDF upload
* Offline demo data
* ZIP imports

---

# System Architecture

```text
             RBI Circular / PDF Upload
                      │
                      ▼
           Signal Classification Engine
                      │
                      ▼
        ReAct Agentic Orchestrator
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
 Obligation      Entity        Delta Analysis
 Extraction     Extraction
        │
        ▼
   MAP Generation
        │
        ▼
  MAP Priority Index (MPI)
        │
        ▼
 Wing Routing Engine
        │
        ▼
 PostgreSQL Database
        │
        ▼
    Dashboard
        │
        ▼
 Evidence Validation
        │
        ▼
 Compliance Certificate
```

---

# Technology Stack

| Component                | Technology            |
| ------------------------ | --------------------- |
| Backend                  | FastAPI               |
| Frontend                 | React             |
| Database                 | PostgreSQL            |
| Background Tasks         | Celery                |
| Cache                    | Redis                 |
| NLP                      | spaCy                 |
| Financial Classification | FinBERT               |
| Semantic Search          | Sentence Transformers |
| Vector Database          | ChromaDB              |
| Knowledge Graph          | NetworkX              |
| PDF Processing           | PyMuPDF               |
| Web Scraping             | BeautifulSoup         |
| ORM                      | SQLAlchemy            |
| Language                 | Python                |

---

# What Makes IntelliMandate Different?

* True ReAct Agent (not a sequential workflow)
* Offline AI processing
* Autonomous compliance extraction
* Dynamic risk prioritization
* Knowledge graph for regulatory impact analysis
* Intelligent Wing routing
* Multi-stage validation engine
* Complete audit trail generation

---

# What Is NOT Used

IntelliMandate intentionally avoids dependence on cloud-hosted LLMs.

Not used:

* OpenAI API
* Claude API
* Gemini API
* Groq API
* Ollama
* LM Studio
* Remote inference APIs
* Paid AI services

---

# Repository Structure

```text
intellimandate/
├── backend/
├── frontend/
├── agents/
├── database/
├── demo_data/
├── tests/
├── README.md
├── requirements.txt
└── .gitignore
```

---

# Getting Started

## 1. Clone the repository

```bash
git clone https://github.com/SooryaDayal/IntelliMandate.git
cd IntelliMandate
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

## 3. Download spaCy models

```bash
python -m spacy download en_core_web_sm
python -m spacy download en_core_web_trf
```

## 4. Configure PostgreSQL

Create a PostgreSQL database and update your environment variables or configuration.

## 5. Start Redis (required for background orchestration tasks).

redis-server

## 6. Start the backend

```bash
uvicorn backend.main:app --reload
```

Backend documentation:

```
http://localhost:8000/docs
```

## 6. Launch the frontend

```bash
npm run dev
```

---

# Future Improvements

* Multi-regulator support
* Automated regulatory monitoring
* Email and Teams notifications
* Compliance analytics dashboard
* Predictive compliance risk scoring
* OCR support for scanned circulars
* Enterprise authentication
* Role-based access control

---

# Team

**Backend Lead**

* FastAPI
* Database
* Routing Engine
* Knowledge Graph

**AI & Intelligence Lead**

* ReAct Orchestrator
* NLP Pipeline
* Validation Engine
* MAP Priority Index

**Frontend Lead**

* React Dashboard
* Upload Workflow
* Evidence Validation UI
* Audit Trail

---

# License

This project was developed for the **Canara Bank SuRaksha Hackathon** as an educational and demonstration prototype.
