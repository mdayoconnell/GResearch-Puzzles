#!/usr/bin/env python3
"""Export maxima.csv as a small browser-readable data file."""

from __future__ import annotations

import csv
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "data" / "maxima.csv"
TARGET = HERE / "maxima_data.js"


def parse_set(raw: str) -> list[int]:
    contents = raw.strip().removeprefix("{").removesuffix("}").strip()
    if not contents:
        return []
    return [int(value.strip()) for value in contents.split(",")]


def main() -> None:
    maxima: dict[str, dict[str, object]] = {}
    with SOURCE.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            key = f"{row['p']},{row['t']}"
            maxima[key] = {
                "value": int(row["F_max"]),
                "set": parse_set(row["S_max_example"]),
                "proven": row["proven"].strip().lower() == "true",
                "method": row["search_method"],
            }

    payload = json.dumps(maxima, separators=(",", ":"), sort_keys=True)
    TARGET.write_text(
        "// Generated from src/data/maxima.csv by export_maxima_data.py.\n"
        f"window.HARE_SHARE_MAXIMA={payload};\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(maxima)} maxima to {TARGET}")


if __name__ == "__main__":
    main()
