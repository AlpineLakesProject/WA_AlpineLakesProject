#!/usr/bin/env python3
"""
parser.py — WDFW High Lakes HTML Parser
Parses raw HTML downloaded by scraper.py and extracts structured lake records.

Usage:
    python parser.py                       # Parse all saved HTML, produce parsed_lakes.json
    python parser.py --input data/raw_html/detail  # Custom input dir
    python parser.py --test                # Parse first 5 lakes and print results

Output:
    data/parsed_lakes.json    # List of raw extracted records (before dataset generation)
"""

import argparse
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

# ─── Config ───────────────────────────────────────────────────────
DETAIL_DIR = Path("data/raw_html/detail")
URLS_FILE   = Path("data/lake_urls.json")
OUTPUT_FILE = Path("data/parsed_lakes.json")

UNKNOWN = "unknown"

SPECIES_KEYWORDS = [
    "Rainbow trout", "Cutthroat trout", "Brook trout",
    "Brown trout", "Golden trout", "Lake trout",
    "Kokanee", "Largemouth bass", "Smallmouth bass",
    "Yellow perch", "Tiger trout", "Bull trout",
]


# ─── Field extractors ────────────────────────────────────────────
def safe_text(tag) -> str:
    """Return stripped text of a BeautifulSoup tag, or UNKNOWN."""
    if tag is None:
        return UNKNOWN
    txt = tag.get_text(separator=" ", strip=True)
    return txt if txt else UNKNOWN


def extract_field(soup: BeautifulSoup, label_text: str) -> str:
    """
    Find a field by its label text in the page.
    WDFW detail pages often use <dt>/<dd> or labeled <div> pairs.
    """
    # Try definition list pattern
    for dt in soup.find_all(["dt", "th", "strong", "label", "span"]):
        if label_text.lower() in dt.get_text().lower():
            # Look for adjacent dd / next sibling with content
            for sibling in [dt.find_next_sibling(), dt.find_next("dd"), dt.find_next("td")]:
                if sibling:
                    txt = sibling.get_text(separator=" ", strip=True)
                    if txt:
                        return txt
    return UNKNOWN


def extract_coordinates(soup: BeautifulSoup) -> tuple[float, float]:
    """Extract lat/lon from the page. Returns (lat, lon) or (0, 0)."""
    # Pattern 1: Google Maps link
    for a in soup.find_all("a", href=re.compile(r"maps\.google|google\.com/maps")):
        m = re.search(r"q=([\-\d.]+),([\-\d.]+)", a.get("href", ""))
        if m:
            return float(m.group(1)), float(m.group(2))

    # Pattern 2: Leaflet / data attributes
    for el in soup.find_all(True, {"data-lat": True, "data-lon": True}):
        try:
            return float(el["data-lat"]), float(el["data-lon"])
        except (ValueError, KeyError):
            pass

    # Pattern 3: Inline coordinate spans
    for span in soup.find_all("span"):
        txt = span.get_text(strip=True)
        m = re.search(r"(4[5-9]\.\d{4,}),\s*([-]12[0-2]\.\d{4,})", txt)
        if m:
            return float(m.group(1)), float(m.group(2))

    # Pattern 4: Anywhere in page text
    page_text = soup.get_text()
    m = re.search(r"(4[5-9]\.\d{5,})[,\s]+([-]12[0-2]\.\d{5,})", page_text)
    if m:
        return float(m.group(1)), float(m.group(2))

    return 0.0, 0.0


def extract_number(text: str) -> str:
    """Extract first numeric value (int or float) from a string."""
    if not text or text == UNKNOWN:
        return UNKNOWN
    text_clean = text.replace(",", "")
    m = re.search(r"[\d]+(?:\.\d+)?", text_clean)
    return m.group() if m else UNKNOWN


def extract_species(soup: BeautifulSoup, full_text: str) -> list[str]:
    """Extract fish species from page content."""
    found = []
    for sp in SPECIES_KEYWORDS:
        if sp.lower() in full_text.lower():
            found.append(sp)
    return found if found else [UNKNOWN]


def extract_stocking(soup: BeautifulSoup) -> list[dict]:
    """Extract stocking history table if present."""
    records = []
    for table in soup.find_all("table"):
        headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if not any(h in headers for h in ["year", "species", "number", "stocked"]):
            continue
        for tr in table.find_all("tr")[1:]:  # skip header row
            cells = [td.get_text(strip=True) for td in tr.find_all("td")]
            if len(cells) >= 2:
                rec = {}
                for i, h in enumerate(headers[:len(cells)]):
                    rec[h] = cells[i]
                records.append(rec)
    return records


