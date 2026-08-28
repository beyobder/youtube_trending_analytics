"""
load_and_join.py
-----------------
Core per-partition workload (Part 4/5 of the submission document):
  1. Load a country's Category JSON -> {category_id: title} dict.
  2. Load that country's TrendingRecord CSV.
  3. Map category_id -> category_title via a hash-lookup join.
  4. Tag every row with country_code (the partition key, from the filename).
  5. Group by (country_code, category_title) and aggregate
     sum(views), sum(likes), count(rows).

This module has no side effects at import time and is picklable, so the same
`load_and_join` function is reused unchanged by both the sequential baseline
(benchmark.py::run_sequential) and the multiprocessing pool workers
(benchmark.py::run_parallel) -- exactly as described in Part 6/7.
"""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import csv_path, category_json_path  # noqa: E402


def load_category_map(country: str) -> dict:
    """Load {country}_category_id.json -> {int(category_id): title}."""
    with open(category_json_path(country), "r", encoding="utf-8") as f:
        payload = json.load(f)
    return {int(item["id"]): item["snippet"]["title"] for item in payload["items"]}


def load_and_join(country: str) -> pd.DataFrame:
    """
    Single-partition workload for one country.

    Returns a DataFrame with columns:
        country_code, category_title, total_views, total_likes, video_rows
    """
    df = pd.read_csv(csv_path(country), encoding="latin1")
    rows_before = len(df)

    cat_map = load_category_map(country)
    df["category_title"] = df["category_id"].map(cat_map).fillna("Unknown")
    df["country_code"] = country

    rows_after = len(df)
    assert rows_before == rows_after, (
        f"{country}: row count changed during join "
        f"({rows_before} -> {rows_after}); category_id -> title must be "
        f"single-valued for this invariant to hold (see Part 4)."
    )

    grouped = (
        df.groupby(["country_code", "category_title"])
        .agg(
            total_views=("views", "sum"),
            total_likes=("likes", "sum"),
            video_rows=("video_id", "count"),
        )
        .reset_index()
    )
    return grouped


def load_and_join_with_counts(country: str):
    """Same as load_and_join, but also returns (rows_before, rows_after) for
    the Part 9 correctness validation table."""
    df = pd.read_csv(csv_path(country), encoding="latin1")
    rows_before = len(df)

    cat_map = load_category_map(country)
    df["category_title"] = df["category_id"].map(cat_map).fillna("Unknown")
    df["country_code"] = country
    rows_after = len(df)

    grouped = (
        df.groupby(["country_code", "category_title"])
        .agg(
            total_views=("views", "sum"),
            total_likes=("likes", "sum"),
            video_rows=("video_id", "count"),
        )
        .reset_index()
    )
    return grouped, rows_before, rows_after
