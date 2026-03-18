"""Minimal data loaders used by the web resolver."""

from __future__ import annotations

import csv
from pathlib import Path

from .utils import normalize_hsn_digits, normalize_text


def load_hsn_master(path: Path) -> list[dict]:
    """Load GST master rows with normalized fields needed by lookup."""
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            hsn8_raw = (
                row.get("hsn_8digit")
                or row.get("hsn8")
                or row.get("hsn")
                or row.get("hsn_code")
                or ""
            )
            hsn8 = normalize_hsn_digits(hsn8_raw)
            if len(hsn8) != 8:
                continue

            description = (
                row.get("description")
                or row.get("product")
                or row.get("product_description")
                or ""
            )
            category = row.get("category") or row.get("chapter_name") or ""

            aliases_raw = row.get("aliases") or ""
            aliases = [a.strip() for a in aliases_raw.split("|") if a.strip()]

            rows.append(
                {
                    "hsn8": hsn8,
                    "description": description,
                    "category": category,
                    "aliases_norm": [normalize_text(a) for a in aliases],
                }
            )
    return rows
