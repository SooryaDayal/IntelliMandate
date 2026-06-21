"""
Offline Circular Ingestion
File: backend/scrapers/offline_ingestion.py

Handles two offline input sources:
  1. demo_data/ folder — pre-downloaded Canara Bank relevant PDFs
  2. User-uploaded PDFs — from Streamlit upload_circular.py page

No internet required. Uses PyMuPDF for text extraction and
the existing classifier.py for signal classification.

Returns the same dict format as fetch_rbi_circulars() so the
rest of the pipeline (orchestrator, extraction agent, routing
engine) works identically regardless of source.
"""

import io
import json
import os
import zipfile
from datetime import datetime, date
from typing import Optional

import fitz  # PyMuPDF

from backend.scrapers.classifier import classify_circular, detect_source_from_url


# ============================================================
# CONSTANTS
# ============================================================

DEFAULT_DEMO_DIR = "demo_data/"
MAX_PAGES_TO_EXTRACT = 50


# ============================================================
# HELPER: EXTRACT TEXT FROM PDF BYTES
# Same logic as pdf_extractor.py but works on raw bytes
# without needing a download step first
# ============================================================

def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Optional[str]:
    """
    Extracts text from PDF bytes using PyMuPDF.
    Used for both file-on-disk and uploaded-bytes ingestion.
    """
    try:
        doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
        total_pages = len(doc)
        pages_to_read = min(total_pages, MAX_PAGES_TO_EXTRACT)

        extracted_pages = []
        for page_num in range(pages_to_read):
            page = doc[page_num]
            page_text = page.get_text("text")
            if page_text.strip():
                extracted_pages.append(
                    f"--- Page {page_num + 1} ---\n{page_text.strip()}"
                )

        doc.close()

        if not extracted_pages:
            print("[Offline Ingestion] No text extracted — PDF may be scanned/image-only.")
            return None

        full_text = "\n\n".join(extracted_pages)
        print(
            f"[Offline Ingestion] Extracted {len(full_text):,} characters "
            f"from {len(extracted_pages)} pages."
        )
        return full_text

    except Exception as e:
        print(f"[Offline Ingestion] PDF extraction error: {e}")
        return None


def _parse_date_safe(date_str) -> Optional[date]:
    """Parses a date string in common formats. Returns None on failure."""
    if not date_str:
        return None
    if isinstance(date_str, date):
        return date_str

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(date_str), fmt).date()
        except ValueError:
            continue
    return None


# ============================================================
# FUNCTION 1: INGEST A SINGLE PDF FILE FROM DISK
# ============================================================

def ingest_pdf_file(
    file_path: str,
    title:     Optional[str] = None,
    source:    str = "RBI",
    ref_number: str = "",
    date_issued: Optional[date] = None,
) -> dict:
    """
    Ingests a single PDF file from disk.
    Used for demo_data/ folder circulars.

    Args:
        file_path:   Path to the PDF file on disk
        title:       Circular title — if None, uses filename
        source:      Regulatory authority — RBI, CERT_IN, NPCI, etc.
        ref_number:  Circular reference number
        date_issued: Date the circular was issued

    Returns:
        Dict matching fetch_rbi_circulars() format:
        {title, date, url, ref_number, doc_type, source,
         raw_text, signal_type, confidence}
    """
    if not os.path.exists(file_path):
        print(f"[Offline Ingestion] File not found: {file_path}")
        return {}

    with open(file_path, "rb") as f:
        pdf_bytes = f.read()

    filename = os.path.basename(file_path)
    final_title = title or filename.replace(".pdf", "").replace("_", " ").title()

    raw_text = _extract_text_from_pdf_bytes(pdf_bytes)

    classification = classify_circular(
        title      = final_title,
        text       = raw_text or "",
        ref_number = ref_number,
    )

    return {
        "title":       final_title,
        "date":        date_issued,
        "url":         f"file://{file_path}",
        "ref_number":  ref_number,
        "doc_type":    "PDF",
        "source":      source.upper(),
        "raw_text":    raw_text or "",
        "signal_type": classification["signal_type"],
        "confidence":  classification["confidence"],
        "ingestion_method": "OFFLINE_FILE",
    }


# ============================================================
# FUNCTION 2: INGEST PDF FROM BYTES (Streamlit upload)
# ============================================================

def ingest_pdf_bytes(
    file_bytes:  bytes,
    filename:    str,
    title:       Optional[str] = None,
    source:      str = "RBI",
    ref_number:  str = "",
) -> dict:
    """
    Ingests a PDF from raw bytes — used when a compliance
    officer uploads a circular directly through Streamlit.

    Args:
        file_bytes: Raw PDF bytes from the upload
        filename:   Original filename from the upload
        title:      Circular title — if None, uses filename
        source:     Regulatory authority
        ref_number: Circular reference number, if known

    Returns:
        Dict matching fetch_rbi_circulars() format
    """
    final_title = title or filename.replace(".pdf", "").replace("_", " ").title()

    raw_text = _extract_text_from_pdf_bytes(file_bytes)

    classification = classify_circular(
        title      = final_title,
        text       = raw_text or "",
        ref_number = ref_number,
    )

    print(
        f"[Offline Ingestion] Uploaded circular '{final_title[:50]}' "
        f"classified as {classification['signal_type']} "
        f"({classification['confidence']} confidence)"
    )

    return {
        "title":       final_title,
        "date":        datetime.now().date(),
        "url":         f"upload://{filename}",
        "ref_number":  ref_number,
        "doc_type":    "PDF",
        "source":      source.upper(),
        "raw_text":    raw_text or "",
        "signal_type": classification["signal_type"],
        "confidence":  classification["confidence"],
        "ingestion_method": "MANUAL_UPLOAD",
    }


