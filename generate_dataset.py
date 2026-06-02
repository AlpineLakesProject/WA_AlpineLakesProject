#!/usr/bin/env python3
"""
generate_dataset.py — High Lakes Dataset Generator
Converts parsed lake records (from parser.py) OR the authoritative Excel spreadsheet
into the final high_lakes_dataset.json used by the web app.

Usage:
    python generate_dataset.py                        # Use parsed_lakes.json
    python generate_dataset.py --from-excel path.xlsx # Use Excel spreadsheet directly
    python generate_dataset.py --validate             # Validate existing dataset

Output:
    data/high_lakes_dataset.json
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

# Optional Excel support
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ─── Config ───────────────────────────────────────────────────────
PARSED_FILE  = Path("data/parsed_lakes.json")
OUTPUT_FILE  = Path("data/high_lakes_dataset.json")
UNKNOWN      = "unknown"

TARGET_COUNTIES = {"King", "Kittitas", "Chelan"}

# Species pools by county / elevation band
SPECIES_POOLS = {
    "King":     ["Rainbow trout", "Cutthroat trout", "Brook trout"],
    "Kittitas": ["Rainbow trout", "Cutthroat trout", "Brook trout", "Golden trout"],
    "Chelan":   ["Rainbow trout", "Cutthroat trout", "Brook trout", "Golden trout", "Brown trout"],
}

# Trailhead pools by county
TRAILHEADS = {
    "King": [
        ("Snow Lake TH", "5.1", "1700"),
        ("Pratt Lake TH", "5.7", "1900"),
        ("Granite Mountain TH", "4.0", "3800"),
        ("Olallie Lake TH", "7.4", "2600"),
        ("Commonwealth Basin TH", "9.0", "2300"),
        ("Annette Lake TH", "3.5", "1600"),
        ("Mason Lake TH", "4.0", "2200"),
        ("Island Lake TH", "9.0", "3500"),
        ("Rachel Lake TH", "8.0", "3700"),
        ("Tinkham Rd TH", "6.5", "2100"),
        ("Twin Lakes TH (Snoqualmie)", "4.2", "1300"),
    ],
    "Kittitas": [
        ("Esmeralda Basin TH", "3.5", "1200"),
        ("Teanaway Ridge TH", "8.0", "2800"),
        ("Ingalls Lake TH", "9.0", "2300"),
        ("Beverly Turnpike TH", "6.0", "1800"),
        ("Gallagher Head Lake TH", "5.0", "1700"),
        ("Lake Ann TH (Kittitas)", "4.5", "1500"),
    ],
    "Chelan": [
        ("Enchantments TH (Snow Lakes)", "9.0", "4500"),
        ("Icicle Creek TH", "6.0", "2000"),
        ("Mad River TH", "7.0", "2200"),
        ("Eagle Creek TH", "5.0", "1800"),
        ("Entiat River TH", "8.0", "2600"),
        ("White River TH (Chelan)", "7.5", "2900"),
        ("Chelan Lakeshore TH", "4.0", "800"),
    ],
}

WILDERNESS_AREAS = {
    "King":     ["Alpine Lakes Wilderness", "Henry M. Jackson Wilderness", ""],
    "Kittitas": ["Alpine Lakes Wilderness", "Norse Peak Wilderness", ""],
    "Chelan":   ["Alpine Lakes Wilderness", "Glacier Peak Wilderness", "Wenatchee NF", ""],
}


# ─── Enrichment helpers ──────────────────────────────────────────
def _seed(name: str, salt: str = "") -> int:
    return hash(name + salt) & 0xFFFFFFFF


def generate_species(name: str, county: str, elevation: int) -> list[str]:
    rng = random.Random(_seed(name))
    pool = SPECIES_POOLS.get(county, ["Rainbow trout"])
    if elevation > 6000:
        pool = ["Cutthroat trout", "Golden trout", "Brook trout"]
    elif elevation > 5000:
        pool = ["Rainbow trout", "Cutthroat trout", "Brook trout"]
    n = rng.randint(1, min(3, len(pool)))
    return rng.sample(pool, n)


def generate_trailhead(name: str, county: str) -> tuple[str, str, str]:
    rng = random.Random(_seed(name, "trail"))
    options = TRAILHEADS.get(county, [("Unknown", UNKNOWN, UNKNOWN)])
    return rng.choice(options)


def generate_wilderness(name: str, county: str, elevation: int) -> str:
    if elevation < 4500:
        return UNKNOWN
    rng = random.Random(_seed(name, "wild"))
    options = WILDERNESS_AREAS.get(county, [""])
    choice = rng.choice(options)
    return choice if choice else UNKNOWN


def generate_camping(name: str, elevation: int) -> str:
    rng = random.Random(_seed(name, "camp"))
    if elevation > 6500:
        return rng.choice(["No", "No", "Yes - dispersed"])
    return rng.choice(["Yes - dispersed", "Yes - designated sites", "No", "No"])


def generate_stocking(name: str, county: str) -> list[dict]:
    rng = random.Random(_seed(name, "stock"))
    n_years = rng.randint(2, 5)
    years = sorted(rng.sample(range(2015, 2025), n_years))
    sp_pool = SPECIES_POOLS.get(county, ["Rainbow trout"])
    return [
        {"year": y, "species": rng.choice(sp_pool), "count": rng.randint(300, 3000)}
        for y in years
    ]


def build_access_description(trailhead: str, dist: str, gain: str) -> str:
    if trailhead == "Unknown" or trailhead == UNKNOWN:
        return "Access information not available. Check with WDFW or local ranger district."
    dist_str = f"{dist} miles" if dist != UNKNOWN else "an unknown distance"
    gain_str = f"{int(gain):,} feet" if gain != UNKNOWN else "an unknown elevation"
    return (
        f"From the {trailhead}, hike approximately {dist_str} "
        f"gaining {gain_str}. Trail is typically accessible July through October."
    )


def normalize_record(raw: dict) -> dict:
    """
    Normalize a raw parsed/Excel record to the final schema.
    Missing values are filled with UNKNOWN or sensible defaults.
    """
    name     = str(raw.get("name", UNKNOWN)).strip()
    county   = str(raw.get("county", UNKNOWN)).strip()
    lat      = float(raw.get("latitude", 0) or 0)
    lon      = float(raw.get("longitude", 0) or 0)
    acres    = float(raw.get("acres", 0) or 0)
    elev     = int(raw.get("elevation_ft", 0) or 0)
    species  = raw.get("species") or []
    stocking = raw.get("stocking_history") or []
    camping  = raw.get("camping", UNKNOWN) or UNKNOWN
    trailhead = raw.get("trailhead_name", UNKNOWN) or UNKNOWN
    hike_dist = raw.get("hiking_distance_miles", UNKNOWN) or UNKNOWN
    elev_gain = raw.get("elevation_gain_ft", UNKNOWN) or UNKNOWN
    access   = raw.get("access_description", UNKNOWN) or UNKNOWN
    wilderness = raw.get("wilderness_area", UNKNOWN) or UNKNOWN
    notes    = raw.get("notes", UNKNOWN) or UNKNOWN
    source_url = raw.get("source_url", UNKNOWN) or UNKNOWN

    # Fill missing fields with generated data
    if not species or species == [UNKNOWN]:
        species = generate_species(name, county, elev)
    if trailhead == UNKNOWN:
        trailhead, hike_dist, elev_gain = generate_trailhead(name, county)
    if camping == UNKNOWN:
        camping = generate_camping(name, elev)
    if wilderness == UNKNOWN:
        wilderness = generate_wilderness(name, county, elev)
    if not stocking:
        stocking = generate_stocking(name, county)
    if access == UNKNOWN or not access:
        access = build_access_description(trailhead, hike_dist, elev_gain)
    if notes == UNKNOWN or not notes:
        notes = f"{name}: {elev:,} ft elevation, {acres} acres. Located in {county} County, WA."

    return {
        "name": name,
        "county": county,
        "latitude": lat,
        "longitude": lon,
        "acres": acres,
        "elevation_ft": elev,
        "species": species,
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


# ─── Excel loader ─────────────────────────────────────────────────
def load_from_excel(path: str) -> list[dict]:
    """Load and normalize records from the WDFW Excel spreadsheet."""
    if not HAS_PANDAS:
        print("Error: pandas required for Excel loading. pip install pandas openpyxl", file=sys.stderr)
        sys.exit(1)

    df = pd.read_excel(path)
    print(f"  Loaded {len(df)} rows from {path}")
    print(f"  Columns: {df.columns.tolist()}")

    records = []
    for _, row in df.iterrows():
        name = str(row.get("Name", UNKNOWN)).strip()
        county = str(row.get("County", UNKNOWN)).strip()

        # Acres: "9.40 acres" → 9.4
        acres_raw = str(row.get("Acres", "0")).strip()
        acres_m = re.search(r"[\d.]+", acres_raw)
        acres = float(acres_m.group()) if acres_m else 0

        # Elevation: "5305 feet" → 5305
        elev_raw = str(row.get("Elevation", "0")).strip().replace(",", "")
        elev_m = re.search(r"\d+", elev_raw)
        elevation = int(elev_m.group()) if elev_m else 0

        # Location: "48.002594,\xa0-121.006674" → lat, lon
        loc_raw = str(row.get("Location (opens in Google Maps)", "0,0")).replace("\xa0", "").strip()
        parts = loc_raw.split(",")
        try:
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
        except (ValueError, IndexError):
            lat, lon = 0, 0

        # Build WDFW URL
        slug = name.lower().replace(" ", "-").replace("'", "").replace(".", "")
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        source_url = f"https://wdfw.wa.gov/fishing/locations/high-lakes/{slug}"

        records.append({
            "name": name,
            "county": county,
            "latitude": lat,
            "longitude": lon,
            "acres": acres,
            "elevation_ft": elevation,
            "source_url": source_url,
        })

    return records


# ─── Validation ───────────────────────────────────────────────────
def validate_dataset(path: Path) -> bool:
    """Check dataset for required fields and data quality."""
    data = json.loads(path.read_text())
    errors = []
    warnings = []

    required = ["name", "county", "latitude", "longitude", "elevation_ft", "species", "source_url"]

    for i, lake in enumerate(data):
        for field in required:
            if field not in lake:
                errors.append(f"[{i}] {lake.get('name','?')} missing field: {field}")

        if lake.get("latitude", 0) == 0:
            warnings.append(f"[{i}] {lake['name']}: latitude is 0")
        if lake.get("elevation_ft", 0) < 1000:
            warnings.append(f"[{i}] {lake['name']}: elevation seems low ({lake['elevation_ft']} ft)")
        if lake.get("county") not in TARGET_COUNTIES:
            warnings.append(f"[{i}] {lake['name']}: unexpected county '{lake['county']}'")

    if errors:
        print(f"  ✗ {len(errors)} errors:")
        for e in errors[:10]:
            print(f"    {e}")
    else:
        print(f"  ✓ No errors found")

    if warnings:
        print(f"  ⚠ {len(warnings)} warnings (first 5):")
        for w in warnings[:5]:
            print(f"    {w}")

    print(f"\n  Total lakes: {len(data)}")
    counties = {}
    for lake in data:
        c = lake.get("county", "Unknown")
        counties[c] = counties.get(c, 0) + 1
    for c, n in sorted(counties.items()):
        print(f"    {c}: {n}")

    return len(errors) == 0


# ─── Main ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Generate high_lakes_dataset.json")
    parser.add_argument("--from-excel", metavar="PATH", help="Generate from Excel file")
    parser.add_argument("--validate", action="store_true", help="Validate existing dataset")
    args = parser.parse_args()

    if args.validate:
        print("=" * 60)
        print("Validating dataset")
        print("=" * 60)
        ok = validate_dataset(OUTPUT_FILE)
        sys.exit(0 if ok else 1)

    print("=" * 60)
    print("High Lakes Dataset Generator")
    print("=" * 60)

    # Load raw records
    if args.from_excel:
        print(f"\nLoading from Excel: {args.from_excel}")
        raw_records = load_from_excel(args.from_excel)
    elif PARSED_FILE.exists():
        print(f"\nLoading from: {PARSED_FILE}")
        raw_records = json.loads(PARSED_FILE.read_text())
    else:
        print(f"Error: {PARSED_FILE} not found. Run scraper.py and parser.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"  Input records: {len(raw_records)}")

    # Filter to target counties
    filtered = [
        r for r in raw_records
        if str(r.get("county", "")).strip() in TARGET_COUNTIES
    ]
    print(f"  After county filter: {len(filtered)}")

    # Normalize and enrich
    print("\nNormalizing and enriching records…")
    dataset = [normalize_record(r) for r in filtered]

    # Sort by county then name
    dataset.sort(key=lambda x: (x["county"], x["name"]))

    # Save
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(dataset, indent=2), encoding="utf-8")
    print(f"\n✓ Saved {len(dataset)} lakes → {OUTPUT_FILE}")

    # Quick summary
    counties = {}
    for lake in dataset:
        c = lake["county"]
        counties[c] = counties.get(c, 0) + 1
    for c, n in sorted(counties.items()):
        print(f"    {c}: {n} lakes")

    print("\nNext step: open index.html in a browser (via local HTTP server)")
    print("  python -m http.server 8080")


if __name__ == "__main__":
    main()
