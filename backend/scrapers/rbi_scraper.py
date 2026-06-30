"""
RBI Circular Scraper
File: backend/scrapers/rbi_scraper.py

Scrapes RBI public notifications page and RSS feeds.
No login required. No API key. Completely free.

Sources:
  Primary  → https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx
  Fallback → https://www.rbi.org.in/scripts/rss.aspx (RSS feeds)

RBI table column layout (confirmed from live page):
  Col[0] → Department name
  Col[1] → Date (format: DD.M.YYYY e.g. 08.6.2026)
  Col[2] → Circular reference number (RBI/2026-2027/106...)
  Col[3] → Subject / Title (contains link to circular)
"""

import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, date
from typing import Optional
from bs4 import BeautifulSoup
from backend.scrapers.classifier import detect_source_from_url


# ============================================================
# CONSTANTS
# ============================================================

BASE_URL         = "https://www.rbi.org.in"
SCRIPTS_BASE_URL = "https://www.rbi.org.in/Scripts"

CIRCULAR_INDEX_URL = (
    "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx"
)

RBI_RSS_FEEDS = {
    "circulars":         "https://www.rbi.org.in/scripts/rss.aspx?Id=2",
    "notifications":     "https://www.rbi.org.in/scripts/rss.aspx?Id=6",
    "press_releases":    "https://www.rbi.org.in/scripts/rss.aspx?Id=5",
    "master_directions": "https://www.rbi.org.in/scripts/rss.aspx?Id=7",
}

# No Accept-Encoding — prevents Brotli compressed binary responses
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

REQUEST_DELAY_SECONDS = 2


# ============================================================
# HELPER: SAFE HTTP GET
# ============================================================