# ============================================================
# FUNCTION 3: LOAD ALL DEMO DATA
# ============================================================

def load_demo_data(demo_dir: str = DEFAULT_DEMO_DIR) -> list[dict]:
    """
    Loads all pre-downloaded demo circulars from the demo_data/
    folder. Reads demo_data/metadata.json for titles, ref numbers,
    sources, and dates — then ingests each corresponding PDF.

    Used for fully offline demo runs with zero internet.

    Args:
        demo_dir: Path to the demo_data folder

    Returns:
        List of dicts, same format as fetch_rbi_circulars()
    """
    metadata_path = os.path.join(demo_dir, "metadata.json")

    if not os.path.exists(metadata_path):
        print(f"[Offline Ingestion] metadata.json not found at {metadata_path}")
        return []

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata_list = json.load(f)

    print(f"[Offline Ingestion] Loading {len(metadata_list)} demo circulars...")

    results = []

    for entry in metadata_list:
        filename    = entry.get("filename", "")
        file_path   = os.path.join(demo_dir, filename)

        if not os.path.exists(file_path):
            print(f"[Offline Ingestion] Skipping missing file: {file_path}")
            continue

        circular = ingest_pdf_file(
            file_path   = file_path,
            title       = entry.get("title"),
            source      = entry.get("source", "RBI"),
            ref_number  = entry.get("ref_number", ""),
            date_issued = _parse_date_safe(entry.get("date")),
        )

        if circular:
            results.append(circular)
            print(
                f"[Offline Ingestion] Loaded: {circular['title'][:50]}... "
                f"→ {circular['signal_type']}"
            )

    print(f"[Offline Ingestion] Demo data load complete. {len(results)} circulars loaded.")
    return results


# ============================================================
# FUNCTION 4: INGEST A ZIP FILE OF MULTIPLE PDFs
# ============================================================

def ingest_zip_file(
    zip_path: str = None,
    zip_bytes: bytes = None,
    source: str = "RBI",
) -> list[dict]:
    """
    Extracts a ZIP file and ingests every PDF inside.
    Accepts either a file path on disk OR raw zip bytes
    (for Streamlit ZIP uploads).

    Args:
        zip_path:  Path to ZIP file on disk (optional)
        zip_bytes: Raw bytes of an uploaded ZIP (optional)
        source:    Default regulatory authority for all PDFs inside

    Returns:
        List of dicts, one per PDF found in the ZIP
    """
    if zip_path:
        zf = zipfile.ZipFile(zip_path, "r")
    elif zip_bytes:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
    else:
        print("[Offline Ingestion] No zip_path or zip_bytes provided.")
        return []

    results = []
    pdf_names = [n for n in zf.namelist() if n.lower().endswith(".pdf")]

    print(f"[Offline Ingestion] Found {len(pdf_names)} PDFs in ZIP archive.")

    for pdf_name in pdf_names:
        try:
            pdf_bytes = zf.read(pdf_name)
            circular = ingest_pdf_bytes(
                file_bytes = pdf_bytes,
                filename   = os.path.basename(pdf_name),
                source     = source,
            )
            if circular:
                results.append(circular)
        except Exception as e:
            print(f"[Offline Ingestion] Error ingesting {pdf_name} from ZIP: {e}")
            continue

    zf.close()
    print(f"[Offline Ingestion] ZIP ingestion complete. {len(results)} circulars loaded.")
    return results


# ============================================================
# STANDALONE TEST
# Run: python -m backend.scrapers.offline_ingestion
# ============================================================

if __name__ == "__main__":
    print("Testing offline ingestion (demo_data/ folder)...\n")

    if not os.path.exists(DEFAULT_DEMO_DIR):
        print(
            f"demo_data/ folder not found at '{DEFAULT_DEMO_DIR}'.\n"
            f"Create it and add metadata.json + PDFs first (Task A-3-6)."
        )
    else:
        circulars = load_demo_data()

        if circulars:
            print(f"\n--- Loaded {len(circulars)} circulars ---")
            for i, c in enumerate(circulars, 1):
                print(f"\n[{i}] {c['title'][:60]}")
                print(f"     Source      : {c['source']}")
                print(f"     Signal Type : {c['signal_type']}")
                print(f"     Confidence  : {c['confidence']}")
                print(f"     Text length : {len(c['raw_text'])} chars")
        else:
            print("No circulars loaded. Check demo_data/metadata.json exists.")