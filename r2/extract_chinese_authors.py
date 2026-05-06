#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract Chinese author-address-year mappings from names_address_year.xlsx
using unique_authors.csv as the name filter.

Input files:
  - r1/csv/unique_authors.csv    : one author name per line
  - r2/names_address_year.csv    : actually an xlsx with columns:
                                   Author Full Names, Addresses, Publication Year

Output file:
  - r2/chinesename_address_year.csv  : columns name, address, year

Address parsing rules:
  - Addresses are separated by semicolons, but semicolons inside [...] brackets
    belong to the author-name list and should NOT split the address.
  - If an address starts with [Name1; Name2], only those names map to it.
  - If an address has no [...] prefix, ALL authors on this row map to it.
  - Only names that appear in unique_authors.csv are kept in the output.
"""

import csv
import re
from pathlib import Path

import pandas as pd


def load_unique_authors(path: Path) -> set[str]:
    """Load a set of author names from a one-name-per-line CSV/txt file."""
    names = set()
    with open(path, "r", encoding="utf-8-sig") as f:
        for line in f:
            name = line.strip()
            if name:
                names.add(name)
    return names


def split_addresses(addr: str) -> list[str]:
    """
    Split an address string by semicolons, but ignore semicolons that are
    inside [...] brackets (they separate author names, not addresses).
    """
    if not isinstance(addr, str) or not addr.strip():
        return []

    parts = []
    current = ""
    depth = 0
    for char in addr:
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        elif char == ";" and depth == 0:
            parts.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        parts.append(current.strip())
    return parts


def parse_address_part(part: str) -> tuple[list[str] | None, str]:
    """
    Parse a single address fragment.

    Returns:
        (names, address) where:
        - names is a list of author names if the part starts with [...],
          or None if there is no [...] prefix.
        - address is the actual address text (with the [...] prefix removed).
    """
    part = part.strip()
    match = re.match(r"^\[(.+?)\]\s*(.*)$", part)
    if match:
        names_in_bracket = [n.strip() for n in match.group(1).split(";") if n.strip()]
        address = match.group(2).strip()
        return names_in_bracket, address
    else:
        return None, part


def main() -> None:
    # ---- paths ----
    project_root = Path(__file__).parent.parent  # go up from r2/ to project root
    unique_authors_path = project_root / "r1" / "csv" / "unique_authors.csv"
    input_path = project_root / "r2" / "names_address_year.csv"  # actually xlsx
    output_path = project_root / "r2" / "chinesename_address_year.csv"

    # ---- load unique authors ----
    unique_authors = load_unique_authors(unique_authors_path)
    print(f"Loaded {len(unique_authors):,} unique author names.")

    # ---- load source data ----
    df = pd.read_excel(input_path)
    print(f"Loaded {len(df):,} rows from {input_path.name}.")

    records = []

    for idx, row in df.iterrows():
        authors_raw = str(row.get("Author Full Names", "")).strip()
        addresses_raw = str(row.get("Addresses", "")).strip()
        year = row.get("Publication Year")

        if not authors_raw or not addresses_raw or pd.isna(year):
            continue

        # split authors (they are always separated by semicolons)
        all_authors = [a.strip() for a in authors_raw.split(";") if a.strip()]

        # keep only authors that are in the unique list
        relevant_authors = [a for a in all_authors if a in unique_authors]
        if not relevant_authors:
            continue

        # split addresses, respecting [...] brackets
        address_parts = split_addresses(addresses_raw)

        for part in address_parts:
            bracket_names, address = parse_address_part(part)

            if not address:
                continue

            if bracket_names is not None:
                # explicit mapping: only the names inside the brackets get this address
                matched = [n for n in bracket_names if n in unique_authors]
                for name in matched:
                    records.append({"name": name, "address": address, "year": int(year)})
            else:
                # no bracket prefix: all relevant authors on this row get this address
                for name in relevant_authors:
                    records.append({"name": name, "address": address, "year": int(year)})

    # ---- deduplicate ----
    out_df = pd.DataFrame(records).drop_duplicates(subset=["name", "address", "year"])
    print(f"Extracted {len(out_df):,} unique name-address-year records.")

    # ---- write output ----
    out_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"Output written to {output_path}")


if __name__ == "__main__":
    main()
