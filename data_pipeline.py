"""Fetch live earthquake and GitHub repository data, then build a dashboard."""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import requests


logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
GITHUB_URL = "https://api.github.com/search/repositories"
REQUEST_TIMEOUT_SECONDS = 20
OUTPUT_FILE = Path("dashboard.html")

EARTHQUAKE_COLUMNS = [
    "place",
    "magnitude",
    "time",
    "latitude",
    "longitude",
    "depth",
    "url",
]
REPOSITORY_COLUMNS = ["name", "stars", "description", "url"]


def get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Request JSON from an API and report network or response errors."""
    headers = {"User-Agent": "Live-Data-Pipeline-Dashboard"}
    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as error:
        logging.error("Request to %s failed: %s", url, error)
        return None
    except ValueError as error:
        logging.error("The response from %s was not valid JSON: %s", url, error)
        return None

    if not isinstance(data, dict):
        logging.error("The response from %s did not contain a JSON object.", url)
        return None
    return data


def fetch_earthquakes() -> pd.DataFrame:
    """Fetch M4.5+ earthquakes from the USGS past-week GeoJSON feed."""
    data = get_json(USGS_URL)
    if data is None:
        return pd.DataFrame(columns=EARTHQUAKE_COLUMNS)

    features = data.get("features")
    if not isinstance(features, list):
        logging.error("The USGS response is missing its features list.")
        return pd.DataFrame(columns=EARTHQUAKE_COLUMNS)

    rows: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, dict):
            logging.warning("Skipping an earthquake entry that is not an object.")
            continue

        properties = feature.get("properties")
        geometry = feature.get("geometry")
        coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
        if not isinstance(properties, dict) or not isinstance(coordinates, list) or len(coordinates) < 3:
            logging.warning("Skipping an earthquake entry with missing properties or coordinates.")
            continue

        try:
            longitude, latitude, depth = coordinates[:3]
            magnitude = properties.get("mag")
            timestamp = properties.get("time")
            if magnitude is None or timestamp is None:
                raise ValueError("magnitude or time is missing")

            rows.append(
                {
                    "place": properties.get("place") or "Unknown location",
                    "magnitude": float(magnitude),
                    "time": pd.to_datetime(timestamp, unit="ms", utc=True, errors="raise"),
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "depth": float(depth),
                    "url": properties.get("url") or "",
                }
            )
        except (TypeError, ValueError, OverflowError) as error:
            logging.warning("Skipping an earthquake entry with invalid data: %s", error)

    if not rows:
        logging.warning("The USGS feed did not contain any usable earthquake entries.")
    return pd.DataFrame(rows, columns=EARTHQUAKE_COLUMNS)


def fetch_top_repositories() -> pd.DataFrame:
    """Fetch the ten most-starred Python repositories from GitHub."""
    data = get_json(
        GITHUB_URL,
        params={
            "q": "language:python",
            "sort": "stars",
            "order": "desc",
            "per_page": 10,
        },
    )
    if data is None:
        return pd.DataFrame(columns=REPOSITORY_COLUMNS)

    repositories = data.get("items")
    if not isinstance(repositories, list):
        logging.error("The GitHub response is missing its items list.")
        return pd.DataFrame(columns=REPOSITORY_COLUMNS)

    rows: list[dict[str, Any]] = []
    for repository in repositories:
        if not isinstance(repository, dict):
            logging.warning("Skipping a repository entry that is not an object.")
            continue
        name = repository.get("full_name")
        stars = repository.get("stargazers_count")
        if not name or stars is None:
            logging.warning("Skipping a repository entry missing its name or star count.")
            continue
        try:
            rows.append(
                {
                    "name": str(name),
                    "stars": int(stars),
                    "description": repository.get("description") or "No description provided.",
                    "url": repository.get("html_url") or "",
                }
            )
        except (TypeError, ValueError) as error:
            logging.warning("Skipping a repository entry with invalid data: %s", error)

    if not rows:
        logging.warning("GitHub did not return any usable repositories.")
    return pd.DataFrame(rows, columns=REPOSITORY_COLUMNS)


def make_earthquake_map(earthquakes: pd.DataFrame) -> go.Figure:
    """Create an interactive map with earthquake magnitude and event details."""
    if earthquakes.empty:
        figure = go.Figure()
        figure.add_annotation(text="No earthquake data is available.", showarrow=False)
        figure.update_layout(title="M4.5+ Earthquakes — Past 7 Days")
        return figure

    figure = px.scatter_geo(
        earthquakes,
        lat="latitude",
        lon="longitude",
        size="magnitude",
        color="magnitude",
        color_continuous_scale="YlOrRd",
        size_max=18,
        custom_data=["url"],
        hover_name="place",
        hover_data={
            "magnitude": ":.1f",
            "time": True,
            "latitude": ":.3f",
            "longitude": ":.3f",
            "depth": ":.1f",
            "url": False,
        },
        title="M4.5+ Earthquakes — Past 7 Days",
        projection="natural earth",
    )
    figure.update_traces(
        hovertemplate=(
            "<b>%{hovertext}</b><br>"
            "Magnitude: %{customdata[1]:.1f}<br>"
            "Time: %{customdata[2]}<br>"
            "Latitude: %{lat:.3f}<br>"
            "Longitude: %{lon:.3f}<br>"
            "Depth: %{customdata[3]:.1f} km<br>"
            "<a href='%{customdata[0]}' target='_blank'>Open USGS event</a>"
            "<extra></extra>"
        ),
        customdata=earthquakes[["url", "magnitude", "time", "depth"]].to_numpy(),
    )
    figure.update_geos(showcountries=True, showland=True, landcolor="rgb(243, 243, 243)")
    return figure


def make_repository_chart(repositories: pd.DataFrame) -> go.Figure:
    """Create a horizontal bar chart with clickable repository links."""
    if repositories.empty:
        figure = go.Figure()
        figure.add_annotation(text="No repository data is available.", showarrow=False)
        figure.update_layout(title="Top 10 Python Repositories by Stars")
        return figure

    ordered = repositories.sort_values("stars", ascending=True)
    figure = go.Figure(
        go.Bar(
            x=ordered["stars"],
            y=ordered["name"],
            orientation="h",
            marker_color="#4c78a8",
            customdata=ordered[["description", "url"]].to_numpy(),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Stars: %{x:,}<br>"
                "%{customdata[0]}<br>"
                "<a href='%{customdata[1]}' target='_blank'>Open repository</a>"
                "<extra></extra>"
            ),
        )
    )
    figure.update_layout(
        title="Top 10 Python Repositories by Stars",
        xaxis_title="Stars",
        yaxis_title="Repository",
        yaxis={"autorange": "reversed"},
        margin={"l": 150},
    )
    return figure


def save_dashboard(map_figure: go.Figure, repository_figure: go.Figure) -> None:
    """Save both interactive charts together in a single HTML dashboard."""
    map_html = pio.to_html(map_figure, full_html=False, include_plotlyjs="cdn")
    repository_html = pio.to_html(repository_figure, full_html=False, include_plotlyjs=False)
    page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live Data Pipeline &amp; Interactive Dashboard</title>
  <style>
    body {{ max-width: 1200px; margin: 0 auto; padding: 1rem; font-family: Arial, sans-serif; }}
    .chart {{ margin: 1rem 0 2rem; }}
  </style>
</head>
<body>
  <h1>Live Data Pipeline &amp; Interactive Dashboard</h1>
  <section class="chart">{map_html}</section>
  <section class="chart">{repository_html}</section>
</body>
</html>
"""
    OUTPUT_FILE.write_text(page, encoding="utf-8")
    logging.info("Dashboard saved to %s", OUTPUT_FILE.resolve())


def main() -> None:
    """Fetch the latest data and generate the interactive dashboard."""
    earthquakes = fetch_earthquakes()
    repositories = fetch_top_repositories()

    logging.info("Loaded %d earthquake events.", len(earthquakes))
    logging.info("Loaded %d GitHub repositories.", len(repositories))
    save_dashboard(
        make_earthquake_map(earthquakes),
        make_repository_chart(repositories),
    )


if __name__ == "__main__":
    main()
