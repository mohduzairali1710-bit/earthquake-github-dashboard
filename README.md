# Live Data Pipeline & Interactive Dashboard

A beginner-friendly Python script that fetches recent significant earthquakes
from the USGS and popular Python repositories from GitHub, then combines the
results in an interactive Plotly dashboard.

## What it does

- Fetches M4.5+ earthquakes from the USGS GeoJSON feed for the past seven days.
- Fetches the ten most-starred repositories tagged as Python from GitHub.
- Cleans the API responses into Pandas DataFrames and reports incomplete entries.
- Builds a world map with magnitude-scaled, magnitude-colored earthquake markers.
- Builds a horizontal repository star chart with descriptions and clickable links.
- Saves both charts together in `dashboard.html`.

## Requirements

- Python 3.10 or newer
- Internet access to reach the USGS and GitHub APIs

## Setup

Open a terminal in this project folder and create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the packages:

```powershell
python -m pip install -r requirements.txt
```

## Run

```powershell
python data_pipeline.py
```

Open `dashboard.html` in a web browser to explore the charts. The GitHub API
is used without authentication, so its public rate limit applies.
