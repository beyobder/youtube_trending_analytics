# GUI Tutorial — YouTube Trending Analytics Console

This walks through exactly what to type/click in `gui.py` to see each kind
of output. No real dataset is required — the GUI can generate a synthetic
one for you with one click.

```bash
cd youtube_trending_analytics
pip install -r requirements.txt
python gui.py
```

---

## 1. The settings bar (top of the window)

These four fields control every stage. Set them once before you start
running things — you can change them between runs too.

| Field | What it does | Try |
|---|---|---|
| **rows/country** | How many synthetic rows to generate per country (only matters for the *Generate sample data* stage) | `4000` for a normal run, `500`–`1000` for a fast demo |
| **pool sizes** | Space-separated list of `multiprocessing.Pool` sizes to benchmark | `2 4 8` (default), or just `4` to test one size |
| **repeats** | How many timed repetitions per run (median is reported) | `3` (default), raise to `5`+ for steadier timings |
| **force regenerate data** | Checkbox — if checked, *Generate sample data* always overwrites `data/`, even if files are already there | Leave unchecked unless you changed `rows/country` and want fresh data |

Changing rows/pool sizes/repeats does **not** re-run anything by itself —
it only changes what the *next* stage you click will use.

---

## 2. First run — the fastest way to see everything

1. Leave the settings at their defaults (or set **rows/country** to `1000`
   for a quicker first look).
2. Go to the **Pipeline** tab.
3. Click **Run everything**.
4. The window jumps to the **Console** tab automatically — you'll see the
   real script output streaming in live (this is `generate_sample_data.py`,
   then `profile_data.py`, `benchmark.py`, `validate.py`, `skew_analysis.py`
   running in order).
5. When it finishes, click back to **Pipeline**. The four stat cards, the
   stage table, and the artifacts table are now populated. Every other tab
   is populated too.

That's it — one button gets you a fully populated GUI.

---

## 3. Running one stage at a time (to see how each output changes)

Instead of **Run everything**, use the individual buttons in **Run a
stage**. Each one only affects certain tabs:

| Button you click | Script run | What appears / updates |
|---|---|---|
| **Generate sample data** | `generate_sample_data.py` | Creates the 20 files in `data/`. Nothing in `output/` changes yet — no tabs populate from this alone. |
| **Profile files** | `profile_data.py` | **Files & eligibility** tab fills in (per-country row counts, `wc -l` vs. pandas discrepancy, columns, nulls). Also updates the "rows across all files" stat card once you refresh. |
| **Baseline + parallel benchmark** | `benchmark.py` | **Baseline vs parallel** tab fills in (timing table + bar chart). Also writes `output/final_aggregate.csv`, so the **Join & partition key** tab's preview table fills in too. Updates the "groups in the result" and "fastest run measured" stat cards. |
| **Correctness validation** | `validate.py` | **Correctness & output** tab fills in (row-count checks, PASSED/FAILED comparisons). Updates the PASSED/FAILED stat card. |
| **Partition balance & skew** | `skew_analysis.py` | **Partition balance** tab fills in (predicted vs. actual rows per country, top categories by views). |

If a stage needs `data/` and it isn't there yet, the GUI automatically runs
**Generate sample data** first (you'll see both in the Console).

**Tip:** click one stage at a time, then switch to the tab it fills in —
that's the clearest way to see the connection between "what I ran" and
"what output changed."

---

## 4. What to input to see specific things

**"I just want to see the file profiling / row counts."**
→ Click **Profile files**, then open the **Files & eligibility** tab.

**"I want to see how much faster/slower parallel is."**
→ Set **pool sizes** (e.g. `2 4 8`), click **Baseline + parallel
benchmark**, then open **Baseline vs parallel**. The green bar/row is
always the fastest run measured.

**"I want to see the actual joined & aggregated data
(country + category + views/likes)."**
→ Run **Baseline + parallel benchmark** at least once (it writes
`final_aggregate.csv`), then open **Join & partition key** — the table
there is a live preview of that file (first 500 rows).

**"I want proof the parallel results match the sequential baseline."**
→ Click **Correctness validation**, then open **Correctness & output**.
Green **PASSED** = parallel results matched exactly; the top-right label
mirrors the PASSED/FAILED stat card on the Pipeline tab.

**"I want to see which countries/categories are unbalanced."**
→ Click **Partition balance & skew**, then open **Partition balance**. Rows
below the predicted average show in red, above in green.

**"I already ran things in a previous session and just reopened the GUI."**
→ Click **Refresh from output/** on the Pipeline tab — it re-reads
whatever's already in `output/` without re-running anything.

**"I want to try a bigger/smaller dataset."**
→ Change **rows/country**, check **force regenerate data**, click
**Generate sample data**, then re-run whichever stages you care about
(their outputs will reflect the new data size).

**"I want to test just pool size 4, five times, for steadier numbers."**
→ Set **pool sizes** to `4`, **repeats** to `5`, click **Baseline +
parallel benchmark**.

---

## 5. Reading the Pipeline tab stat cards

| Card | Where the number comes from |
|---|---|
| **rows across all files** | Sum of `video_rows` across every row of `final_aggregate.csv` (i.e. total joined rows across all countries) |
| **groups in the result** | Number of rows in `final_aggregate.csv` — one row per `(country_code, category_title)` pair |
| **fastest run measured** | The minimum median time across the sequential baseline and every parallel pool size tested |
| **PASSED / FAILED** | The `OVERALL` line from `validate.py` — PASSED means every parallel run matched the sequential baseline exactly |

These only update after the relevant stage has run (or after **Refresh
from output/** if the files already exist from an earlier run).

---

## 6. Console tab

This is a live terminal view of whatever subprocess is currently running —
useful for reading error tracebacks if a stage shows **failed** in the
stage table. Click **Clear** any time to wipe it; it doesn't affect the
underlying `output/` files.

---

## 7. Troubleshooting

- **A stage shows "failed" in the stage table** — switch to **Console**
  and scroll up to the `$ script.py ...` line for that stage; the Python
  traceback right after it is the actual error.
- **Tabs look empty after opening the GUI** — nothing's been run yet in
  this session. Either click a stage button, or click **Refresh from
  output/** if you know `output/` already has files from a previous run.
- **Buttons are greyed out** — a stage is currently running; wait for it to
  finish (watch the Console tab) and they'll re-enable automatically.
- **Want the real Kaggle dataset instead of synthetic data** — drop the 20
  real files into `data/` yourself (see `data/README.txt`), then just run
  the stages from **Profile files** onward — skip **Generate sample data**.
