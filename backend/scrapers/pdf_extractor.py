"""
PDF Text Extractor
File: backend/scrapers/pdf_extractor.py

Two responsibilities:
  1. Fetch the RBI circular detail page and find the actual PDF link
  2. Download the PDF and extract full text using PyMuPDF (fitz)

RBI circular flow:
  Scraper gives us → BS_CircularIndexDisplay.aspx?Id=XXXXX (detail page)
  Detail page contains → link to actual PDF on rbidocs.rbi.org.in
  PDF extractor downloads → PDF bytes → extracts text page by page

Install: pip install pymupdf
"""

import io
import time
import requests
import fitz  # PyMuPDF
from typing import Optional
from bs4 import BeautifulSoup


# ============================================================
# CONSTANTS
# ============================================================

RBIDOCS_BASE = "https://rbidocs.rbi.org.in"
RBI_BASE     = "https://www.rbi.org.in"

# Same headers as scraper — no Accept-Encoding to avoid Brotli
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
    "Connection":      "keep-alive",
}

PDF_HEADERS = {
    **HEADERS,
    "Accept": "application/pdf,application/octet-stream,*/*;q=0.8",
}

REQUEST_DELAY_SECONDS = 1
MAX_PAGES_TO_EXTRACT  = 50  # Safety cap — most RBI circulars are under 20 pages


# ============================================================
# HELPER: SAFE HTTP GET
# ============================================================

