#!/usr/bin/env python3
"""
scraper.py — WDFW High Lakes Scraper
Scrapes all lake pages from wdfw.wa.gov for King (59), Kittitas (42), and Chelan (132) counties.

Usage:
    python scraper.py                      # Full scrape, saves to data/raw_html/
    python scraper.py --dry-run            # Print URLs only, no download
    python scraper.py --pages-only         # Fetch list pages only (no detail pages)

Output:
    data/raw_html/list/page_<n>.html       # Paginated list pages
    data/raw_html/detail/<slug>.html       # Individual lake detail pages
    data/lake_urls.json                    # All discovered lake URLs
"""

import argparse
import json
import os
import re
import time
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ─── Config ───────────────────────────────────────────────────────
BASE_URL = "https://wdfw.wa.gov"
SEARCH_URL = (
    "https://wdfw.wa.gov/fishing/locations/high-lakes"
    "?name=&county%5B0%5D=59&county%5B1%5D=42&county%5B2%5D=132"
    "&species=&page={page}"
)

COUNTY_IDS = {
    "59": "King",
    "42": "Kittitas",
    "132": "Chelan",
}

RAW_DIR = Path("data/raw_html")
LIST_DIR = RAW_DIR / "list"
DETAIL_DIR = RAW_DIR / "detail"
URLS_FILE = Path("data/lake_urls.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

DELAY_BETWEEN_REQUESTS = 0.5   # seconds, be polite
MAX_PAGES = 50                  # safety cap


# ─── Helpers ─────────────────────────────────────────────────────
def slugify(url: str) -> str:
    """Convert a URL path to a safe filename."""
    slug = url.rstrip("/").split("/")[-1]
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", slug)
    return slug or "lake"


def fetch(url: str, retries: int = 3, delay: float = DELAY_BETWEEN_REQUESTS) -> str | None:
    """Fetch a URL with retries. Returns HTML text or None on failure."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            time.sleep(delay)
            return resp.text
        except requests.RequestException as e:
            wait = (attempt + 1) * 2
            print(f"  ✗ Attempt {attempt+1}/{retries} failed for {url}: {e}")
            if attempt < retries - 1:
                print(f"    Retrying in {wait}s…")
                time.sleep(wait)
    return None


# ─── List page scraping ───────────────────────────────────────────
def parse_lake_urls_from_list(html: str) -> list[str]:
    """Extract lake detail URLs from a search-results page."""
    soup = BeautifulSoup(html, "lxml")
    urls = []
    table = soup.find("table")
    if not table:
        return urls
    for a in table.find_all("a", href=True):
        href = a["href"]
        if "/high-lakes/" in href and "high-lakes?name" not in href:
            full = BASE_URL + href if href.startswith("/") else href
            if full not in urls:
                urls.append(full)
    return urls


def has_results(html: str) -> bool:
    """Return True if the page contains any lake results."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return False
    tbody = table.find("tbody")
    return bool(tbody and tbody.find("tr"))


def scrape_list_pages(save: bool = True) -> list[str]:
    """
    Enumerate all search result pages and collect lake detail URLs.
    Returns deduplicated list of lake URLs.
    """
    print("=" * 60)
    print("Step 1 — Enumerating lake list pages")
    print("=" * 60)

    if save:
        LIST_DIR.mkdir(parents=True, exist_ok=True)

    all_urls: list[str] = []

    for page in range(MAX_PAGES):
        url = SEARCH_URL.format(page=page)
        print(f"  Page {page}: {url}")

        html = fetch(url)
        if html is None:
            print(f"  ✗ Failed to fetch page {page}. Stopping.")
            break

        if not has_results(html):
            print(f"  ✓ No more results at page {page}. Done.")
            break

        if save:
            (LIST_DIR / f"page_{page:03d}.html").write_text(html, encoding="utf-8")

        urls = parse_lake_urls_from_list(html)
        print(f"    Found {len(urls)} lake URLs")
        all_urls.extend(urls)

    # Deduplicate preserving order
    seen = set()
    deduped = []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    print(f"\n  Total unique lake URLs: {len(deduped)}")
    return deduped


# ─── Detail page scraping ─────────────────────────────────────────
def scrape_detail_pages(urls: list[str], save: bool = True) -> dict[str, str]:
    """
    Visit each lake detail URL and optionally save HTML.
    Returns dict of {url: html}.
    """
    print("\n" + "=" * 60)
    print("Step 2 — Fetching lake detail pages")
    print("=" * 60)

    if save:
        DETAIL_DIR.mkdir(parents=True, exist_ok=True)

    html_map: dict[str, str] = {}
    total = len(urls)

    for i, url in enumerate(urls):
        slug = slugify(url)
        out_path = DETAIL_DIR / f"{slug}.html"

        # Skip if already downloaded
        if save and out_path.exists():
            print(f"  [{i+1:3d}/{total}] ↩ Cached  {slug}")
            html_map[url] = out_path.read_text(encoding="utf-8")
            continue

        print(f"  [{i+1:3d}/{total}] ↓ Fetching {url}")
        html = fetch(url)

        if html is None:
            print(f"    ✗ Failed to fetch {url}")
            html_map[url] = ""
            continue

        if save:
            out_path.write_text(html, encoding="utf-8")
        html_map[url] = html

    successful = sum(1 for v in html_map.values() if v)
    print(f"\n  Successfully fetched: {successful}/{total}")
    return html_map


# ─── Main ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="WDFW High Lakes scraper")
    parser.add_argument("--dry-run", action="store_true", help="Print URLs only, no download")
    parser.add_argument("--pages-only", action="store_true", help="Fetch list pages only")
    args = parser.parse_args()

    Path("data").mkdir(exist_ok=True)

    if args.dry_run:
        urls = scrape_list_pages(save=False)
        print("\nDry run — discovered URLs:")
        for u in urls:
            print(f"  {u}")
        return

    # Step 1: Collect URLs
    urls = scrape_list_pages(save=True)

    # Save URL list
    URLS_FILE.write_text(json.dumps(urls, indent=2), encoding="utf-8")
    print(f"\n  URL list saved → {URLS_FILE}")

    if args.pages_only:
        print("\nStopping after list pages (--pages-only).")
        return

    # Step 2: Fetch detail pages
    html_map = scrape_detail_pages(urls, save=True)

    print("\n✓ Scraping complete.")
    print(f"  Raw HTML → {RAW_DIR}/")
    print(f"  URL list → {URLS_FILE}")
    print("\nNext step: python parser.py")


if __name__ == "__main__":
    main()
