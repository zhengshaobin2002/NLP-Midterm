#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze author migration patterns from chinesename_address_year.csv.

Outputs:
    - author_maps/crosscountry_migration.csv   : authors with addresses in multiple countries
    - author_maps/incountry_migration.csv      : authors with multiple addresses but only one country
    - author_maps/crosscountry_arc_map.html    : world map with arced migration flows
    - author_maps/crosscountry_sankey.html     : Sankey diagram of origin-destination flows
    - author_maps/incountry_migration_map.html : world map showing in-country migration author counts by country
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


DEFAULT_INPUT_FILE = "chinesename_address_year.csv"
DEFAULT_OUTPUT_DIR = "author_maps"
BASE_DIR = Path(__file__).resolve().parent

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

STATIC_IMAGE_FORMAT = "png"
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "Australia": (133.7751, -25.2744),
    "Austria": (14.5501, 47.5162),
    "Belgium": (4.4699, 50.5039),
    "Brunei": (114.7277, 4.5353),
    "Cambodia": (104.9903, 12.5657),
    "Canada": (-106.3468, 56.1304),
    "Chile": (-71.5429, -35.6751),
    "China": (104.1954, 35.8617),
    "Colombia": (-74.2973, 4.5709),
    "Czech Republic": (15.4729, 49.8175),
    "Denmark": (9.5018, 56.2639),
    "Finland": (25.7482, 61.9241),
    "France": (2.2137, 46.2276),
    "Germany": (10.4515, 51.1657),
    "Ghana": (-1.0232, 7.9465),
    "Greece": (21.8243, 39.0742),
    "Hungary": (19.5033, 47.1625),
    "Indonesia": (113.9213, -0.7893),
    "Ireland": (-8.2439, 53.4129),
    "Israel": (34.8516, 31.0461),
    "Italy": (12.5674, 41.8719),
    "Japan": (138.2529, 36.2048),
    "Malaysia": (101.9758, 4.2105),
    "Netherlands": (5.2913, 52.1326),
    "New Zealand": (174.8860, -40.9006),
    "Norway": (8.4689, 60.4720),
    "Philippines": (121.7740, 12.8797),
    "Poland": (19.1451, 51.9194),
    "Russia": (105.3188, 61.5240),
    "Singapore": (103.8198, 1.3521),
    "Sint Maarten": (-63.0548, 18.0425),
    "South Africa": (22.9375, -30.5595),
    "South Korea": (127.7669, 35.9078),
    "Spain": (-3.7492, 40.4637),
    "Sweden": (18.6435, 60.1282),
    "Switzerland": (8.2275, 46.8182),
    "Thailand": (100.9925, 15.8700),
    "Turkey": (35.2433, 38.9637),
    "United Arab Emirates": (53.8478, 23.4241),
    "United Kingdom": (-3.4360, 55.3781),
    "United States": (-95.7129, 37.0902),
    "Vietnam": (108.2772, 14.0583),
    "Zimbabwe": (29.1549, -19.0154),
    "Pr 00708 Usa": (-95.7129, 37.0902),
}
COUNTRY_ALIASES = {
    "USA": "United States",
    "U S A": "United States",
    "UNITED STATES": "United States",
    "UNITED STATES OF AMERICA": "United States",
    "US": "United States",
    "PR USA": "United States",
    "ENGLAND": "United Kingdom",
    "SCOTLAND": "United Kingdom",
    "WALES": "United Kingdom",
    "NORTHERN IRELAND": "United Kingdom",
    "NORTH IRELAND": "United Kingdom",
    "UK": "United Kingdom",
    "U K": "United Kingdom",
    "UNITED KINGDOM": "United Kingdom",
    "GREAT BRITAIN": "United Kingdom",
    "HONG KONG": "China",
    "HONG KONG SAR": "China",
    "TAIWAN": "China",
    "MACAO": "China",
    "MACAU": "China",
    "PEOPLE S REPUBLIC OF CHINA": "China",
    "PEOPLES REPUBLIC OF CHINA": "China",
    "PEOPLES R CHINA": "China",
    "PEOPLE S R CHINA": "China",
    "P R CHINA": "China",
    "P R C": "China",
    "PRC": "China",
    "MAINLAND CHINA": "China",
    "U ARAB EMIRATES": "United Arab Emirates",
    "TURKIYE": "Turkey",
}


