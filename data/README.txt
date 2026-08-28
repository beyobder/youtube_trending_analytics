This folder holds the dataset files the pipeline reads.

If you run run_all.py (or the GUI's "Generate sample data" / "Run everything")
and this folder is empty (or incomplete), a synthetic sample dataset matching
the real schema is generated here automatically, so the whole pipeline works
out of the box with no download required.

To use the REAL Kaggle "Trending YouTube Video Statistics" dataset instead:

1. Download and unzip the Kaggle dataset.
2. Copy these 20 files directly into this data/ folder (no subfolders):
     CAvideos.csv   CA_category_id.json
     DEvideos.csv   DE_category_id.json
     FRvideos.csv   FR_category_id.json
     GBvideos.csv   GB_category_id.json
     INvideos.csv   IN_category_id.json
     JPvideos.csv   JP_category_id.json
     KRvideos.csv   KR_category_id.json
     MXvideos.csv   MX_category_id.json
     RUvideos.csv   RU_category_id.json
     USvideos.csv   US_category_id.json
3. Run: python run_all.py --skip-generate  (or just skip "Generate sample
   data" in the GUI and start from "Profile files")

The pipeline will use the real files exactly as-is; no code changes needed.
