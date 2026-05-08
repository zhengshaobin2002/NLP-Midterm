from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px


TARGET_YEARS = [1991, 2000, 2010, 2020, 2024]
DEFAULT_INPUT_FILE = "r2/chinesename_address_year.csv"
DEFAULT_OUTPUT_DIR = "r2/maps"

US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC",
}

STATIC_IMAGE_FORMAT = "png"
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
    required_columns = {"name", "address", "year", "Article Title"}
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in input file: {sorted(missing)}")

    df = df.copy()
    df["name"] = df["name"].astype(str).str.strip()
    df["address"] = df["address"].astype(str).str.strip()
    df["Article Title"] = df["Article Title"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["name", "address", "year", "Article Title"])
    return df


def print_name_address_summary(df: pd.DataFrame) -> None:
    address_counts = df.groupby("name")["address"].nunique().sort_values(ascending=False)
    multi_address_people = address_counts[address_counts > 1]

    print(f"Total valid rows: {len(df)}")
    print(f"People with more than one address: {len(multi_address_people)}")
    if not multi_address_people.empty:
        print("Top multi-address people:")
        for name, count in multi_address_people.head(10).items():
            print(f"  {name}: {count} addresses")


def build_yearly_country_counts(
    df: pd.DataFrame,
    years: list[int],
    count_col: str,
    output_col: str,
    dedup_cols: list[str] | None = None,
) -> dict[int, pd.DataFrame]:
    results: dict[int, pd.DataFrame] = {}

    for year in years:
        year_frame = df[df["year"] == year].copy()
        if year_frame.empty:
            results[year] = pd.DataFrame(columns=["country", output_col])
            continue

        year_frame["country"] = year_frame["address"].map(extract_country)
        year_frame = year_frame.dropna(subset=["country"])
        if dedup_cols:
            year_frame = year_frame.drop_duplicates(subset=dedup_cols)

        counts = (
            year_frame.groupby("country")[count_col]
            .nunique()
            .reset_index(name=output_col)
            .sort_values([output_col, "country"], ascending=[False, True])
        )
        results[year] = counts

    return results


def make_blue_palette(bin_count: int) -> list[str]:
    return px.colors.sample_colorscale("Blues", [0.35 + 0.6 * i / max(bin_count - 1, 1) for i in range(bin_count)])


def format_count_range(interval: pd.Interval) -> str:
    lower = max(1, math.ceil(float(interval.left)))
    upper = max(lower, math.floor(float(interval.right)))
    if lower == upper:
        return str(lower)
    return f"{lower}-{upper}"


def build_discrete_color_bins(counts: pd.DataFrame, count_col: str = "people_count") -> pd.DataFrame:
    if counts.empty:
        return counts.assign(color_bin=pd.Series(dtype="object"))

    binned = counts.copy()
    positive = binned[binned[count_col] > 0].copy()
    if positive.empty:
        binned["color_bin"] = pd.NA
        return binned

    bin_count = min(5, positive[count_col].nunique())
    if bin_count <= 1:
        binned["color_bin"] = f"{int(positive[count_col].iloc[0])}"
        return binned

    categories = pd.qcut(positive[count_col], q=bin_count, duplicates="drop")
    label_map = {interval: format_count_range(interval) for interval in categories.cat.categories}
    binned["color_bin"] = pd.NA
    binned.loc[positive.index, "color_bin"] = categories.map(label_map)
    return binned


def build_fixed_color_bins(
    counts: pd.DataFrame,
    bins: list[int],
    labels: list[str],
    count_col: str = "people_count",
) -> pd.DataFrame:
    if counts.empty:
        return counts.assign(color_bin=pd.Series(dtype="object"))

    binned = counts.copy()
    positive = binned[binned[count_col] > 0].copy()
    if positive.empty:
        binned["color_bin"] = pd.NA
        return binned

    categories = pd.cut(positive[count_col], bins=bins, labels=labels, include_lowest=True)
    binned["color_bin"] = pd.NA
    binned.loc[positive.index, "color_bin"] = categories.astype("object")
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
                "Static image export requires kaleido. Install it with `pip install kaleido` "
                "or `conda install -c conda-forge kaleido`, then rerun the script."
            ) from exc
        raise


