"""Minimal data loaders used by the web resolver."""

from __future__ import annotations

import csv
from pathlib import Path

from .utils import normalize_hsn_digits, normalize_text


_HEADER_TOKENS = {
    "hsn8",
    "hsn_8digit",
    "hsn",
    "hsn_code",
    "description",
    "category",
}


def _split_line(line: str) -> list[str]:
    """Split one row that may be tab- or comma-delimited."""
    raw = line.rstrip("\n\r")
    if "\t" in raw and raw.count("\t") >= 1:
        return [p.strip() for p in raw.split("\t")]
    return [p.strip() for p in next(csv.reader([raw]))]


def _is_header_like(parts: list[str], full_line: str) -> bool:
    if not parts:
        return True
    first = parts[0].strip().lower()
    line_lower = full_line.lower()
    if first in _HEADER_TOKENS:
        return True
    if "hsn8" in line_lower and "description" in line_lower:
        return True
    return False


def load_hsn_master(path: Path) -> list[dict]:
    """Load GST master rows with normalized fields needed by lookup."""
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line in handle:
            if not line.strip():
                continue

            parts = _split_line(line)
            if _is_header_like(parts, line):
                continue

            hsn8 = normalize_hsn_digits(parts[0] if parts else "")
            if len(hsn8) != 8:
                continue

            description = parts[1] if len(parts) > 1 else ""
            category = parts[2] if len(parts) > 2 else ""
            aliases_raw = parts[3] if len(parts) > 3 else ""

            dedupe_key = (hsn8, normalize_text(description))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

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
