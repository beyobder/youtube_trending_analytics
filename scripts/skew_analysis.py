"""
skew_analysis.py
-----------------
Part 10: Partition balance and skew analysis.
  - Compares each country's actual row count to the naive predicted-equal-split
    average.
  - Reports which category_title dominates total_views within each country.

Usage:
    python skew_analysis.py
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import COUNTRIES, csv_path, SKEW_OUTPUT_TXT  # noqa: E402
from load_and_join import load_and_join  # noqa: E402


def main():
    lines = []

    row_counts = {c: len(pd.read_csv(csv_path(c), encoding="latin1")) for c in COUNTRIES}
    total_rows = sum(row_counts.values())
    predicted_avg = total_rows / len(COUNTRIES)

    lines.append("=== Partition balance (country_code) ===")
    lines.append(f"{'Country':<10}{'Predicted':<14}{'Actual':<12}{'% vs predicted':<16}")
    for country, actual in sorted(row_counts.items(), key=lambda kv: -kv[1]):
        pct = (actual - predicted_avg) / predicted_avg * 100
        lines.append(f"{country:<10}{predicted_avg:<14,.0f}{actual:<12,}{pct:>+14.1f}%")
    lines.append("")

    min_country = min(row_counts, key=row_counts.get)
    max_country = max(row_counts, key=row_counts.get)
    spread = row_counts[max_country] / max(row_counts[min_country], 1)
    lines.append(f"Smallest partition: {min_country} ({row_counts[min_country]:,} rows)")
    lines.append(f"Largest partition:  {max_country} ({row_counts[max_country]:,} rows)")
    lines.append(f"Max/min spread: {spread:.2f}x")
    lines.append("")

    lines.append("=== Category-level skew within each country (top 3 by total_views) ===")
    for country in COUNTRIES:
        grouped = load_and_join(country).sort_values("total_views", ascending=False)
        lines.append(f"  {country}:")
        for _, row in grouped.head(3).iterrows():
            lines.append(
                f"    {row['category_title']:<24} total_views={row['total_views']:,}"
            )
    lines.append("")

    output = "\n".join(lines)
    print(output)
    with open(SKEW_OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"\nSaved to {SKEW_OUTPUT_TXT}")


if __name__ == "__main__":
    main()
