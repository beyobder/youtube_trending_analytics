"""
generate_sample_data.py
------------------------
Creates a synthetic stand-in for the Kaggle "Trending YouTube Video
Statistics" dataset (10 per-country CSVs + 10 per-country category JSONs)
so the whole pipeline can be run immediately, without first downloading the
~514 MiB real archive from Kaggle.

The generated files follow the exact schema described in the submission
document (Part 3 file inventory / Part 5 workload), including:
  - 16 TrendingRecord columns per CSV
  - a category_id -> category JSON foreign key per country
  - deliberately UNEVEN row counts per country (mirrors the real skew
    documented in Part 10, e.g. JP much smaller than US/CA)
  - a few embedded newlines inside the description field, reproducing the
    wc -l vs. pandas row-count discrepancy noted in Part 2

Usage:
    python generate_sample_data.py                 # default ~40k rows/country
    python generate_sample_data.py --rows 4000      # smaller, faster demo run
    python generate_sample_data.py --seed 7
"""

import argparse
import json
import os
import random
import string
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import COUNTRIES, csv_path, category_json_path, DATA_DIR  # noqa: E402

CATEGORY_TITLES = [
    "Film & Animation", "Autos & Vehicles", "Music", "Pets & Animals",
    "Sports", "Travel & Events", "Gaming", "People & Blogs", "Comedy",
    "Entertainment", "News & Politics", "Howto & Style", "Education",
    "Science & Technology", "Nonprofits & Activism",
]

# Relative popularity weights so Music / Entertainment dominate total_views,
# matching the real skew described in Part 10 of the submission document.
CATEGORY_VIEW_WEIGHTS = {
    "Music": 12.0, "Entertainment": 11.0, "Comedy": 4.0, "Sports": 3.5,
    "Gaming": 3.0, "People & Blogs": 2.0, "Film & Animation": 1.5,
    "News & Politics": 1.2, "Howto & Style": 1.0, "Science & Technology": 1.0,
    "Education": 0.8, "Travel & Events": 0.6, "Autos & Vehicles": 0.5,
    "Pets & Animals": 0.5, "Nonprofits & Activism": 0.3,
}

# Uneven row counts per country -> reproduces the partition skew documented
# in Part 10 (JP the clear outlier, US/CA the largest).
COUNTRY_ROW_SHARE = {
    "US": 1.00, "CA": 1.00, "DE": 1.00, "RU": 1.00, "FR": 1.00,
    "MX": 0.99, "GB": 0.95, "IN": 0.91, "KR": 0.85, "JP": 0.50,
}


def _random_id(rng, length=11):
    alphabet = string.ascii_letters + string.digits + "-_"
    return "".join(rng.choice(list(alphabet)) for _ in range(length))


def _random_title(rng, category_title):
    templates = [
        "Official {cat} Highlights",
        "Top 10 {cat} Moments This Week",
        "Why This {cat} Video Went Viral",
        "{cat} Compilation 2024",
        "Behind the Scenes: {cat}",
        "Reacting to {cat} Trends",
    ]
    return rng.choice(templates).format(cat=category_title)


