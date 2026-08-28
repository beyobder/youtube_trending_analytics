"""
config.py
---------
Central configuration for the Session 1 pipeline: country partition list,
file system paths, and shared constants. Every other script imports from here
so the partition key and folder layout only need to be changed in one place.
"""

import os

# ---------------------------------------------------------------------------
# Partition key values (one CSV + one JSON per country -> 10 partitions)
# ---------------------------------------------------------------------------
COUNTRIES = ["CA", "DE", "FR", "GB", "IN", "JP", "KR", "MX", "RU", "US"]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def csv_path(country: str) -> str:
    """Path to a country's TrendingRecord CSV, e.g. data/CAvideos.csv"""
    return os.path.join(DATA_DIR, f"{country}videos.csv")


def category_json_path(country: str) -> str:
    """Path to a country's Category lookup JSON, e.g. data/CA_category_id.json"""
    return os.path.join(DATA_DIR, f"{country}_category_id.json")


# ---------------------------------------------------------------------------
# Output artifact paths (match Part 13 "Repository Evidence" naming)
# ---------------------------------------------------------------------------
PROFILE_OUTPUT_TXT = os.path.join(OUTPUT_DIR, "profile_output.txt")
BENCHMARK_OUTPUT_TXT = os.path.join(OUTPUT_DIR, "benchmark_output.txt")
VALIDATION_OUTPUT_TXT = os.path.join(OUTPUT_DIR, "validation_output.txt")
SKEW_OUTPUT_TXT = os.path.join(OUTPUT_DIR, "skew_analysis.txt")
FINAL_AGGREGATE_CSV = os.path.join(OUTPUT_DIR, "final_aggregate.csv")

# Columns expected in every TrendingRecord CSV (16 columns per Part 3)
TRENDING_RECORD_COLUMNS = [
    "video_id", "trending_date", "title", "channel_title", "category_id",
    "publish_time", "tags", "views", "likes", "dislikes", "comment_count",
    "thumbnail_link", "comments_disabled", "ratings_disabled",
    "video_error_or_removed", "description",
]

# Pool sizes benchmarked in Part 8
POOL_SIZES = [2, 4, 8]

# Number of repeated timed runs per setting (Part 6/8 "repeated runs")
BENCHMARK_REPEATS = 3