def save_year_map(
    counts: pd.DataFrame,
    year: int,
    output_dir: Path,
    image_format: str,
    export_image: bool,
    count_col: str = "people_count",
    value_label: str = "People",
    title_prefix: str = "Author distribution",
    filename_prefix: str = "author_distribution",
) -> tuple[Path, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / f"{filename_prefix}_{year}.html"
    image_path = output_dir / f"{filename_prefix}_{year}.{image_format}"
    label_font_size = 10

    if count_col == "people_count":
        if year == 2010:
            binned = build_fixed_color_bins(
                counts,
                bins=[0, 10, 20, 155],
                labels=["1-10", "11-20", "21-155"],
                count_col=count_col,
            )
        elif year == 2020:
            binned = build_fixed_color_bins(
                counts,
                bins=[0, 20, 50, 571],
                labels=["1-20", "21-50", "51-571"],
                count_col=count_col,
            )
        elif year == 2024:
            if counts.empty or counts[count_col].dropna().empty:
                max_val = 51
            else:
                max_val = int(counts[count_col].max())
                if max_val < 51:
                    max_val = 51

            binned = build_fixed_color_bins(
                counts,
                bins=[0, 20, 50, max_val],
                labels=["1-20", "21-50", "51-1041"],
                count_col=count_col,
            )
        else:
            binned = build_discrete_color_bins(counts, count_col=count_col)
    else:
        if year == 2010:
            binned = build_fixed_color_bins(
                counts,
                bins=[0, 10, 20, 159],
                labels=["1-10", "11-20", "21-159"],
                count_col=count_col,
            )
        elif year == 2020:
            binned = build_fixed_color_bins(
                counts,
                bins=[0, 20, 50, 527],
                labels=["1-20", "21-50", "51-527"],
                count_col=count_col,
            )
        elif year == 2024:
            binned = build_fixed_color_bins(
                counts,
                bins=[0, 30, 60, 995],
                labels=["1-30", "31-60", "61-995"],
                count_col=count_col,
            )
        else:
            binned = build_discrete_color_bins(counts, count_col=count_col)

    positive = binned[binned[count_col] > 0].copy()

    figure = go.Figure()

    if not positive.empty:
        ordered_positive = positive.sort_values([count_col, "country"], ascending=[True, True])
        bin_labels = list(dict.fromkeys(ordered_positive["color_bin"].tolist()))
        palette = make_blue_palette(len(bin_labels))

        for label, color in zip(bin_labels, palette, strict=False):
            bin_rows = positive[positive["color_bin"] == label]
            figure.add_trace(
                go.Choropleth(
                    locations=bin_rows["country"],
                    locationmode="country names",
                    z=bin_rows[count_col],
                    text=bin_rows["country"],
                    name=label,
                    colorscale=[[0, color], [1, color]],
                    showscale=False,
                    marker_line_color="white",
                    marker_line_width=0.4,
                    hovertemplate=f"Country/region: %{{location}}<br>{value_label}: %{{z}}<extra></extra>",
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
        non_dark_rows = positive if darkest_bin_label is None else positive[positive["color_bin"] != darkest_bin_label]
        dark_rows = positive[positive["color_bin"] == darkest_bin_label] if darkest_bin_label is not None else positive.iloc[0:0]

        if not non_dark_rows.empty:
            figure.add_trace(
                go.Scattergeo(
                    locations=non_dark_rows["country"],
                    locationmode="country names",
                    text=non_dark_rows[count_col].astype(str),
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
                    text=dark_rows[count_col].astype(str),
                    mode="text",
                    textposition="middle center",
                    textfont=dict(size=label_font_size, color="#ffffff"),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    figure.update_layout(
        title=f"{title_prefix} in {year}",
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


def save_summary_csv(
    yearly_counts: dict[int, pd.DataFrame],
    output_dir: Path,
    count_col: str,
    filename: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / filename
    records = []

    for year, counts in yearly_counts.items():
        for row in counts.itertuples(index=False):
            records.append({"year": year, "country": row.country, count_col: int(getattr(row, count_col))})

    pd.DataFrame(records).to_csv(summary_path, index=False, encoding="utf-8-sig")
    return summary_path


def main() -> None:
    input_path = Path(DEFAULT_INPUT_FILE)
    output_dir = Path(DEFAULT_OUTPUT_DIR)
    df = load_data(input_path)
    print_name_address_summary(df)

    # Author distribution
    yearly_author_counts = build_yearly_country_counts(
        df, TARGET_YEARS, count_col="name", output_col="people_count", dedup_cols=["name", "country"]
    )
    author_summary_path = save_summary_csv(
        yearly_author_counts, output_dir, count_col="people_count", filename="yearly_country_counts.csv"
    )
    print(f"Author summary CSV written to {author_summary_path}", flush=True)

    for year in TARGET_YEARS:
        print(f"Rendering author map for year {year}...", flush=True)
        html_path, image_path = save_year_map(
            yearly_author_counts[year],
            year,
            output_dir,
            STATIC_IMAGE_FORMAT,
            False,
            count_col="people_count",
            value_label="People",
            title_prefix="Author distribution",
            filename_prefix="author_distribution",
        )
        print(f"Year {year} (authors): {len(yearly_author_counts[year])} countries/regions -> {html_path}")
        if image_path is not None:
            print(f"Year {year} (authors): static image -> {image_path}")

    # Article distribution
    yearly_article_counts = build_yearly_country_counts(
        df, TARGET_YEARS, count_col="Article Title", output_col="article_count"
    )
    article_summary_path = save_summary_csv(
        yearly_article_counts, output_dir, count_col="article_count", filename="yearly_country_article_counts.csv"
    )
    print(f"Article summary CSV written to {article_summary_path}", flush=True)

    for year in TARGET_YEARS:
        print(f"Rendering article map for year {year}...", flush=True)
        html_path, image_path = save_year_map(
            yearly_article_counts[year],
            year,
            output_dir,
            STATIC_IMAGE_FORMAT,
            False,
            count_col="article_count",
            value_label="Articles",
            title_prefix="Article distribution",
            filename_prefix="article_distribution",
        )
        print(f"Year {year} (articles): {len(yearly_article_counts[year])} countries/regions -> {html_path}")
        if image_path is not None:
            print(f"Year {year} (articles): static image -> {image_path}")


if __name__ == "__main__":
    main()
