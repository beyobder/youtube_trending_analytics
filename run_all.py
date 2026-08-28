#!/usr/bin/env python3
"""
run_all.py
----------
Runs the complete Session 1 pipeline end to end, in the order the submission
document expects:

    1. Generate synthetic sample data (skipped automatically if you've
       already placed the real Kaggle CSV/JSON files in data/)
    2. Profile every file                      -> output/profile_output.txt
    3. Run the sequential baseline + parallel
       benchmarks (processes = 2, 4, 8)         -> output/benchmark_output.txt
                                                 -> output/final_aggregate.csv
    4. Validate parallel results against the
       sequential baseline                      -> output/validation_output.txt
    5. Partition balance / category skew         -> output/skew_analysis.txt

Usage:
    python run_all.py                  # uses/generates default ~40k rows/country
    python run_all.py --rows 4000      # smaller synthetic dataset, runs faster
    python run_all.py --skip-generate  # use whatever is already in data/
"""

import argparse
import os
import sys

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from config import COUNTRIES, csv_path, category_json_path  # noqa: E402


def data_already_present() -> bool:
    return all(
        os.path.exists(csv_path(c)) and os.path.exists(category_json_path(c))
        for c in COUNTRIES
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=40000,
                         help="Base rows/country for synthetic data generation "
                              "(ignored if data/ already has all 20 files, or "
                              "if --skip-generate is passed)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-generate", action="store_true",
                         help="Never (re)generate synthetic data, even if data/ "
                              "is missing files -- fails loudly instead")
    parser.add_argument("--pool-sizes", type=int, nargs="+", default=[2, 4, 8])
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    if data_already_present():
        print("Found all 20 dataset files in data/ -- using them as-is "
              "(delete data/ contents first if you want fresh synthetic data).")
    elif args.skip_generate:
        print("ERROR: data/ is missing one or more of the expected 20 files "
              "and --skip-generate was passed.", file=sys.stderr)
        sys.exit(1)
    else:
        print("No complete dataset found in data/ -- generating synthetic "
              "sample data so the pipeline can run end to end.\n")
        import generate_sample_data
        sys.argv = ["generate_sample_data.py", "--rows", str(args.rows), "--seed", str(args.seed)]
        generate_sample_data.main()

    print("\n" + "=" * 70)
    print("STEP 1/4: Profiling dataset (Part 3)")
    print("=" * 70)
    import profile_data
    profile_data.main()

    print("\n" + "=" * 70)
    print("STEP 2/4: Sequential baseline + parallel benchmarks (Part 6/7/8)")
    print("=" * 70)
    import benchmark
    sys.argv = ["benchmark.py", "--pool-sizes", *map(str, args.pool_sizes),
                "--repeats", str(args.repeats)]
    benchmark.main()

    print("\n" + "=" * 70)
    print("STEP 3/4: Correctness validation (Part 9)")
    print("=" * 70)
    import validate
    sys.argv = ["validate.py", "--pool-sizes", *map(str, args.pool_sizes)]
    validate.main()

    print("\n" + "=" * 70)
    print("STEP 4/4: Partition balance and skew analysis (Part 10)")
    print("=" * 70)
    import skew_analysis
    skew_analysis.main()

    print("\n" + "=" * 70)
    print("Pipeline complete. See the output/ folder for all artifacts:")
    print("  output/profile_output.txt")
    print("  output/benchmark_output.txt")
    print("  output/final_aggregate.csv")
    print("  output/validation_output.txt")
    print("  output/skew_analysis.txt")
    print("=" * 70)


if __name__ == "__main__":
    main()
