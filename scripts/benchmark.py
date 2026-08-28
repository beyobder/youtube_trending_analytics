"""
benchmark.py
------------
Implements and times:
  - run_sequential(): Part 6 sequential baseline (plain for-loop, 1 process)
  - run_parallel(n_workers): Part 7 parallel implementation
      (multiprocessing.Pool, bounded by `processes=n_workers`)

Both call the identical `load_and_join` function from load_and_join.py, so
any difference in results between the two can only come from parallel
execution itself, not from different logic -- this is what makes the Part 9
correctness check meaningful.

Usage:
    python benchmark.py                  # sequential + pool sizes 2,4,8
    python benchmark.py --pool-sizes 2 4
    python benchmark.py --repeats 5
"""

import argparse
import os
import statistics
import sys
import time
from multiprocessing import Pool

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (COUNTRIES, POOL_SIZES, BENCHMARK_REPEATS,  # noqa: E402
                     BENCHMARK_OUTPUT_TXT, FINAL_AGGREGATE_CSV)
from load_and_join import load_and_join  # noqa: E402


def _worker(country):
    """Top-level (picklable) function so multiprocessing.Pool can ship it to
    worker processes -- must stay a module-level function, not a lambda or
    closure."""
    return load_and_join(country)


def combine(parts):
    """Union all per-country partitions, then re-aggregate in case the same
    (country_code, category_title) pair ever needs merging across partitions
    (it doesn't here, since country_code is the partition key -- kept for
    correctness/generality)."""
    combined = pd.concat(parts, ignore_index=True)
    return (
        combined.groupby(["country_code", "category_title"])[
            ["total_views", "total_likes", "video_rows"]
        ]
        .sum()
        .reset_index()
    )


def run_sequential() -> pd.DataFrame:
    """Part 6: plain for-loop over all country partitions, one process."""
    parts = [load_and_join(c) for c in COUNTRIES]
    return combine(parts)


def run_parallel(n_workers: int) -> pd.DataFrame:
    """Part 7: multiprocessing.Pool bounded to n_workers concurrent processes."""
    with Pool(processes=n_workers) as pool:
        parts = pool.map(_worker, COUNTRIES)
    return combine(parts)


def timed_runs(fn, repeats):
    """Run `fn()` `repeats` times, return (times_list, median_time, last_result)."""
    times = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        times.append(time.perf_counter() - start)
    return times, statistics.median(times), result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool-sizes", type=int, nargs="+", default=POOL_SIZES,
                         help=f"Pool sizes to benchmark (default: {POOL_SIZES})")
    parser.add_argument("--repeats", type=int, default=BENCHMARK_REPEATS,
                         help=f"Timed repeats per setting (default: {BENCHMARK_REPEATS})")
    args = parser.parse_args()

    report_lines = []

    def log(msg=""):
        print(msg)
        report_lines.append(msg)

    log("=== Sequential baseline ===")
    seq_times, seq_median, seq_result = timed_runs(run_sequential, args.repeats)
    log(f"times: {[round(t, 3) for t in seq_times]}")
    log(f"median: {round(seq_median, 3)}")
    log(f"result rows/groups: {len(seq_result)}")
    log("")

    parallel_results = {}
    parallel_medians = {}
    for n in args.pool_sizes:
        log(f"=== Parallel, processes={n} ===")
        times, median, result = timed_runs(lambda n=n: run_parallel(n), args.repeats)
        parallel_results[n] = result
        parallel_medians[n] = median
        log(f"times: {[round(t, 3) for t in times]}")
        log(f"median: {round(median, 3)}")
        log(f"result rows/groups: {len(result)}")
        log("")

    # Summary table (Part 8) -- reuses the medians/results already computed above
    log("=== Summary (execution time in seconds) ===")
    log(f"{'Run':<28}{'Time (s)':<12}{'Rows/groups':<14}")
    log(f"{'Sequential baseline':<28}{seq_median:<12.3f}{len(seq_result):<14}")
    for n in args.pool_sizes:
        result = parallel_results[n]
        # times list for this n was captured in the loop above via closure;
        # recompute the label/median pairing from parallel_medians dict instead
        label = f"Parallel (processes={n})"
        log(f"{label:<28}{parallel_medians[n]:<12.3f}{len(result):<14}")

    with open(BENCHMARK_OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print(f"\nSaved raw benchmark output to {BENCHMARK_OUTPUT_TXT}")

    # Persist the final aggregate (use the sequential result as the
    # canonical output; Part 9 confirms it is identical to every parallel run)
    seq_result_sorted = seq_result.sort_values(
        ["country_code", "category_title"]
    ).reset_index(drop=True)
    seq_result_sorted.to_csv(FINAL_AGGREGATE_CSV, index=False)
    print(f"Saved final aggregate to {FINAL_AGGREGATE_CSV} "
          f"({len(seq_result_sorted)} rows)")

    return seq_result, parallel_results


if __name__ == "__main__":
    main()