def safe_get(
    url: str,
    timeout: int = 20,
    headers: dict = None
) -> Optional[requests.Response]:
    _headers = headers or HEADERS

    for attempt in range(3):
        try:
            response = requests.get(url, headers=_headers, timeout=timeout)

            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                print(f"[PDF Extractor] 403 Forbidden: {url}")
                return None
            elif response.status_code == 404:
                print(f"[PDF Extractor] 404 Not Found: {url}")
                return None
            elif response.status_code == 429:
                wait = (attempt + 1) * 5
                print(f"[PDF Extractor] Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"[PDF Extractor] HTTP {response.status_code} attempt {attempt + 1}: {url}")

        except requests.exceptions.Timeout:
            print(f"[PDF Extractor] Timeout attempt {attempt + 1}: {url}")
        except requests.exceptions.ConnectionError:
            print(f"[PDF Extractor] Connection error attempt {attempt + 1}: {url}")
        except Exception as e:
            print(f"[PDF Extractor] Unexpected error: {e}")

        time.sleep(REQUEST_DELAY_SECONDS * (attempt + 1))

    return None


# ============================================================
# STEP 1: FIND PDF LINK ON CIRCULAR DETAIL PAGE
#
# RBI circular detail pages (BS_CircularIndexDisplay.aspx?Id=XXXX)
# contain one or more links to the actual PDF documents.
# This function fetches that page and extracts the PDF URL.
# ============================================================

def find_pdf_url(detail_page_url: str) -> Optional[str]:
    """
    Fetches the RBI circular detail page and finds the PDF download link.

    Args:
        detail_page_url: URL of the circular detail page
                         e.g. https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx?Id=13475

    Returns:
        Full URL of the PDF document, or None if not found.
    """
    print(f"[PDF Extractor] Fetching detail page: {detail_page_url}")
    response = safe_get(detail_page_url)

    if not response:
        return None

    # Verify we got HTML
    if "<" not in response.text[:100]:
        print("[PDF Extractor] Detail page response is not HTML.")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    pdf_url = None

    # Strategy 1: Look for direct .pdf links
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.lower().endswith(".pdf"):
            pdf_url = _build_full_url(href)
            print(f"[PDF Extractor] Found PDF link: {pdf_url}")
            break

    # Strategy 2: Look for links on rbidocs.rbi.org.in domain
    if not pdf_url:
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip()
            if "rbidocs.rbi.org.in" in href:
                pdf_url = href
                print(f"[PDF Extractor] Found rbidocs link: {pdf_url}")
                break

    # Strategy 3: Look for links with common RBI document path patterns
    if not pdf_url:
        for tag in soup.find_all("a", href=True):
            href = tag["href"].strip().lower()
            if any(pattern in href for pattern in ["/rdocs/", "/pdfs/", "notification"]):
                pdf_url = _build_full_url(tag["href"].strip())
                print(f"[PDF Extractor] Found document link: {pdf_url}")
                break

    if not pdf_url:
        print(f"[PDF Extractor] No PDF link found on detail page: {detail_page_url}")

    return pdf_url


def _build_full_url(href: str) -> str:
    """Converts relative href to full URL."""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return RBI_BASE + href
    return RBI_BASE + "/" + href


# ============================================================
# STEP 2: DOWNLOAD PDF BYTES
# ============================================================

def download_pdf_bytes(pdf_url: str) -> Optional[bytes]:
    """
    Downloads a PDF from a URL and returns raw bytes.

    Args:
        pdf_url: Direct URL to the PDF file

    Returns:
        PDF content as bytes, or None on failure.
    """
    print(f"[PDF Extractor] Downloading PDF: {pdf_url}")
    response = safe_get(pdf_url, timeout=30, headers=PDF_HEADERS)

    if not response:
        return None

    # Verify response is actually a PDF
    content_type = response.headers.get("Content-Type", "")
    content_bytes = response.content

    if not content_bytes:
        print("[PDF Extractor] Empty response body.")
        return None

    # Check PDF magic bytes: PDFs always start with %PDF
    if not content_bytes.startswith(b"%PDF"):
        print(
            f"[PDF Extractor] Response is not a valid PDF.\n"
            f"  Content-Type: {content_type}\n"
            f"  First bytes: {content_bytes[:20]}"
        )
        return None

    print(f"[PDF Extractor] Downloaded {len(content_bytes):,} bytes.")
    return content_bytes


# ============================================================
# STEP 3: EXTRACT TEXT FROM PDF BYTES
# ============================================================

def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> Optional[str]:
    """
    Extracts full text from PDF bytes using PyMuPDF (fitz).

    Args:
        pdf_bytes: Raw PDF file content as bytes

    Returns:
        Extracted text as a single string, or None on failure.
    """
    try:
        # Open PDF from memory — no temp file needed
        doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")

        total_pages = len(doc)
        pages_to_read = min(total_pages, MAX_PAGES_TO_EXTRACT)

        print(f"[PDF Extractor] PDF has {total_pages} pages. Reading {pages_to_read}.")

        extracted_pages = []

        for page_num in range(pages_to_read):
            page = doc[page_num]

            # Extract text with layout preservation
            # "text" mode: plain text, reads top-to-bottom left-to-right
            page_text = page.get_text("text")

            if page_text.strip():
                extracted_pages.append(
                    f"--- Page {page_num + 1} ---\n{page_text.strip()}"
                )

        doc.close()

        if not extracted_pages:
            print("[PDF Extractor] No text extracted — PDF may be scanned/image-only.")
            return None

        full_text = "\n\n".join(extracted_pages)
        print(
            f"[PDF Extractor] Extracted {len(full_text):,} characters "
            f"from {len(extracted_pages)} pages."
        )
        return full_text

    except fitz.FileDataError:
        print("[PDF Extractor] PyMuPDF could not open file — corrupted or invalid PDF.")
        return None
    except Exception as e:
        print(f"[PDF Extractor] Unexpected error during extraction: {e}")
        return None


# ============================================================
# STEP 4: EXTRACT TEXT FROM HTML DETAIL PAGE
# Used when no PDF is available — extracts circular text from HTML
# ============================================================

def extract_text_from_html(detail_page_url: str) -> Optional[str]:
    """
    Fallback for circulars that are HTML-only (no PDF).
    Extracts the main content text from the RBI circular detail page.

    Args:
        detail_page_url: URL of the circular detail page

    Returns:
        Extracted text content, or None on failure.
    """
    print(f"[PDF Extractor] Extracting HTML text from: {detail_page_url}")
    response = safe_get(detail_page_url)

    if not response:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove navigation, headers, footers, scripts, styles
    for tag in soup(["script", "style", "nav", "header", "footer", "form"]):
        tag.decompose()

    # Try to find the main content div
    content = (
        soup.find("div", {"id": "wrapper"})
        or soup.find("div", {"class": "content"})
        or soup.find("div", {"id": "content"})
        or soup.find("div", {"class": "innerbox"})
        or soup.find("td", {"class": "tabledata"})
        or soup.find("body")
    )

    if not content:
        print("[PDF Extractor] Could not find main content area in HTML.")
        return None

    text = content.get_text(separator="\n", strip=True)

    # Clean up excessive whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned = "\n".join(lines)

    if len(cleaned) < 100:
        print("[PDF Extractor] Extracted HTML text is too short — likely navigation only.")
        return None

    print(f"[PDF Extractor] Extracted {len(cleaned):,} characters from HTML page.")
    return cleaned


# ============================================================
# MAIN ENTRY POINT
# Full pipeline: detail page URL → extracted text
# ============================================================

def extract_circular_text(circular: dict) -> Optional[str]:
    """
    Main function called by the Extraction Agent (Member B).
    Takes a circular dict from the RBI scraper and returns its full text.

    Pipeline:
      1. Check if URL is already a direct PDF → extract immediately
      2. If HTML detail page → find PDF link → download → extract
      3. If no PDF found → extract HTML text as fallback

    Args:
        circular: Dict from fetch_rbi_circulars() containing:
                  url, title, doc_type, date, ref_number, department

    Returns:
        Extracted text string, or None if extraction fails.
    """
    url      = circular.get("url", "")
    doc_type = circular.get("doc_type", "HTML")
    title    = circular.get("title", "Unknown")

    print(f"\n[PDF Extractor] Processing: {title[:60]}...")

    if not url:
        print("[PDF Extractor] No URL provided.")
        return None

    # Case 1: URL is already a direct PDF
    if url.lower().endswith(".pdf") or doc_type == "PDF":
        pdf_bytes = download_pdf_bytes(url)
        if pdf_bytes:
            return extract_text_from_pdf_bytes(pdf_bytes)

    # Case 2: URL is an HTML detail page
    # Try to find the PDF link on the detail page first
    pdf_url = find_pdf_url(url)

    if pdf_url:
        time.sleep(REQUEST_DELAY_SECONDS)
        pdf_bytes = download_pdf_bytes(pdf_url)
        if pdf_bytes:
            return extract_text_from_pdf_bytes(pdf_bytes)

    # Case 3: No PDF found — fall back to HTML text extraction
    print("[PDF Extractor] No PDF available. Extracting HTML text as fallback.")
    return extract_text_from_html(url)


# ============================================================
# STANDALONE TEST
# Run: python -m backend.scrapers.pdf_extractor
# Tests extraction on the first circular from the live RBI scraper
# ============================================================

if __name__ == "__main__":
    from backend.scrapers.rbi_scraper import fetch_rbi_circulars

    print("Fetching latest RBI circulars...")
    circulars = fetch_rbi_circulars(max_circulars=3)

    if not circulars:
        print("No circulars fetched. Cannot test PDF extractor.")
        exit(1)

    # Test on first circular
    test_circular = circulars[0]
    print(f"\nTesting PDF extraction on:")
    print(f"  Title  : {test_circular['title']}")
    print(f"  URL    : {test_circular['url']}")
    print(f"  Type   : {test_circular['doc_type']}")

    text = extract_circular_text(test_circular)

    if text:
        print(f"\n--- Extracted Text Preview (first 1000 chars) ---")
        print(text[:1000])
        print(f"\n--- Total extracted: {len(text):,} characters ---")
    else:
        print("\nText extraction failed for this circular.")
        print("This may happen if the RBI page requires JavaScript to render.")
        print("Try with a different circular URL.")