"""
profile_data.py
----------------
Profiles every TrendingRecord CSV and Category JSON, one pandas pass per
file, and writes the results to output/profile_output.txt. Mirrors the
"Profiling output" table in Part 3 of the submission document, including the
row-count reconciliation between `wc -l` and pandas noted in Part 2.

Usage:
    python profile_data.py
"""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (COUNTRIES, csv_path, category_json_path,  # noqa: E402
                     PROFILE_OUTPUT_TXT)


def wc_l_count(path: str) -> int:
    """Fast newline count -- can OVER-count vs. pandas when a quoted field
    contains an embedded newline (see Part 2 note in the submission doc)."""
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def profile_csv(country: str, lines):
    path = csv_path(country)
    df = pd.read_csv(path, encoding="latin1")

    raw_line_count = wc_l_count(path) - 1  # minus header
    pandas_row_count = len(df)

    lines.append(f"== {os.path.basename(path)} ==")
    lines.append(f"wc -l row estimate : {raw_line_count:,}")
    lines.append(f"pandas row count   : {pandas_row_count:,}  <-- authoritative")
    if raw_line_count != pandas_row_count:
        lines.append(f"  (discrepancy of {raw_line_count - pandas_row_count:,} rows "
                      f"due to embedded newlines inside quoted fields)")
    lines.append(f"columns={len(df.columns)}")
    for col in df.columns:
        nulls = int(df[col].isna().sum())
        lines.append(f"  {col}: dtype={df[col].dtype}, nulls={nulls}")
    lines.append("")
    return pandas_row_count


def profile_json(country: str, lines):
    path = category_json_path(country)
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    items = payload.get("items", [])
    lines.append(f"== {os.path.basename(path)} ==")
    lines.append(f"items={len(items)}")
    lines.append("  # {id, snippet.title, snippet.assignable}")
    lines.append("")
    return len(items)


def main():
    lines = []
    total_rows = 0
    for country in COUNTRIES:
        total_rows += profile_csv(country, lines)
        profile_json(country, lines)

    lines.append(f"TOTAL TrendingRecord rows across all {len(COUNTRIES)} files: {total_rows:,}")

    output = "\n".join(lines)
    with open(PROFILE_OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(output)

    print(output)
    print(f"\nSaved to {PROFILE_OUTPUT_TXT}")
    return total_rows


if __name__ == "__main__":
    main()
