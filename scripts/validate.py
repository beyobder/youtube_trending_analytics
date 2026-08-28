"""
validate.py
-----------
Part 9 correctness validation: confirms the parallel implementation produces
the same logical result as the sequential baseline, and that no rows were
gained or lost during the join.

Usage:
    python validate.py                # runs sequential + all default pool sizes
    python validate.py --pool-sizes 2 4 8
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import COUNTRIES, POOL_SIZES, VALIDATION_OUTPUT_TXT  # noqa: E402
from load_and_join import load_and_join_with_counts  # noqa: E402
from benchmark import run_sequential, run_parallel, combine  # noqa: E402


def check_row_counts(lines):
    """Per-country rows_before == rows_after check (Part 9)."""
    lines.append("=== Row-count check before/after join (per country) ===")
    all_ok = True
    for country in COUNTRIES:
        _, before, after = load_and_join_with_counts(country)
        ok = before == after
        all_ok &= ok
        lines.append(f"  {country}: {before:,} -> {after:,}  {'OK' if ok else 'MISMATCH'}")
    lines.append(f"All countries match: {all_ok}")
    lines.append("")
    return all_ok


def compare(seq_result, par_result, label, lines):
    merged = seq_result.merge(
        par_result, on=["country_code", "category_title"], suffixes=("_seq", "_par")
    )
    views_diff = (merged["total_views_seq"] - merged["total_views_par"]).abs().max()
    likes_diff = (merged["total_likes_seq"] - merged["total_likes_par"]).abs().max()
    rows_match = len(seq_result) == len(par_result) == len(merged)

    lines.append(f"=== {label} vs sequential ===")
    lines.append(f"rows match: {rows_match}")
    lines.append(f"max abs diff views: {views_diff}")
    lines.append(f"max abs diff likes: {likes_diff}")
    lines.append("PASSED" if (rows_match and views_diff == 0 and likes_diff == 0) else "FAILED")
    lines.append("")
    return rows_match and views_diff == 0 and likes_diff == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool-sizes", type=int, nargs="+", default=POOL_SIZES)
    args = parser.parse_args()

    lines = []
    row_check_ok = check_row_counts(lines)

    seq_result = run_sequential()
    all_passed = row_check_ok
    for n in args.pool_sizes:
        par_result = run_parallel(n)
        passed = compare(seq_result, par_result, f"Parallel (processes={n})", lines)
        all_passed &= passed

    lines.append(f"OVERALL: {'ALL CHECKS PASSED' if all_passed else 'ONE OR MORE CHECKS FAILED'}")

    output = "\n".join(lines)
    print(output)
    with open(VALIDATION_OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"\nSaved to {VALIDATION_OUTPUT_TXT}")

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