def normalize_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()


def extract_country(address: str) -> str | None:
    if not isinstance(address, str) or not address.strip():
        return None

    parts = [part.strip() for part in address.split(",") if part.strip()]
    if not parts:
        return None

    last_normalized = normalize_text(parts[-1])
    if not last_normalized:
        return None

    if last_normalized in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[last_normalized]

    if last_normalized.startswith("SINGAPORE"):
        return "Singapore"

    first_token = last_normalized.split(" ", 1)[0]
    if first_token in US_STATE_CODES:
        return "United States"

    if last_normalized in {"UK", "UNITED KINGDOM", "GREAT BRITAIN"}:
        return "United Kingdom"

    if last_normalized in {"CHINA", "PEOPLES REPUBLIC OF CHINA", "PEOPLES R CHINA", "P R CHINA"}:
        return "China"

    return last_normalized.title()


def load_data(input_file: Path) -> pd.DataFrame:
    df = pd.read_csv(input_file, encoding="utf-8-sig")
    required_columns = {"name", "address", "year"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in input file: {sorted(missing)}")

    df = df.copy()
    df["name"] = df["name"].astype(str).str.strip()
    df["address"] = df["address"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["name", "address", "year"])
    return df


# ---------------------------------------------------------------------------
# Cross-country migration (retained from original script)
# ---------------------------------------------------------------------------

def build_crosscountry_records(df: pd.DataFrame) -> pd.DataFrame:
    """Authors whose addresses span more than one distinct country."""
    work_frame = df.copy()
    work_frame["country"] = work_frame["address"].map(extract_country)
    work_frame = work_frame.dropna(subset=["country"])

    author_country_counts = work_frame.groupby("name")["country"].nunique()
    migrating_authors = author_country_counts[author_country_counts > 1].index

    migration_frame = work_frame[work_frame["name"].isin(migrating_authors)].copy()
    migration_frame = migration_frame.drop_duplicates(subset=["name", "country", "year"])
    migration_frame = migration_frame.sort_values(
        ["name", "year", "country"], ascending=[True, True, True]
    )
    return migration_frame[["name", "country", "year"]]


def save_crosscountry_csv(df: pd.DataFrame, output_root: Path) -> tuple[Path, int, pd.DataFrame]:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "crosscountry_migration.csv"
    frame = build_crosscountry_records(df)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    distinct_authors = frame["name"].nunique()
    return path, distinct_authors, frame


def build_crosscountry_flows(df: pd.DataFrame) -> Counter[tuple[str, str]]:
    """
    Build origin->destination flows by looking at adjacent (year, country)
    pairs for each author.
    """
    flows: Counter[tuple[str, str]] = Counter()

    for _, group in df.groupby("name"):
        sorted_rows = group.sort_values(["year", "country"]).drop_duplicates(
            subset=["year", "country"]
        )
        countries = sorted_rows["country"].tolist()
        for i in range(len(countries) - 1):
            origin = countries[i]
            dest = countries[i + 1]
            if origin != dest:
                flows[(origin, dest)] += 1

    return flows


def save_crosscountry_arc_map(
    flows: Counter[tuple[str, str]],
    output_dir: Path,
    min_flow: int = 1,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "crosscountry_arc_map.html"

    filtered = {k: v for k, v in flows.items() if v >= min_flow}
    max_flow = max(filtered.values()) if filtered else 1

    fig = go.Figure()

    marker_countries = set()
    for origin, dest in filtered:
        marker_countries.add(origin)
        marker_countries.add(dest)

    marker_lons = []
    marker_lats = []
    marker_texts = []
    for country in sorted(marker_countries):
        if country in COUNTRY_COORDS:
            lon, lat = COUNTRY_COORDS[country]
            marker_lons.append(lon)
            marker_lats.append(lat)
            marker_texts.append(country)

    if marker_lons:
        fig.add_trace(
            go.Scattergeo(
                lon=marker_lons,
                lat=marker_lats,
                mode="markers+text",
                text=marker_texts,
                textposition="top center",
                marker=dict(size=8, color="#1f77b4"),
                name="Countries",
                hoverinfo="text",
            )
        )

    for (origin, dest), count in sorted(filtered.items(), key=lambda x: x[1]):
        if origin not in COUNTRY_COORDS or dest not in COUNTRY_COORDS:
            continue

        lon0, lat0 = COUNTRY_COORDS[origin]
        lon1, lat1 = COUNTRY_COORDS[dest]
        mid_lon = (lon0 + lon1) / 2
        mid_lat = (lat0 + lat1) / 2
        dist = math.sqrt((lon1 - lon0) ** 2 + (lat1 - lat0) ** 2)
        lift = min(dist * 0.35, 35)
        if mid_lat >= 0:
            mid_lat += lift
        else:
            mid_lat -= lift

        line_lons = [lon0, mid_lon, lon1]
        line_lats = [lat0, mid_lat, lat1]

        width = 1 + (count / max_flow) * 5
        opacity = 0.3 + (count / max_flow) * 0.5

        fig.add_trace(
            go.Scattergeo(
                lon=line_lons,
                lat=line_lats,
                mode="lines",
                line=dict(width=width, color=f"rgba(200, 50, 50, {opacity})"),
                name=f"{origin} → {dest} ({count})",
                hoverinfo="name",
                showlegend=False,
            )
        )

    fig.update_layout(
        title="Cross-country author migration flows",
        geo=dict(
            showframe=False,
            showcoastlines=True,
            showcountries=True,
            showland=True,
            landcolor="#e6e6e6",
            countrycolor="white",
            projection_type="natural earth",
        ),
        margin=dict(l=0, r=10, t=70, b=0),
    )

    fig.write_html(str(html_path), include_plotlyjs="cdn", full_html=True)
    return html_path


def save_crosscountry_sankey(
    flows: Counter[tuple[str, str]],
    output_dir: Path,
    min_flow: int = 1,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "crosscountry_sankey.html"

    filtered = {k: v for k, v in flows.items() if v >= min_flow}

    nodes = set()
    for origin, dest in filtered:
        nodes.add(origin)
        nodes.add(dest)
    node_list = sorted(nodes)
    node_index = {n: i for i, n in enumerate(node_list)}

    sources = []
    targets = []
    values = []
    for (origin, dest), count in filtered.items():
        sources.append(node_index[origin])
        targets.append(node_index[dest])
        values.append(count)

    fig = go.Figure(
        data=[
            go.Sankey(
                node=dict(
                    pad=15,
                    thickness=20,
                    line=dict(color="black", width=0.5),
                    label=node_list,
                    color="rgba(31, 119, 180, 0.8)",
                ),
                link=dict(
                    source=sources,
                    target=targets,
                    value=values,
                    color="rgba(200, 50, 50, 0.3)",
                ),
            )
        ]
    )

    fig.update_layout(
        title_text="Cross-country author migration (origin → destination)",
        font_size=12,
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig.write_html(str(html_path), include_plotlyjs="cdn", full_html=True)
    return html_path


# ---------------------------------------------------------------------------
# In-country migration (new)
# ---------------------------------------------------------------------------

def extract_institution(address: str) -> str:
    """Extract the first segment of an address (university/institution name)."""
    if not isinstance(address, str) or not address.strip():
        return ""
    parts = address.split(",", 1)
    return parts[0].strip()


def build_incountry_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Authors with multiple distinct addresses but all within a single country,
    and the addresses belong to at least two different institutions
    (first segment of the address, e.g. university name).
    Returns columns: name, address, year, country.
    """
    work_frame = df.copy()
    work_frame["country"] = work_frame["address"].map(extract_country)
    work_frame["institution"] = work_frame["address"].map(extract_institution)
    work_frame = work_frame.dropna(subset=["country"])

    # Count distinct addresses, countries, and institutions per author
    author_stats = work_frame.groupby("name").agg(
        address_count=("address", "nunique"),
        country_count=("country", "nunique"),
        institution_count=("institution", "nunique"),
    )

    incountry_authors = author_stats[
        (author_stats["address_count"] > 1)
        & (author_stats["country_count"] == 1)
        & (author_stats["institution_count"] >= 2)
    ].index

    incountry_frame = work_frame[work_frame["name"].isin(incountry_authors)].copy()
    incountry_frame = incountry_frame.drop_duplicates(subset=["name", "address", "year"])
    incountry_frame = incountry_frame.sort_values(
        ["name", "year", "address"], ascending=[True, True, True]
    )
    return incountry_frame[["name", "address", "year", "country"]]


def save_incountry_csv(df: pd.DataFrame, output_root: Path) -> tuple[Path, int]:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / "incountry_migration.csv"
    frame = build_incountry_records(df)
    frame.to_csv(path, index=False, encoding="utf-8-sig")
    distinct_authors = frame["name"].nunique()
    return path, distinct_authors


# ---------------------------------------------------------------------------
# Map helpers (adapted from original)
# ---------------------------------------------------------------------------

def make_blue_palette(bin_count: int) -> list[str]:
    return px.colors.sample_colorscale(
        "Blues", [0.35 + 0.6 * i / max(bin_count - 1, 1) for i in range(bin_count)]
    )


def format_count_range(interval: pd.Interval) -> str:
    lower = max(1, math.ceil(float(interval.left)))
    upper = max(lower, math.floor(float(interval.right)))
    if lower == upper:
        return str(lower)
    return f"{lower}-{upper}"


def build_discrete_color_bins(counts: pd.DataFrame) -> pd.DataFrame:
    if counts.empty:
        return counts.assign(color_bin=pd.Series(dtype="object"))

    binned = counts.copy()
    positive = binned[binned["people_count"] > 0].copy()
    if positive.empty:
        binned["color_bin"] = pd.NA
        return binned

    bin_count = min(5, positive["people_count"].nunique())
    if bin_count <= 1:
        binned["color_bin"] = f"{int(positive['people_count'].iloc[0])}"
        return binned

    categories = pd.qcut(positive["people_count"], q=bin_count, duplicates="drop")
    label_map = {interval: format_count_range(interval) for interval in categories.cat.categories}
    binned["color_bin"] = pd.NA
    binned.loc[positive.index, "color_bin"] = categories.map(label_map)
    return binned


def export_static_image(figure: go.Figure, image_path: Path) -> None:
    try:
        figure.write_image(
            str(image_path),
            format=image_path.suffix.lstrip("."),
            width=1400,
            height=780,
            scale=2,
        )
    except ValueError as exc:
        message = str(exc).lower()
        if "kaleido" in message:
            raise RuntimeError(
                "Static image export requires kaleido. Install it with "
"`pip install kaleido` or `conda install -c conda-forge kaleido`, then rerun."
            ) from exc
        raise


def build_incountry_country_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate in-country migration authors by their single country."""
    counts = (
        df.groupby("country")["name"]
        .nunique()
        .reset_index(name="people_count")
        .sort_values(["people_count", "country"], ascending=[False, True])
    )
    return counts


def save_incountry_map(
    counts: pd.DataFrame,
    output_dir: Path,
    image_format: str,
    export_image: bool,
) -> tuple[Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "incountry_migration_map.html"
    image_path = output_dir / f"incountry_migration_map.{image_format}"
    label_font_size = 10

    binned = build_discrete_color_bins(counts)
    positive = binned[binned["people_count"] > 0].copy()

    figure = go.Figure()

    if not positive.empty:
        ordered_positive = positive.sort_values(
            ["people_count", "country"], ascending=[True, True]
        )
        bin_labels = list(dict.fromkeys(ordered_positive["color_bin"].tolist()))
        palette = make_blue_palette(len(bin_labels))

        for label, color in zip(bin_labels, palette, strict=False):
            bin_rows = positive[positive["color_bin"] == label]
            figure.add_trace(
                go.Choropleth(
                    locations=bin_rows["country"],
                    locationmode="country names",
                    z=bin_rows["people_count"],
                    text=bin_rows["country"],
                    name=label,
                    colorscale=[[0, color], [1, color]],
                    showscale=False,
                    marker_line_color="white",
                    marker_line_width=0.4,
                    hovertemplate="Country/region: %{location}<br>People: %{z}<extra></extra>",
                )
            )
            figure.add_trace(
                go.Scattergeo(
                    lon=[0],
                    lat=[0],
                    mode="markers",
                    marker=dict(size=10, color=color, symbol="square"),
                    name=label,
                    showlegend=True,
                    hoverinfo="skip",
                    visible="legendonly",
                )
            )

        darkest_bin_label = bin_labels[-1] if bin_labels else None
        non_dark_rows = (
            positive if darkest_bin_label is None
            else positive[positive["color_bin"] != darkest_bin_label]
        )
        dark_rows = (
            positive[positive["color_bin"] == darkest_bin_label]
            if darkest_bin_label is not None
            else positive.iloc[0:0]
        )

        if not non_dark_rows.empty:
            figure.add_trace(
                go.Scattergeo(
                    locations=non_dark_rows["country"],
                    locationmode="country names",
                    text=non_dark_rows["people_count"].astype(str),
                    mode="text",
                    textposition="middle center",
                    textfont=dict(size=label_font_size, color="#1f1f1f"),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

        if not dark_rows.empty:
            figure.add_trace(
                go.Scattergeo(
                    locations=dark_rows["country"],
                    locationmode="country names",
                    text=dark_rows["people_count"].astype(str),
                    mode="text",
                    textposition="middle center",
                    textfont=dict(size=label_font_size, color="#ffffff"),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    figure.update_layout(
        title="In-country migration authors by country",
        geo=dict(
            showframe=False,
            showcoastlines=True,
            showcountries=True,
            showland=True,
            landcolor="#e6e6e6",
            countrycolor="white",
            projection_type="natural earth",
        ),
        legend=dict(
            x=0.88,
            y=0.02,
            xanchor="right",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.82)",
            bordercolor="#d0d0d0",
            borderwidth=1,
            font=dict(size=11),
        ),
        margin=dict(l=0, r=10, t=70, b=0),
    )

    figure.write_html(str(html_path), include_plotlyjs="cdn", full_html=True)
    if export_image:
        export_static_image(figure, image_path)
        return html_path, image_path
    return html_path, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    input_path = BASE_DIR / DEFAULT_INPUT_FILE
    output_dir = BASE_DIR / DEFAULT_OUTPUT_DIR
    df = load_data(input_path)

    # ---- Cross-country migration ----
    cross_path, cross_authors, cross_frame = save_crosscountry_csv(df, output_dir)
    print(f"Cross-country CSV written to {cross_path}", flush=True)
    print(f"Cross-country distinct authors: {cross_authors}", flush=True)

    cross_flows = build_crosscountry_flows(cross_frame)
    print(f"Extracted {len(cross_flows)} unique origin→destination flows.", flush=True)

    print("Top 10 cross-country flows:", flush=True)
    for (origin, dest), count in cross_flows.most_common(10):
        print(f"  {origin} → {dest}: {count}", flush=True)

    arc_path = save_crosscountry_arc_map(cross_flows, output_dir, min_flow=1)
    print(f"Cross-country arc map saved to {arc_path}", flush=True)

    sankey_path = save_crosscountry_sankey(cross_flows, output_dir, min_flow=1)
    print(f"Cross-country Sankey diagram saved to {sankey_path}", flush=True)

    # ---- In-country migration ----
    incountry_path, incountry_authors = save_incountry_csv(df, output_dir)
    print(f"In-country CSV written to {incountry_path}", flush=True)
    print(f"In-country distinct authors: {incountry_authors}", flush=True)

    # ---- In-country map ----
    incountry_df = build_incountry_records(df)
    incountry_counts = build_incountry_country_counts(incountry_df)
    print(f"Rendering in-country migration map...", flush=True)
    html_path, image_path = save_incountry_map(
        incountry_counts,
        output_dir,
        STATIC_IMAGE_FORMAT,
        False,
    )
    print(
        f"In-country map: {len(incountry_counts)} countries/regions -> {html_path}",
        flush=True,
    )
    if image_path is not None:
        print(f"In-country static image -> {image_path}", flush=True)


if __name__ == "__main__":
    main()
