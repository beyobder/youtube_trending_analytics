# Partitioned Category-Engagement Analytics — YouTube Trending Dataset

MIT 261 — Parallel and Distributed Systems | Session 1: Foundations in In-Memory Cluster Compute

This is a complete, ready-to-run implementation of the Session 1 workload
described in the submission document: partition the multi-country YouTube
Trending dataset by `country_code`, join each partition against its category
lookup file, aggregate `sum(views)`, `sum(likes)`, `count(rows)` by
`(country_code, category_title)`, and benchmark a sequential baseline against
a bounded-parallelism `multiprocessing.Pool` implementation.

**No download required to try it out.** If you run it without the real
Kaggle dataset in `data/`, it automatically generates a synthetic dataset
with the exact same schema (10 countries, category JSON lookups, skewed row
counts, embedded-newline edge cases) so every script runs end to end
immediately. Swap in the real Kaggle files at any time — see
[Using the real dataset](#using-the-real-dataset) below.

## What's included

```
youtube_trending_analytics/
├── run_all.py                  # runs the entire pipeline end to end
├── gui.py                      # desktop GUI console (wraps the same scripts)
├── requirements.txt
├── data/                       # dataset files live here (auto-generated if empty)
│   └── README.txt
├── output/                     # all generated reports/results land here
└── scripts/
    ├── config.py                # country list, paths, shared constants
    ├── generate_sample_data.py  # synthetic dataset generator (schema-accurate)
    ├── profile_data.py          # Part 3: per-file profiling
    ├── load_and_join.py         # Part 4/5: core join + aggregation logic
    ├── benchmark.py             # Part 6/7/8: sequential baseline + parallel + timing
    ├── validate.py              # Part 9: correctness validation
    └── skew_analysis.py         # Part 10: partition balance / category skew
```

## Requirements

- Python 3.9+
- pandas, numpy (see `requirements.txt`)

## Setup

```bash
# 1. Unzip this project, then cd into it
cd youtube_trending_analytics

# 2. (Recommended) create a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

## GUI console

A desktop GUI wraps the same scripts unchanged — it launches each one as a
real subprocess, streams its console output live, and parses everything it
writes into `output/` into readable tabs (file profiling, join/partition-key
preview, baseline-vs-parallel timings with a bar chart, correctness results,
and partition balance).

```bash
python gui.py
```

Requires Tk (bundled with most Python installs; on Debian/Ubuntu if it's
missing: `sudo apt-get install python3-tk`). Set rows/pool sizes/repeats in
the header, then use the **Run a stage** buttons or **Run everything**. The
**Console** tab shows the live output of whichever script is running; the
**Pipeline** tab's stage table and artifact list, plus every other tab,
update automatically as each stage finishes (or any time via **Refresh from
output/**).

## Running everything (one command)

```bash
python run_all.py
```

This will, in order:

1. Generate a synthetic ~40,000-rows-per-country dataset into `data/`
   (skipped automatically if `data/` already has all 20 real dataset files)
2. Profile every CSV/JSON file → `output/profile_output.txt`
3. Run the sequential baseline, then the parallel implementation at pool
   sizes 2, 4, and 8 → `output/benchmark_output.txt` and
   `output/final_aggregate.csv`
4. Validate every parallel run against the sequential baseline (row counts,
   summed values) → `output/validation_output.txt`
5. Analyze partition balance and category-level skew →
   `output/skew_analysis.txt`

### Useful flags

```bash
# Faster demo run with a smaller synthetic dataset
python run_all.py --rows 4000

# Use whatever is already in data/ (real dataset) instead of generating
python run_all.py --skip-generate

# Only benchmark specific pool sizes, with more repeats
python run_all.py --pool-sizes 2 4 8 --repeats 5
```

## Running individual steps

Each script can also be run on its own from inside `scripts/` once `data/`
has files in it (generate them first with
`python scripts/generate_sample_data.py` if needed):

```bash
cd scripts

python generate_sample_data.py --rows 40000   # create/refresh sample data
python profile_data.py                        # Part 3 profiling
python benchmark.py --pool-sizes 2 4 8         # Part 6/7/8 baseline + parallel
python validate.py --pool-sizes 2 4 8          # Part 9 correctness check
python skew_analysis.py                        # Part 10 skew analysis
```

## Using the real dataset

1. Download the Kaggle "Trending YouTube Video Statistics" dataset and
   unzip it.
2. Copy all 20 files (10 `{CC}videos.csv` + 10 `{CC}_category_id.json`)
   directly into `data/` — see `data/README.txt` for the exact filenames.
3. Run:
   ```bash
   python run_all.py --skip-generate
   ```

The join/aggregation/benchmark code is identical either way — only the
input files change.

## Output artifacts

| File | Contents |
|---|---|
| `output/profile_output.txt` | Per-file row counts, column dtypes, null counts (Part 3) |
| `output/final_aggregate.csv` | `country_code, category_title, total_views, total_likes, video_rows` — the Session 1 deliverable that Session 2 consumes |
| `output/benchmark_output.txt` | Raw timing runs for the sequential baseline and each pool size (Part 6/8) |
| `output/validation_output.txt` | Row-count and value-diff checks confirming parallel results match the baseline exactly (Part 9) |
| `output/skew_analysis.txt` | Predicted vs. actual rows per partition, plus top categories by views per country (Part 10) |

## Notes on parallel performance

On a single-core machine, `multiprocessing.Pool(processes=N>1)` will
typically run **slower** than the sequential baseline — there's no second
core for a second process to actually run on, so you pay process-spawn and
inter-process pickling overhead with no concurrency benefit. This is
expected behavior, not a bug, and is exactly the result documented in the
submission's Part 8 benchmark table. On a multi-core machine you should see
the parallel runs pull ahead once the per-partition CSV parsing cost
outweighs the process-management overhead.

## Troubleshooting

- **`FileNotFoundError` for a CSV/JSON in `data/`** — run
  `python scripts/generate_sample_data.py` first, or drop in the real
  Kaggle files (see above).
- **Pipeline seems slow** — pass `--rows 4000` (or smaller) to
  `run_all.py`/`generate_sample_data.py` for a quick smoke-test run before
  scaling back up to the full ~40,000 rows/country.
- **`pip install` fails on a restricted machine** — try
  `pip install -r requirements.txt --user`.
