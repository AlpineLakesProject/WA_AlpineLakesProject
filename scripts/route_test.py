import json
import csv
from pathlib import Path

TEST_LAKES = {
    "Colchuck",
    "Eightmile",
    "Rock (King County)",
    "Crystal",
    "Inspiration"
}

DATASET = Path("high_lakes_dataset.json")
OUTPUT = Path("reports/route_comparison.csv")

with open(DATASET, "r", encoding="utf-8") as f:
    lakes = json.load(f)

OUTPUT.parent.mkdir(exist_ok=True)

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)

    writer.writerow([
        "lake",
        "county",
        "latitude",
        "longitude",
        "current_trailhead",
        "current_distance",
        "current_gain",
        "routed_trailhead",
        "routed_distance",
        "routed_gain",
        "status"
    ])

    for lake in lakes:
        if lake["name"] in TEST_LAKES:

            writer.writerow([
                lake["name"],
                lake.get("county", ""),
                lake.get("latitude", ""),
                lake.get("longitude", ""),
                lake.get("trailhead_name", ""),
                lake.get("hiking_distance_miles", ""),
                lake.get("elevation_gain_ft", ""),
                "",
                "",
                "",
                "PENDING_ROUTE_TEST"
            ])

print(f"Created {OUTPUT}")