# ─── Main parser ──────────────────────────────────────────────────
def parse_lake_html(html: str, source_url: str) -> dict:
    """Parse a single lake detail HTML page into a structured record."""
    soup = BeautifulSoup(html, "lxml")
    full_text = soup.get_text()

    # Lake name — usually in <h1> or page title
    name = UNKNOWN
    for tag in ["h1", "h2"]:
        el = soup.find(tag)
        if el:
            txt = el.get_text(strip=True)
            if txt and "high lake" not in txt.lower():
                name = txt
                break
    if name == UNKNOWN:
        title = soup.find("title")
        if title:
            name = title.get_text(strip=True).split("|")[0].strip()

    # County
    county = extract_field(soup, "county")
    if county == UNKNOWN:
        for kw in ["King", "Kittitas", "Chelan"]:
            if kw.lower() in full_text.lower():
                county = kw
                break

    # Coordinates
    lat, lon = extract_coordinates(soup)

    # Acres
    acres_text = extract_field(soup, "acres") or extract_field(soup, "size") or extract_field(soup, "area")
    acres = extract_number(acres_text)

    # Elevation
    elev_text = extract_field(soup, "elevation")
    elevation = extract_number(elev_text)

    # Species
    species = extract_species(soup, full_text)

    # Stocking history
    stocking = extract_stocking(soup)

    # Access & trailhead
    access = extract_field(soup, "access") or extract_field(soup, "directions")
    trailhead = extract_field(soup, "trailhead")
    hike_dist = extract_field(soup, "distance") or extract_field(soup, "miles")
    elev_gain = extract_field(soup, "elevation gain") or extract_field(soup, "gain")

    # Camping
    camping = extract_field(soup, "camping")

    # Wilderness
    wilderness = extract_field(soup, "wilderness")

    # Notes — look for a general description block
    notes = UNKNOWN
    for tag in soup.find_all(["p", "div"], class_=re.compile(r"desc|content|body|notes", re.I)):
        txt = tag.get_text(separator=" ", strip=True)
        if len(txt) > 60:
            notes = txt[:500]  # cap at 500 chars
            break

    return {
        "name": name,
        "county": county,
        "latitude": lat,
        "longitude": lon,
        "acres": float(acres) if acres != UNKNOWN else 0,
        "elevation_ft": int(elevation) if elevation != UNKNOWN else 0,
        "species": [s for s in species if s != UNKNOWN],
        "trailhead_name": trailhead,
        "hiking_distance_miles": hike_dist,
        "elevation_gain_ft": elev_gain,
        "camping": camping,
        "access_description": access,
        "wilderness_area": wilderness,
        "stocking_history": stocking,
        "notes": notes,
        "source_url": source_url,
    }


# ─── Batch parsing ────────────────────────────────────────────────
def parse_all(detail_dir: Path, urls_file: Path) -> list[dict]:
    """Parse all HTML files in the detail directory."""
    html_files = sorted(detail_dir.glob("*.html"))
    print(f"  Found {len(html_files)} HTML files in {detail_dir}")

    # Build slug → URL map if available
    url_map = {}
    if urls_file.exists():
        urls = json.loads(urls_file.read_text())
        for u in urls:
            slug = u.rstrip("/").split("/")[-1]
            slug = re.sub(r"[^a-zA-Z0-9_-]", "_", slug)
            url_map[slug] = u

    records = []
    for i, path in enumerate(html_files):
        slug = path.stem
        source_url = url_map.get(slug, f"https://wdfw.wa.gov/fishing/locations/high-lakes/{slug}")
        html = path.read_text(encoding="utf-8")
        record = parse_lake_html(html, source_url)
        records.append(record)
        if (i + 1) % 50 == 0:
            print(f"    Parsed {i+1}/{len(html_files)}…")

    return records


# ─── Main ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="WDFW High Lakes HTML parser")
    parser.add_argument("--input", type=Path, default=DETAIL_DIR, help="Detail HTML directory")
    parser.add_argument("--test", action="store_true", help="Parse first 5 files and print")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} does not exist. Run scraper.py first.", file=sys.stderr)
        sys.exit(1)

    print("=" * 60)
    print("WDFW High Lakes Parser")
    print("=" * 60)

    records = parse_all(args.input, URLS_FILE)

    if args.test:
        for r in records[:5]:
            print(json.dumps(r, indent=2))
        return

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"\n✓ Parsed {len(records)} lakes → {OUTPUT_FILE}")
    print("\nNext step: python generate_dataset.py")


if __name__ == "__main__":
    main()
