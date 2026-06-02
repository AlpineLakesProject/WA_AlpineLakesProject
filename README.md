# High Lakes Explorer 🏔️

Interactive web map for all **421 Washington WDFW High Lakes** in King, Kittitas, and Chelan Counties.

Built from the [WDFW High Lakes Database](https://wdfw.wa.gov/fishing/locations/high-lakes).

---

## Live Demo

[https://your-username.github.io/high-lakes-explorer](https://your-username.github.io/high-lakes-explorer)

---

## Features

- **421 lakes** plotted on a USGS topo base map
- **Color-coded markers** by elevation (4 bands from teal → deep blue)
- **Marker size** scales with lake acreage
- **Rich popups** with: elevation, acres, species, camping, trailhead, stocking history, access description
- **Filters**: County · Species · Camping · Hiking Distance · Elevation Gain · Min Lake Elevation
- **Search** by lake name (real-time)
- **Scrollable lake list** synced to map — click any entry to fly to the lake
- Mobile-responsive with sidebar toggle

---

## Project Structure

```
high-lakes-explorer/
├── index.html               # App shell
├── styles.css               # Pacific Northwest aesthetic theme
├── app.js                   # Leaflet map + filters + list
├── data/
│   └── high_lakes_dataset.json   # 421 lakes, authoritative dataset
├── scraper.py               # WDFW website scraper
├── parser.py                # HTML → structured fields extractor
├── generate_dataset.py      # Normalizes + enriches → final JSON
└── README.md
```

---

## Dataset Schema

Each lake record in `data/high_lakes_dataset.json`:

```json
{
  "name": "Snow Lake",
  "county": "King",
  "latitude": 47.4456,
  "longitude": -121.4398,
  "acres": 82.0,
  "elevation_ft": 4016,
  "species": ["Rainbow trout", "Cutthroat trout"],
  "trailhead_name": "Snow Lake TH",
  "hiking_distance_miles": "5.1",
  "elevation_gain_ft": "1700",
  "camping": "Yes - dispersed",
  "access_description": "From the Snow Lake TH, hike approximately 5.1 miles...",
  "wilderness_area": "Alpine Lakes Wilderness",
  "stocking_history": [
    {"year": 2021, "species": "Rainbow trout", "count": 1500}
  ],
  "notes": "Snow Lake: 4016 ft elevation, 82.0 acres. Located in King County, WA.",
  "source_url": "https://wdfw.wa.gov/fishing/locations/high-lakes/snow-lake"
}
```

---

## Running Locally

```bash
# Serve the app (required for JSON fetch)
python -m http.server 8080
# Open http://localhost:8080
```

---

## Re-Scraping / Updating Data

### Step 1 — Scrape WDFW

```bash
pip install requests beautifulsoup4 lxml
python scraper.py
```

This saves raw HTML to `data/raw_html/`.

### Step 2 — Parse HTML

```bash
python parser.py
```

Produces `data/parsed_lakes.json` with extracted fields.

### Step 3 — Generate Dataset

```bash
pip install pandas openpyxl
python generate_dataset.py
# or directly from the authoritative Excel:
python generate_dataset.py --from-excel High_Lakes_Dataset_.xlsx
```

Validates and saves `data/high_lakes_dataset.json`.

---

## GitHub Pages Deployment

### Option A — GitHub Actions (recommended, auto-deploys on push)

1. Push this folder to a GitHub repo.

2. In your repo → **Settings** → **Pages** → Source: `GitHub Actions`.

3. Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GitHub Pages
on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v4
      - uses: actions/upload-pages-artifact@v3
        with:
          path: '.'
      - id: deployment
        uses: actions/deploy-pages@v4
```

4. Push → the site deploys automatically. ✅

### Option B — Manual gh-pages branch

```bash
# Install gh-pages tool
npm install -g gh-pages

# Deploy (run from project root)
gh-pages -d .
```

Your site is live at `https://<username>.github.io/<repo-name>`.

---

## Data Sources

- **Primary**: WDFW High Lakes Database — https://wdfw.wa.gov/fishing/locations/high-lakes
- **Coordinates & attributes**: Authoritative Excel inventory (421 lakes, King/Kittitas/Chelan Counties)
- **Base map**: USGS National Hydrography + CartoDB labels

---

## License

Data © Washington Department of Fish & Wildlife. Web application MIT licensed.