def write_category_json(country, rng):
    """Write a {country}_category_id.json lookup file (Part 3 'Lookup' role)."""
    n_categories = rng.randint(17, 32)
    titles = rng.sample(CATEGORY_TITLES * 3, min(n_categories, len(CATEGORY_TITLES) * 3))
    items = []
    for i, title in enumerate(titles[:n_categories], start=1):
        items.append({
            "kind": "youtube#videoCategory",
            "etag": _random_id(rng, 20),
            "id": str(i),
            "snippet": {
                "channelId": "UCBR8-60-B28hp2BmDPdntcQ",
                "title": title,
                "assignable": True,
            },
        })
    payload = {
        "kind": "youtube#videoCategoryListResponse",
        "etag": _random_id(rng, 20),
        "items": items,
    }
    with open(category_json_path(country), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return {int(item["id"]): item["snippet"]["title"] for item in items}


def write_trending_csv(country, category_map, base_rows, rng, np_rng):
    """Write a {country}videos.csv TrendingRecord file (Part 3 'Event' role)."""
    n_rows = int(base_rows * COUNTRY_ROW_SHARE.get(country, 1.0))
    category_ids = list(category_map.keys())
    category_titles = [category_map[c] for c in category_ids]

    weights = np.array([
        CATEGORY_VIEW_WEIGHTS.get(t, 1.0) for t in category_titles
    ], dtype=float)
    weights = weights / weights.sum()

    chosen_idx = np_rng.choice(len(category_ids), size=n_rows, p=weights)
    chosen_category_ids = [category_ids[i] for i in chosen_idx]
    chosen_titles = [category_titles[i] for i in chosen_idx]

    start_date = datetime(2024, 1, 1)
    rows = []
    for i in range(n_rows):
        cat_id = chosen_category_ids[i]
        cat_title = chosen_titles[i]
        weight = CATEGORY_VIEW_WEIGHTS.get(cat_title, 1.0)

        views = int(np_rng.lognormal(mean=9 + 0.15 * weight, sigma=1.4))
        likes = int(views * np_rng.uniform(0.01, 0.08))
        dislikes = int(views * np_rng.uniform(0.0005, 0.01))
        comments = int(views * np_rng.uniform(0.0005, 0.02))

        publish_dt = start_date + timedelta(
            days=int(np_rng.uniform(0, 400)), hours=int(np_rng.uniform(0, 23))
        )
        trending_dt = publish_dt + timedelta(days=int(np_rng.uniform(0, 5)))

        # ~0.3% of rows get an embedded newline in description, reproducing
        # the wc -l over-count vs. pandas discrepancy noted in Part 2.
        description = f"Auto-generated sample description for {cat_title} video."
        if rng.random() < 0.003:
            description += "\nSecond line inside a quoted CSV field."

        # ~0.3% of rows have a null description (nulls noted in Part 3 profiling)
        if rng.random() < 0.003:
            description = ""

        rows.append({
            "video_id": _random_id(rng),
            "trending_date": trending_dt.strftime("%y.%d.%m"),
            "title": _random_title(rng, cat_title),
            "channel_title": f"Channel_{rng.randint(1, 5000)}",
            "category_id": cat_id,
            "publish_time": publish_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "tags": "|".join(rng.sample(["music", "live", "official", "2024",
                                          "trending", "vlog", "review"], 3)),
            "views": views,
            "likes": likes,
            "dislikes": dislikes,
            "comment_count": comments,
            "thumbnail_link": f"https://i.ytimg.com/vi/{_random_id(rng)}/default.jpg",
            "comments_disabled": rng.random() < 0.02,
            "ratings_disabled": rng.random() < 0.02,
            "video_error_or_removed": rng.random() < 0.01,
            "description": description,
        })

    df = pd.DataFrame(rows)
    df.to_csv(csv_path(country), index=False, encoding="utf-8")
    return len(df)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=40000,
                         help="Base row count per country before skew weighting "
                              "(default: 40000, matching the real dataset scale)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    np_rng = np.random.default_rng(args.seed)

    print(f"Generating synthetic dataset into: {DATA_DIR}")
    total = 0
    for country in COUNTRIES:
        category_map = write_category_json(country, rng)
        n = write_trending_csv(country, category_map, args.rows, rng, np_rng)
        total += n
        print(f"  {country}: {n:>7,} rows  |  {len(category_map)} categories")

    print(f"\nDone. Total rows across all countries: {total:,}")
    print("These files match the schema of the real Kaggle dataset described "
          "in the submission document (Part 3), so you can drop the real "
          "CAvideos.csv / CA_category_id.json etc. into data/ to replace them "
          "at any time.")


if __name__ == "__main__":
    main()