def safe_get(url: str, timeout: int = 15) -> Optional[requests.Response]:
    for attempt in range(3):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            if response.status_code == 200:
                return response
            elif response.status_code == 403:
                print(f"[RBI Scraper] 403 Forbidden: {url}")
                return None
            elif response.status_code == 429:
                wait = (attempt + 1) * 5
                print(f"[RBI Scraper] Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"[RBI Scraper] HTTP {response.status_code} attempt {attempt + 1}: {url}")
        except requests.exceptions.Timeout:
            print(f"[RBI Scraper] Timeout attempt {attempt + 1}: {url}")
        except requests.exceptions.ConnectionError:
            print(f"[RBI Scraper] Connection error attempt {attempt + 1}: {url}")
        except Exception as e:
            print(f"[RBI Scraper] Unexpected error: {e}")

        time.sleep(REQUEST_DELAY_SECONDS * (attempt + 1))

    return None


# ============================================================
# HELPER: PARSE RBI DATE
# Handles all date formats seen on RBI pages including
# dot-separated with non-zero-padded month: 08.6.2026
# ============================================================

def parse_rbi_date(date_str: str) -> Optional[date]:
    if not date_str:
        return None

    date_str = date_str.strip()

    # Handle dot-separated format: 08.6.2026 or 08.06.2026
    # strptime cannot handle single-digit months reliably on Windows
    if "." in date_str and date_str.count(".") == 2:
        try:
            parts = date_str.split(".")
            if len(parts) == 3:
                day   = int(parts[0])
                month = int(parts[1])
                year  = int(parts[2])
                if 1 <= month <= 12 and 1 <= day <= 31 and year > 2000:
                    return date(year, month, day)
        except (ValueError, IndexError):
            pass

    # Handle slash-separated: 08/06/2026
    if "/" in date_str and date_str.count("/") == 2:
        try:
            parts = date_str.split("/")
            return date(int(parts[2]), int(parts[1]), int(parts[0]))
        except (ValueError, IndexError):
            pass

    # Handle standard named-month formats
    named_formats = [
        "%B %d, %Y",   # January 15, 2026
        "%b %d, %Y",   # Jan 15, 2026
        "%d %B %Y",    # 15 January 2026
        "%d %b %Y",    # 15 Jan 2026
        "%Y-%m-%d",    # 2026-01-15
        "%d-%m-%Y",    # 15-01-2026
    ]

    for fmt in named_formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


# ============================================================
# HELPER: BUILD CORRECT RBI URL
# Fixes relative URLs — adds /Scripts/ prefix for .aspx pages
# ============================================================

def build_rbi_url(href: str) -> str:
    href = href.strip()

    if href.startswith("http"):
        return href

    # .aspx pages belong under /Scripts/
    if href.lower().endswith(".aspx") or ".aspx?" in href.lower():
        return SCRIPTS_BASE_URL + "/" + href.lstrip("/")

    # PDF documents belong under rbidocs subdomain
    if href.lower().endswith(".pdf"):
        if href.startswith("/"):
            return "https://rbidocs.rbi.org.in" + href
        return "https://rbidocs.rbi.org.in/rdocs/notification/PDFs/" + href

    # Default fallback
    return BASE_URL + "/" + href.lstrip("/")


# ============================================================
# METHOD 1: SCRAPE CIRCULAR INDEX PAGE (Primary)
#
# Confirmed RBI table column layout:
#   Col[0] → Department name
#   Col[1] → Date (DD.M.YYYY)
#   Col[2] → Circular reference number
#   Col[3] → Subject / Title (with link)
# ============================================================

def scrape_circular_index(max_circulars: int = 50) -> list[dict]:
    print("[RBI Scraper] Fetching circular index page...")
    response = safe_get(CIRCULAR_INDEX_URL)

    if not response:
        return []

    # Verify we got actual HTML
    sample = response.text[:100]
    if not ("<" in sample):
        print(f"[RBI Scraper] Response is not HTML: {repr(sample[:50])}")
        return []

    soup     = BeautifulSoup(response.text, "html.parser")
    circulars = []

    # Try named table identifiers first
    table = (
        soup.find("table", {"class": "tablebg"})
        or soup.find("table", {"class": "tabledata"})
        or soup.find("table", {"id": "gvCirculars"})
        or soup.find("table", {"id": "GridView1"})
    )

    # Fall back to largest table
    if not table:
        all_tables = soup.find_all("table")
        if all_tables:
            table = max(all_tables, key=lambda t: len(t.find_all("tr")))
            print(f"[RBI Scraper] Using largest table with {len(table.find_all('tr'))} rows.")

    if not table:
        print("[RBI Scraper] No table found in page.")
        return []

    rows = table.find_all("tr")
    print(f"[RBI Scraper] Processing {len(rows) - 1} data rows...")

    for row in rows[1:]:  # Skip header row
        cols = row.find_all("td")

        if len(cols) < 3:
            continue

        try:
            # Confirmed column layout from live RBI page:
            # Col[0] → Circular reference number (RBI/2026-2027/106...)
            # Col[1] → Date (DD.M.YYYY)
            # Col[2] → Department name
            # Col[3] → Subject / Title (with link)
            ref_number  = cols[0].get_text(strip=True)

            # Col[1] = Date in DD.M.YYYY format
            raw_date    = cols[1].get_text(strip=True)
            parsed_date = parse_rbi_date(raw_date)

            # Col[2] = Department name
            department  = cols[2].get_text(strip=True)

            # Col[3] = Subject with link (falls back to col[2] if no col[3])
            subject_col = cols[3] if len(cols) > 3 else cols[2]
            title       = subject_col.get_text(strip=True)

            # Use department name as fallback title if subject col is empty
            if not title:
                title = department

            # Extract link from subject column
            link_tag = subject_col.find("a") or row.find("a")
            doc_url  = ""
            doc_type = "HTML"

            if link_tag and link_tag.get("href"):
                doc_url  = build_rbi_url(link_tag["href"])
                doc_type = "PDF" if doc_url.lower().endswith(".pdf") else "HTML"

            if title and doc_url:
                circulars.append({
                    "title":      title,
                    "date":       parsed_date,
                    "url":        doc_url,
                    "ref_number": ref_number,
                    "department": department,
                    "doc_type":   doc_type,
                    "source": detect_source_from_url(doc_url),
                })

            if len(circulars) >= max_circulars:
                break

        except Exception as e:
            print(f"[RBI Scraper] Row parse error: {e}")
            continue

        time.sleep(0.1)

    print(f"[RBI Scraper] Extracted {len(circulars)} circulars from index page.")
    return circulars


# ============================================================
# METHOD 2: SCRAPE RSS FEEDS (Fallback)
# ============================================================

def scrape_rss_feeds(
    feed_keys: list[str] = None,
    max_per_feed: int = 20
) -> list[dict]:
    if feed_keys is None:
        feed_keys = list(RBI_RSS_FEEDS.keys())

    all_items = []
    seen_urls = set()

    for key in feed_keys:
        url = RBI_RSS_FEEDS.get(key)
        if not url:
            continue

        print(f"[RBI Scraper] Fetching RSS feed: {key}...")
        response = safe_get(url)

        if not response:
            continue

        try:
            raw = response.content

            # Strip BOM if present
            if raw.startswith(b'\xef\xbb\xbf'):
                raw = raw[3:]
            if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
                raw = raw[2:]

            # Verify it looks like XML
            preview = raw[:100].decode("utf-8", errors="ignore").strip()
            if not (preview.startswith("<?xml") or preview.startswith("<rss")):
                print(f"[RBI Scraper] Feed '{key}' not valid XML. Preview: {repr(preview[:80])}")
                continue

            root    = ET.fromstring(raw)
            channel = root.find("channel")

            if not channel:
                continue

            items = channel.findall("item")
            print(f"[RBI Scraper] {len(items)} items in feed: {key}")

            count = 0
            for item in items:
                if count >= max_per_feed:
                    break

                title_el   = item.find("title")
                link_el    = item.find("link")
                pubdate_el = item.find("pubDate")

                title    = title_el.text.strip()   if title_el   and title_el.text   else ""
                link     = link_el.text.strip()    if link_el    and link_el.text    else ""
                pub_date = pubdate_el.text.strip() if pubdate_el and pubdate_el.text else ""

                if link in seen_urls:
                    continue
                seen_urls.add(link)

                parsed_date = None
                if pub_date:
                    try:
                        parsed_date = datetime.strptime(
                            pub_date, "%a, %d %b %Y %H:%M:%S %z"
                        ).date()
                    except ValueError:
                        parsed_date = parse_rbi_date(pub_date)

                doc_type = "PDF" if link.lower().endswith(".pdf") else "HTML"

                if title:
                    all_items.append({
                        "title":         title,
                        "date":          parsed_date,
                        "url":           link,
                        "ref_number":    "",
                        "department":    "",
                        "doc_type":      doc_type,
                        "source":        "RBI",
                        "feed_category": key,
                    })
                    count += 1

        except ET.ParseError as e:
            print(f"[RBI Scraper] XML parse error for feed {key}: {e}")
        except Exception as e:
            print(f"[RBI Scraper] Error processing feed {key}: {e}")

        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"[RBI Scraper] Total items from RSS: {len(all_items)}")
    return all_items


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def fetch_rbi_circulars(max_circulars: int = 50) -> list[dict]:
    print("[RBI Scraper] Starting RBI circular fetch...")

    circulars = scrape_circular_index(max_circulars=max_circulars)

    if not circulars:
        print("[RBI Scraper] Falling back to RSS feeds...")
        circulars = scrape_rss_feeds(max_per_feed=max_circulars // 4)

    if not circulars:
        print("[RBI Scraper] Both sources returned no data.")
        return []

    print(f"[RBI Scraper] Done. {len(circulars)} circulars retrieved.")
    return circulars


# ============================================================
# STANDALONE TEST
# Run: python -m backend.scrapers.rbi_scraper
# ============================================================

if __name__ == "__main__":
    results = fetch_rbi_circulars(max_circulars=10)

    if results:
        print(f"\n--- Sample Results ({len(results)} items) ---")
        for i, item in enumerate(results[:5], 1):
            print(f"\n[{i}] Title      : {item['title']}")
            print(f"     Department : {item['department']}")
            print(f"     Date       : {item['date']}")
            print(f"     URL        : {item['url']}")
            print(f"     Type       : {item['doc_type']}")
            print(f"     Ref No.    : {item['ref_number']}")
    else:
        print("No results returned.")