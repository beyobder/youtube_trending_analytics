#!/usr/bin/env python3
"""
gui.py
------
Desktop GUI console for the Session 1 pipeline (YouTube Trending Analytics —
partitioned category/engagement analytics, sequential vs. parallel).

Wraps the existing command-line scripts (generate_sample_data.py,
profile_data.py, benchmark.py, validate.py, skew_analysis.py) exactly as-is
-- nothing about the pipeline logic changes. The GUI runs each stage as a
real subprocess, streams its console output live into a "Console" tab, and
parses the artifacts each stage writes into output/ to populate the other
tabs (file profiling, join/partition key preview, baseline-vs-parallel
timings, correctness results, and partition balance).

Usage:
    python gui.py
"""

import csv
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

# ---------------------------------------------------------------------------
# Paths / constants (mirrors scripts/config.py without importing pandas here)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "scripts")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")

COUNTRIES = ["CA", "DE", "FR", "GB", "IN", "JP", "KR", "MX", "RU", "US"]

PROFILE_TXT = os.path.join(OUTPUT_DIR, "profile_output.txt")
BENCHMARK_TXT = os.path.join(OUTPUT_DIR, "benchmark_output.txt")
VALIDATION_TXT = os.path.join(OUTPUT_DIR, "validation_output.txt")
SKEW_TXT = os.path.join(OUTPUT_DIR, "skew_analysis.txt")
FINAL_CSV = os.path.join(OUTPUT_DIR, "final_aggregate.csv")

# ---------------------------------------------------------------------------
# Colors / fonts -- green / gray / brown scheme (earthy, high-contrast triad)
# ---------------------------------------------------------------------------
FOREST = "#3B5D45"         # deep forest green -- primary / header / sidebar
SAGE = "#8A9083"            # muted sage gray-green -- secondary accents
STONE = "#F3F2ED"           # warm light gray -- app background
TAN = "#D8C3A5"              # warm tan -- banner / light accent
BROWN = "#8C5A34"           # saddle brown -- highlight / "fastest" accent

NAVY = FOREST
NAVY_DARK = "#2A4433"
CARD_BG = "#FAFAF7"
CARD_BORDER = SAGE
ORANGE_BG = "#EFE3D0"
ORANGE_FG = "#6E4523"
GREEN = "#2E7D32"
RED = "#b3261e"
GREY_TXT = "#6B7266"
ROW_ALT = "#F0EEE7"
ACCENT = BROWN
CLOUD = STONE
MUTED_BLUE = SAGE
FONT_FAMILY = "Helvetica"


def read_text(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def human_size(n):
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024:
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1024
    return f"{n:,.1f} TB"


# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------
STAGES = [
    {
        "id": "generate",
        "label": "Generate sample data",
        "script": "generate_sample_data.py",
        "engine": "pandas/numpy",
        "desc": "Synthetic 10-country CSV + category JSON pairs (skipped if data/ is already complete)",
    },
    {
        "id": "profile",
        "label": "Profile files",
        "script": "profile_data.py",
        "engine": "pandas",
        "desc": "Row counts, dtypes, nulls per file; wc -l vs. pandas reconciliation",
    },
    {
        "id": "benchmark",
        "label": "Baseline + parallel benchmark",
        "script": "benchmark.py",
        "engine": "pandas / multiprocessing",
        "desc": "Sequential for-loop baseline vs. bounded multiprocessing.Pool at each pool size",
    },
    {
        "id": "validate",
        "label": "Correctness validation",
        "script": "validate.py",
        "engine": "pandas / multiprocessing",
        "desc": "Confirms every parallel run matches the sequential baseline exactly",
    },
    {
        "id": "skew",
        "label": "Partition balance & skew",
        "script": "skew_analysis.py",
        "engine": "pandas",
        "desc": "Predicted-equal-split vs. actual rows per country; top categories by views",
    },
]

ARTIFACTS = [
    ("profile_output.txt", "profile_data.py", PROFILE_TXT),
    ("benchmark_output.txt", "benchmark.py", BENCHMARK_TXT),
    ("final_aggregate.csv", "benchmark.py", FINAL_CSV),
    ("validation_output.txt", "validate.py", VALIDATION_TXT),
    ("skew_analysis.txt", "skew_analysis.py", SKEW_TXT),
]


class PipelineGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Trending Analytics — Parallel Compute Console")
        self.root.geometry("1480x900")
        self.root.minsize(1220, 720)

        self.log_queue = queue.Queue()
        self.running = False
        self.stage_status = {s["id"]: "not run" for s in STAGES}
        self.stage_headline = {s["id"]: "" for s in STAGES}
        self.stage_row = {}

        self._build_style()
        self._build_header()
        self.body = tk.Frame(self.root, bg=CLOUD)
        self.body.pack(fill="both", expand=True)
        self._build_sidebar(self.body)
        self._build_notebook(self.body)
        self._build_statusbar()

        self.refresh_all()
        self.root.after(100, self._poll_log_queue)

    # ------------------------------------------------------------------
    # Style
    # ------------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.root.configure(bg=CLOUD)

        # Vertical tab strip (west side) for originality vs. the top-tab reference layout.
        # Fixed width + left anchor keeps every tab the same size regardless of label length.
        style.configure("TNotebook", background=CLOUD, borderwidth=0, tabposition="wn")
        style.configure(
            "TNotebook.Tab",
            padding=(14, 10),
            font=(FONT_FAMILY, 10),
            background=SAGE,
            foreground="white",
            width=21,
            anchor="w",
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", "#ffffff")],
            foreground=[("selected", NAVY)],
            font=[("selected", (FONT_FAMILY, 10, "bold"))],
        )

        style.configure("Card.TFrame", background=CARD_BG, relief="flat")
        style.configure("White.TFrame", background="#ffffff")
        style.configure("Navy.TFrame", background=NAVY)
        style.configure("Sidebar.TFrame", background=NAVY)

        style.configure(
            "CardNum.TLabel", background=CARD_BG, foreground=NAVY_DARK,
            font=(FONT_FAMILY, 22, "bold"),
        )
        style.configure(
            "CardCaption.TLabel", background=CARD_BG, foreground=GREY_TXT,
            font=(FONT_FAMILY, 9),
        )
        style.configure(
            "CardNumGreen.TLabel", background=CARD_BG, foreground=GREEN,
            font=(FONT_FAMILY, 22, "bold"),
        )
        style.configure(
            "CardNumRed.TLabel", background=CARD_BG, foreground=RED,
            font=(FONT_FAMILY, 22, "bold"),
        )

        style.configure("Section.TLabel", background="#ffffff", foreground=NAVY_DARK,
                         font=(FONT_FAMILY, 11, "bold"))
        style.configure("Body.TLabel", background="#ffffff", foreground="#2b2f36",
                         font=(FONT_FAMILY, 9))
        style.configure("Muted.TLabel", background="#ffffff", foreground=GREY_TXT,
                         font=(FONT_FAMILY, 9))

        style.configure("Stage.TButton", font=(FONT_FAMILY, 9), padding=(10, 8))
        style.configure("Run.TButton", font=(FONT_FAMILY, 10, "bold"), padding=(14, 9))
        style.map("Run.TButton", background=[("!disabled", BROWN)],
                  foreground=[("!disabled", "white")])

        style.configure(
            "Treeview", font=(FONT_FAMILY, 9), rowheight=24, background="#ffffff",
            fieldbackground="#ffffff",
        )
        style.configure(
            "Treeview.Heading", font=(FONT_FAMILY, 9, "bold"), background=NAVY,
            foreground="white",
        )
        style.map("Treeview.Heading", background=[("active", NAVY)])

    # ------------------------------------------------------------------
    # Header -- title/subtitle only; run controls now live in the sidebar
    # ------------------------------------------------------------------
    def _build_header(self):
        header = tk.Frame(self.root, bg=NAVY)
        header.pack(fill="x", side="top")

        inner = tk.Frame(header, bg=NAVY)
        inner.pack(fill="x", padx=20, pady=(14, 12))

        tk.Label(
            inner, text="YouTube Trending Analytics — Parallel Compute Console",
            bg=NAVY, fg="white", font=(FONT_FAMILY, 17, "bold"),
        ).pack(anchor="w")

        self.subtitle_var = tk.StringVar()
        tk.Label(
            inner, textvariable=self.subtitle_var, bg=NAVY, fg=CLOUD,
            font=(FONT_FAMILY, 9),
        ).pack(anchor="w", pady=(2, 0))

    def _update_subtitle(self):
        self.subtitle_var.set(
            f"MIT 261 Parallel and Distributed Systems  ·  partition key: country_code "
            f"({len(COUNTRIES)} partitions)  ·  bounded parallelism via multiprocessing.Pool "
            f"·  pool sizes ({self.poolsizes_var.get().strip()})  ·  rows/country "
            f"({self.rows_var.get().strip()})"
        )

    # ------------------------------------------------------------------
    # Sidebar -- run controls, persistent across every tab (moved out of
    # the header so they're reachable no matter which tab is open)
    # ------------------------------------------------------------------
    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=NAVY, width=225)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        def heading(text, pady=(18, 8)):
            tk.Label(sidebar, text=text, bg=NAVY, fg=CLOUD, font=(FONT_FAMILY, 10, "bold"),
                      anchor="w").pack(fill="x", padx=16, pady=pady)

        def field_label(text):
            tk.Label(sidebar, text=text, bg=NAVY, fg=MUTED_BLUE, font=(FONT_FAMILY, 8),
                      anchor="w").pack(fill="x", padx=16, pady=(6, 1))

        heading("Run settings", pady=(18, 6))

        field_label("rows / country")
        self.rows_var = tk.StringVar(value="4000")
        tk.Entry(sidebar, textvariable=self.rows_var).pack(fill="x", padx=16)

        field_label("pool sizes (space-separated)")
        self.poolsizes_var = tk.StringVar(value="2 4 8")
        tk.Entry(sidebar, textvariable=self.poolsizes_var).pack(fill="x", padx=16)

        field_label("repeats")
        self.repeats_var = tk.StringVar(value="3")
        tk.Entry(sidebar, textvariable=self.repeats_var).pack(fill="x", padx=16)

        self.force_regen_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            sidebar, text="force regenerate data", variable=self.force_regen_var,
            bg=NAVY, fg=CLOUD, selectcolor=NAVY_DARK, activebackground=NAVY,
            activeforeground="white", font=(FONT_FAMILY, 8), anchor="w",
        ).pack(fill="x", padx=14, pady=(10, 0))

        for var in (self.rows_var, self.poolsizes_var, self.repeats_var):
            var.trace_add("write", lambda *_: self._update_subtitle())
        self._update_subtitle()

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=16, pady=16)

        heading("Run a stage", pady=(0, 8))

        self.stage_buttons = {}
        for s in STAGES:
            b = ttk.Button(sidebar, text=s["label"], style="Stage.TButton",
                            command=lambda sid=s["id"]: self.run_single_stage(sid))
            b.pack(fill="x", padx=16, pady=3)
            self.stage_buttons[s["id"]] = b

        ttk.Separator(sidebar, orient="horizontal").pack(fill="x", padx=16, pady=16)

        self.run_all_btn = ttk.Button(sidebar, text="Run everything", style="Run.TButton",
                                       command=self.run_everything)
        self.run_all_btn.pack(fill="x", padx=16, pady=(0, 6))

        self.refresh_btn = ttk.Button(sidebar, text="Refresh from output/",
                                       style="Stage.TButton", command=self.refresh_all)
        self.refresh_btn.pack(fill="x", padx=16)

    # ------------------------------------------------------------------
    # Notebook / tabs -- vertical strip (tabposition "wn") beside the sidebar
    # ------------------------------------------------------------------
    def _build_notebook(self, parent):
        self.nb = ttk.Notebook(parent)
        self.nb.pack(side="left", fill="both", expand=True)

        self.tab_pipeline = ttk.Frame(self.nb, style="White.TFrame")
        self.tab_files = ttk.Frame(self.nb, style="White.TFrame")
        self.tab_join = ttk.Frame(self.nb, style="White.TFrame")
        self.tab_bench = ttk.Frame(self.nb, style="White.TFrame")
        self.tab_correct = ttk.Frame(self.nb, style="White.TFrame")
        self.tab_balance = ttk.Frame(self.nb, style="White.TFrame")
        self.tab_console = ttk.Frame(self.nb, style="White.TFrame")

        self.nb.add(self.tab_pipeline, text="Pipeline")
        self.nb.add(self.tab_files, text="Files & eligibility")
        self.nb.add(self.tab_join, text="Join & partition key")
        self.nb.add(self.tab_bench, text="Baseline vs parallel")
        self.nb.add(self.tab_correct, text="Correctness & output")
        self.nb.add(self.tab_balance, text="Partition balance")
        self.nb.add(self.tab_console, text="Console")

        self._build_tab_pipeline()
        self._build_tab_files()
        self._build_tab_join()
        self._build_tab_bench()
        self._build_tab_correct()
        self._build_tab_balance()
        self._build_tab_console()

    # -- Pipeline tab ---------------------------------------------------
    def _build_tab_pipeline(self):
        root = self.tab_pipeline

        # artifacts table (moved to the top of the tab)
        tk.Label(root, text="Artifacts in output/", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 11, "bold")).pack(anchor="w", padx=20, pady=(16, 4))

        art_frame = tk.Frame(root, bg="#ffffff")
        art_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        acols = ("artifact", "writtenby", "status", "size", "modified")
        self.art_tree = ttk.Treeview(art_frame, columns=acols, show="headings", height=5)
        self.art_tree.heading("artifact", text="Artifact")
        self.art_tree.heading("writtenby", text="Written by")
        self.art_tree.heading("status", text="Status")
        self.art_tree.heading("size", text="Size")
        self.art_tree.heading("modified", text="Last written")
        self.art_tree.column("artifact", width=170, anchor="w")
        self.art_tree.column("writtenby", width=140, anchor="w")
        self.art_tree.column("status", width=90, anchor="w")
        self.art_tree.column("size", width=80, anchor="e")
        self.art_tree.column("modified", width=170, anchor="w")
        art_xsb = ttk.Scrollbar(art_frame, orient="horizontal", command=self.art_tree.xview)
        self.art_tree.configure(xscrollcommand=art_xsb.set)
        self.art_tree.pack(fill="both", expand=True, side="top")
        art_xsb.pack(fill="x", side="bottom")
        self.art_tree.tag_configure("written", foreground=GREEN)
        self.art_tree.tag_configure("missing", foreground=GREY_TXT)

        # stage status table
        tk.Label(root, text="Stage status", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 11, "bold")).pack(anchor="w", padx=20, pady=(4, 4))

        table_frame = tk.Frame(root, bg="#ffffff")
        table_frame.pack(fill="both", expand=False, padx=20, pady=(0, 8))

        cols = ("stage", "script", "status", "headline")
        self.stage_tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=5)
        self.stage_tree.heading("stage", text="Stage")
        self.stage_tree.heading("script", text="Script")
        self.stage_tree.heading("status", text="Status")
        self.stage_tree.heading("headline", text="Headline result")
        self.stage_tree.column("stage", width=180, anchor="w")
        self.stage_tree.column("script", width=140, anchor="w")
        self.stage_tree.column("status", width=90, anchor="w")
        self.stage_tree.column("headline", width=260, anchor="w")
        stage_xsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.stage_tree.xview)
        self.stage_tree.configure(xscrollcommand=stage_xsb.set)
        self.stage_tree.pack(fill="x", side="top")
        stage_xsb.pack(fill="x", side="bottom")

        self.stage_tree.tag_configure("done", foreground=GREEN)
        self.stage_tree.tag_configure("failed", foreground=RED)
        self.stage_tree.tag_configure("running", foreground=ACCENT)
        self.stage_tree.tag_configure("notrun", foreground=GREY_TXT)

        for s in STAGES:
            iid = self.stage_tree.insert(
                "", "end", iid=s["id"],
                values=(s["label"], s["script"], "not run", s["desc"]),
                tags=("notrun",),
            )
            self.stage_row[s["id"]] = iid

        # info banner
        banner = tk.Frame(root, bg=ORANGE_BG)
        banner.pack(fill="x", padx=20, pady=(4, 10))
        tk.Label(
            banner, bg=ORANGE_BG, fg=ORANGE_FG, justify="left", wraplength=1180,
            font=(FONT_FAMILY, 9),
            text=(
                "On a single-core machine, multiprocessing.Pool(processes=N>1) will typically "
                "run slower than the sequential baseline -- there's no second core for a second "
                "process to run on, so you pay process-spawn and pickling overhead with no "
                "concurrency benefit. On a multi-core machine the parallel runs should pull ahead "
                "once per-partition CSV parsing cost outweighs process-management overhead."
            ),
        ).pack(padx=12, pady=8, anchor="w")

        # stat cards -- 2x2 grid at the bottom of the tab
        tk.Label(root, text="Summary", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 11, "bold")).pack(anchor="w", padx=20, pady=(2, 4))

        cards_frame = tk.Frame(root, bg="#ffffff")
        cards_frame.pack(fill="x", padx=20, pady=(0, 16))
        self.card_vars = {}
        self.card_labels = {}
        specs = [
            ("total_rows", "0", "rows across all files"),
            ("groups", "0", "groups in the result"),
            ("fastest", "—", "fastest run measured"),
            ("validation", "NOT RUN", "parallel vs baseline"),
        ]
        for i, (key, default, caption) in enumerate(specs):
            row, col = divmod(i, 2)
            card = tk.Frame(cards_frame, bg=CARD_BG, highlightbackground=CARD_BORDER,
                             highlightthickness=1)
            card.grid(row=row, column=col, sticky="nsew",
                      padx=(0 if col == 0 else 10, 0), pady=(0 if row == 0 else 10, 0))
            cards_frame.grid_columnconfigure(col, weight=1)
            var = tk.StringVar(value=default)
            self.card_vars[key] = var
            lbl = tk.Label(card, textvariable=var, bg=CARD_BG, fg=NAVY_DARK,
                            font=(FONT_FAMILY, 22, "bold"))
            lbl.pack(pady=(14, 2))
            self.card_labels[key] = lbl
            tk.Label(card, text=caption, bg=CARD_BG, fg=GREY_TXT,
                      font=(FONT_FAMILY, 9)).pack(pady=(0, 12))

    # -- Files & eligibility tab -----------------------------------------
    def _build_tab_files(self):
        root = self.tab_files
        tk.Label(root, text="Per-file profiling (Part 3)", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 11, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
        tk.Label(
            root, bg="#ffffff", fg=GREY_TXT, font=(FONT_FAMILY, 9), justify="left",
            wraplength=1200,
            text=("wc -l can OVER-count vs. pandas when a quoted field contains an embedded "
                  "newline. pandas' row count is authoritative for eligibility."),
        ).pack(anchor="w", padx=20, pady=(0, 10))

        frame = tk.Frame(root, bg="#ffffff")
        frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        cols = ("country", "pandas_rows", "wc_estimate", "discrepancy", "columns",
                "total_nulls", "category_items")
        self.files_tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        headers = {
            "country": "Country", "pandas_rows": "pandas rows (authoritative)",
            "wc_estimate": "wc -l estimate", "discrepancy": "Discrepancy",
            "columns": "Columns", "total_nulls": "Total nulls",
            "category_items": "Category items",
        }
        for c in cols:
            self.files_tree.heading(c, text=headers[c])
            self.files_tree.column(c, width=115, anchor="center")
        self.files_tree.column("country", width=70, anchor="w")
        files_xsb = ttk.Scrollbar(frame, orient="horizontal", command=self.files_tree.xview)
        self.files_tree.configure(xscrollcommand=files_xsb.set)
        self.files_tree.pack(fill="both", expand=True, side="top")
        files_xsb.pack(fill="x", side="bottom")

        tk.Label(root, text="Raw profile output", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=20, pady=(6, 4))
        self.files_raw = tk.Text(root, height=10, font=("Courier New", 9), bg=NAVY_DARK,
                                  fg=CLOUD, wrap="none")
        self.files_raw.pack(fill="both", expand=False, padx=20, pady=(0, 16))

    # -- Join & partition key tab ----------------------------------------
    def _build_tab_join(self):
        root = self.tab_join
        tk.Label(root, text="Join & partition key", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 11, "bold")).pack(anchor="w", padx=20, pady=(16, 4))
        explanation = (
            "Partition key: country_code -- derived from each file's name "
            f"({', '.join(COUNTRIES)}), not asserted as a column in the raw CSV.\n"
            "Join: category_id -> category_title via a hash lookup built from that "
            "country's *_category_id.json (unmatched ids fall back to \"Unknown\").\n"
            "Aggregation: group by (country_code, category_title) and compute "
            "sum(views), sum(likes), count(rows)."
        )
        tk.Label(root, text=explanation, bg="#ffffff", fg="#2b2f36", justify="left",
                  font=(FONT_FAMILY, 9), wraplength=1200).pack(anchor="w", padx=20, pady=(0, 10))

        tk.Label(root, text="Preview of output/final_aggregate.csv", bg="#ffffff",
                  fg=NAVY_DARK, font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=20)

        frame = tk.Frame(root, bg="#ffffff")
        frame.pack(fill="both", expand=True, padx=20, pady=(6, 16))
        cols = ("country_code", "category_title", "total_views", "total_likes", "video_rows")
        self.join_tree = ttk.Treeview(frame, columns=cols, show="headings", height=18)
        for c in cols:
            self.join_tree.heading(c, text=c)
            self.join_tree.column(c, width=140, anchor="center" if c != "category_title" else "w")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.join_tree.yview)
        self.join_tree.configure(yscrollcommand=vsb.set)
        self.join_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Baseline vs parallel tab ----------------------------------------
    def _build_tab_bench(self):
        root = self.tab_bench
        tk.Label(root, text="Sequential baseline vs. parallel benchmark", bg="#ffffff",
                  fg=NAVY_DARK, font=(FONT_FAMILY, 11, "bold")).pack(anchor="w", padx=20,
                                                                      pady=(16, 8))

        frame = tk.Frame(root, bg="#ffffff")
        frame.pack(fill="x", padx=20)
        cols = ("run", "time", "rows", "speedup")
        self.bench_tree = ttk.Treeview(frame, columns=cols, show="headings", height=5)
        self.bench_tree.heading("run", text="Run")
        self.bench_tree.heading("time", text="Median time (s)")
        self.bench_tree.heading("rows", text="Rows/groups")
        self.bench_tree.heading("speedup", text="Speedup vs. baseline")
        self.bench_tree.column("run", width=220, anchor="w")
        self.bench_tree.column("time", width=130, anchor="center")
        self.bench_tree.column("rows", width=110, anchor="center")
        self.bench_tree.column("speedup", width=150, anchor="center")
        self.bench_tree.pack(fill="x")
        self.bench_tree.tag_configure("fastest", foreground=GREEN)

        tk.Label(root, text="Relative time (longer bar = slower)", bg="#ffffff",
                  fg=NAVY_DARK, font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=20,
                                                                      pady=(14, 4))
        self.bench_canvas = tk.Canvas(root, height=220, bg="#ffffff", highlightthickness=0)
        self.bench_canvas.pack(fill="x", padx=20, pady=(0, 16))

        tk.Label(root, text="Raw benchmark output", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=20)
        self.bench_raw = tk.Text(root, height=8, font=("Courier New", 9), bg=NAVY_DARK,
                                  fg=CLOUD, wrap="none")
        self.bench_raw.pack(fill="both", expand=True, padx=20, pady=(4, 16))

    # -- Correctness & output tab ----------------------------------------
    def _build_tab_correct(self):
        root = self.tab_correct
        top = tk.Frame(root, bg="#ffffff")
        top.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(top, text="Correctness & output (Part 9)", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 11, "bold")).pack(side="left")
        self.overall_var = tk.StringVar(value="NOT RUN")
        self.overall_lbl = tk.Label(top, textvariable=self.overall_var, bg="#ffffff",
                                     fg=GREY_TXT, font=(FONT_FAMILY, 12, "bold"))
        self.overall_lbl.pack(side="right")

        tk.Label(root, text="Row-count check before/after join (per country)", bg="#ffffff",
                  fg=NAVY_DARK, font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=20,
                                                                      pady=(6, 4))
        frame = tk.Frame(root, bg="#ffffff")
        frame.pack(fill="x", padx=20)
        cols = ("country", "before", "after", "status")
        self.rowcheck_tree = ttk.Treeview(frame, columns=cols, show="headings", height=len(COUNTRIES))
        for c, w in zip(cols, (100, 140, 140, 100)):
            self.rowcheck_tree.heading(c, text=c.capitalize())
            self.rowcheck_tree.column(c, width=w, anchor="center")
        self.rowcheck_tree.pack(fill="x")
        self.rowcheck_tree.tag_configure("ok", foreground=GREEN)
        self.rowcheck_tree.tag_configure("mismatch", foreground=RED)

        tk.Label(root, text="Parallel vs. sequential comparisons", bg="#ffffff",
                  fg=NAVY_DARK, font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=20,
                                                                      pady=(12, 4))
        frame2 = tk.Frame(root, bg="#ffffff")
        frame2.pack(fill="x", padx=20)
        cols2 = ("label", "rows_match", "views_diff", "likes_diff", "result")
        self.cmp_tree = ttk.Treeview(frame2, columns=cols2, show="headings", height=4)
        for c, w, t in zip(cols2, (220, 110, 130, 130, 110),
                            ("Comparison", "Rows match", "Max |views diff|",
                             "Max |likes diff|", "Result")):
            self.cmp_tree.heading(c, text=t)
            self.cmp_tree.column(c, width=w, anchor="center")
        self.cmp_tree.column("label", anchor="w")
        self.cmp_tree.pack(fill="x")
        self.cmp_tree.tag_configure("pass", foreground=GREEN)
        self.cmp_tree.tag_configure("fail", foreground=RED)

        tk.Label(root, text="Raw validation output", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=20, pady=(12, 4))
        self.correct_raw = tk.Text(root, height=8, font=("Courier New", 9), bg=NAVY_DARK,
                                    fg=CLOUD, wrap="none")
        self.correct_raw.pack(fill="both", expand=True, padx=20, pady=(0, 16))

    # -- Partition balance tab -------------------------------------------
    def _build_tab_balance(self):
        root = self.tab_balance
        tk.Label(root, text="Partition balance (country_code)", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 11, "bold")).pack(anchor="w", padx=20, pady=(16, 6))

        frame = tk.Frame(root, bg="#ffffff")
        frame.pack(fill="x", padx=20)
        cols = ("country", "predicted", "actual", "pct")
        self.balance_tree = ttk.Treeview(frame, columns=cols, show="headings",
                                          height=len(COUNTRIES))
        for c, t, w in zip(cols, ("Country", "Predicted (equal split)", "Actual",
                                   "% vs. predicted"), (100, 200, 140, 160)):
            self.balance_tree.heading(c, text=t)
            self.balance_tree.column(c, width=w, anchor="center")
        self.balance_tree.pack(fill="x")
        self.balance_tree.tag_configure("above", foreground=GREEN)
        self.balance_tree.tag_configure("below", foreground=RED)

        self.spread_var = tk.StringVar(value="Run the skew-analysis stage to see spread.")
        tk.Label(root, textvariable=self.spread_var, bg="#ffffff", fg="#2b2f36",
                  font=(FONT_FAMILY, 9, "italic")).pack(anchor="w", padx=20, pady=(8, 12))

        tk.Label(root, text="Top categories by total_views (per country)", bg="#ffffff",
                  fg=NAVY_DARK, font=(FONT_FAMILY, 10, "bold")).pack(anchor="w", padx=20,
                                                                      pady=(0, 4))
        frame2 = tk.Frame(root, bg="#ffffff")
        frame2.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        cols2 = ("country", "rank", "category", "views")
        self.topcat_tree = ttk.Treeview(frame2, columns=cols2, show="headings", height=14)
        for c, t, w in zip(cols2, ("Country", "Rank", "Category", "Total views"),
                            (100, 60, 260, 160)):
            self.topcat_tree.heading(c, text=t)
            self.topcat_tree.column(c, width=w, anchor="center")
        self.topcat_tree.column("category", anchor="w")
        vsb = ttk.Scrollbar(frame2, orient="vertical", command=self.topcat_tree.yview)
        self.topcat_tree.configure(yscrollcommand=vsb.set)
        self.topcat_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # -- Console tab -------------------------------------------------------
    def _build_tab_console(self):
        root = self.tab_console
        top = tk.Frame(root, bg="#ffffff")
        top.pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(top, text="Console", bg="#ffffff", fg=NAVY_DARK,
                  font=(FONT_FAMILY, 11, "bold")).pack(side="left")
        ttk.Button(top, text="Clear", command=self._clear_console).pack(side="right")

        self.console_text = tk.Text(root, bg=NAVY_DARK, fg=CLOUD,
                                     insertbackground=CLOUD,
                                     font=("Courier New", 9), wrap="word")
        self.console_text.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.console_text.configure(state="disabled")

    def _clear_console(self):
        self.console_text.configure(state="normal")
        self.console_text.delete("1.0", "end")
        self.console_text.configure(state="disabled")

    def _log(self, msg):
        self.console_text.configure(state="normal")
        self.console_text.insert("end", msg if msg.endswith("\n") else msg + "\n")
        self.console_text.see("end")
        self.console_text.configure(state="disabled")

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------
    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg="#e7ebf2", height=26)
        bar.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(bar, textvariable=self.status_var, bg="#e7ebf2", fg=GREY_TXT,
                  font=(FONT_FAMILY, 9), anchor="w").pack(side="left", padx=10, pady=3)

    # ------------------------------------------------------------------
    # Running stages
    # ------------------------------------------------------------------
    def _stage_cmd(self, stage_id, settings):
        py = sys.executable
        rows = settings["rows"]
        pool_sizes = settings["pool_sizes"]
        repeats = settings["repeats"]

        if stage_id == "generate":
            return [py, "generate_sample_data.py", "--rows", rows]
        if stage_id == "profile":
            return [py, "profile_data.py"]
        if stage_id == "benchmark":
            return [py, "benchmark.py", "--pool-sizes", *pool_sizes, "--repeats", repeats]
        if stage_id == "validate":
            return [py, "validate.py", "--pool-sizes", *pool_sizes]
        if stage_id == "skew":
            return [py, "skew_analysis.py"]
        raise ValueError(stage_id)

    def _data_present(self):
        for c in COUNTRIES:
            if not os.path.exists(os.path.join(DATA_DIR, f"{c}videos.csv")):
                return False
            if not os.path.exists(os.path.join(DATA_DIR, f"{c}_category_id.json")):
                return False
        return True

    def _set_stage_status(self, stage_id, status, headline=None):
        self.stage_status[stage_id] = status
        if headline is not None:
            self.stage_headline[stage_id] = headline
        tag = {"not run": "notrun", "running…": "running", "done": "done",
               "failed": "failed"}.get(status, "notrun")
        spec = next(s for s in STAGES if s["id"] == stage_id)
        current_headline = self.stage_headline[stage_id] or spec["desc"]
        self.stage_tree.item(self.stage_row[stage_id],
                              values=(spec["label"], spec["script"], status, current_headline),
                              tags=(tag,))

    def _set_buttons_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for b in self.stage_buttons.values():
            b.configure(state=state)
        self.run_all_btn.configure(state=state)
        self.refresh_btn.configure(state=state)

    def run_single_stage(self, stage_id):
        if self.running:
            messagebox.showinfo("Busy", "A stage is already running -- please wait.")
            return
        needs_data = stage_id != "generate"
        plan = []
        if needs_data and not self._data_present() and not self.force_regen_var.get():
            plan.append("generate")
        elif stage_id == "generate" and self.force_regen_var.get():
            pass
        plan.append(stage_id)
        self._launch(plan)

    def run_everything(self):
        if self.running:
            messagebox.showinfo("Busy", "A stage is already running -- please wait.")
            return
        plan = []
        if self.force_regen_var.get() or not self._data_present():
            plan.append("generate")
        plan += ["profile", "benchmark", "validate", "skew"]
        self._launch(plan)

    def _current_settings(self):
        """Snapshot Tk variable values on the main thread -- Tk StringVars must
        not be read from a background thread, so the worker thread receives
        plain Python values instead of touching self.rows_var etc. directly."""
        rows = self.rows_var.get().strip() or "4000"
        pool_sizes = self.poolsizes_var.get().split() or ["2", "4", "8"]
        repeats = self.repeats_var.get().strip() or "3"
        return {"rows": rows, "pool_sizes": pool_sizes, "repeats": repeats}

    def _launch(self, stage_ids):
        self.running = True
        self._set_buttons_enabled(False)
        self.nb.select(self.tab_console)
        settings = self._current_settings()
        t = threading.Thread(target=self._run_stage_sequence, args=(stage_ids, settings),
                              daemon=True)
        t.start()

    def _run_stage_sequence(self, stage_ids, settings):
        for stage_id in stage_ids:
            cmd = self._stage_cmd(stage_id, settings)
            self.log_queue.put(("status", stage_id, "running…", None))
            self.log_queue.put(("log", f"\n$ {os.path.basename(cmd[1])} "
                                        f"{' '.join(cmd[2:])}", None, None))
            ok = self._run_one(stage_id, settings)
            if ok:
                headline = self._headline_for(stage_id)
                self.log_queue.put(("status", stage_id, "done", headline))
            else:
                self.log_queue.put(("status", stage_id, "failed", "See Console tab for the error."))
                self.log_queue.put(("log", f"[stage '{stage_id}' failed -- stopping sequence]", None, None))
                break
        self.log_queue.put(("refresh", None, None, None))
        self.log_queue.put(("done", None, None, None))

    def _run_one(self, stage_id, settings):
        cmd = self._stage_cmd(stage_id, settings)
        try:
            proc = subprocess.Popen(
                cmd, cwd=SCRIPTS_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
            )
        except Exception as e:
            self.log_queue.put(("log", f"[error launching {cmd[1]}: {e}]", None, None))
            return False

        for line in proc.stdout:
            self.log_queue.put(("log", line.rstrip("\n"), None, None))
        proc.wait()
        return proc.returncode == 0

    def _headline_for(self, stage_id):
        try:
            if stage_id == "generate":
                return f"Generated synthetic data for {len(COUNTRIES)} countries in data/"
            if stage_id == "profile":
                text = read_text(PROFILE_TXT) or ""
                m = re.search(r"TOTAL TrendingRecord rows across all \d+ files: ([\d,]+)", text)
                return f"{m.group(1)} total rows profiled across {len(COUNTRIES)} files" if m else "Profiled all files"
            if stage_id == "benchmark":
                rows = self._parse_benchmark_summary()
                if not rows:
                    return "Benchmark complete"
                fastest = min(rows, key=lambda r: r["time"])
                return f"fastest: {fastest['run']} @ {fastest['time']:.3f}s"
            if stage_id == "validate":
                text = read_text(VALIDATION_TXT) or ""
                m = re.search(r"OVERALL: (.+)", text)
                return m.group(1) if m else "Validation complete"
            if stage_id == "skew":
                text = read_text(SKEW_TXT) or ""
                m = re.search(r"Max/min spread: ([\d.]+)x", text)
                return f"partition spread: {m.group(1)}x" if m else "Skew analysis complete"
        except Exception:
            pass
        return "Complete"

    def _poll_log_queue(self):
        try:
            while True:
                kind, a, b, c = self.log_queue.get_nowait()
                if kind == "log":
                    self._log(a)
                elif kind == "status":
                    self._set_stage_status(a, b, c)
                elif kind == "refresh":
                    self.refresh_all()
                elif kind == "done":
                    self.running = False
                    self._set_buttons_enabled(True)
                    self.status_var.set("Ready.")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    # ------------------------------------------------------------------
    # Parsing output/ artifacts into the tabs
    # ------------------------------------------------------------------
    def refresh_all(self):
        self.status_var.set("Refreshing from output/ …")
        self._refresh_artifacts_table()
        self._refresh_files_tab()
        self._refresh_join_tab()
        self._refresh_bench_tab()
        self._refresh_correct_tab()
        self._refresh_balance_tab()
        self._refresh_stat_cards()
        self._refresh_stage_row_headlines()
        self.status_var.set("Ready.")

    def _refresh_stage_row_headlines(self):
        # keep "not run" stages showing their description, but flip to done
        # if the artifact already exists on disk (e.g. from a prior session)
        checks = {
            "generate": self._data_present(),
            "profile": os.path.exists(PROFILE_TXT),
            "benchmark": os.path.exists(BENCHMARK_TXT),
            "validate": os.path.exists(VALIDATION_TXT),
            "skew": os.path.exists(SKEW_TXT),
        }
        for sid, present in checks.items():
            if present and self.stage_status[sid] == "not run":
                self._set_stage_status(sid, "done", self._headline_for(sid))

    def _refresh_artifacts_table(self):
        self.art_tree.delete(*self.art_tree.get_children())
        for name, writer, path in ARTIFACTS:
            if os.path.exists(path):
                st = os.stat(path)
                self.art_tree.insert(
                    "", "end",
                    values=(name, writer, "written", human_size(st.st_size),
                            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))),
                    tags=("written",),
                )
            else:
                self.art_tree.insert(
                    "", "end", values=(name, writer, "not written", "—", "—"),
                    tags=("missing",),
                )

    def _refresh_stat_cards(self):
        # total rows + groups from final_aggregate.csv
        total_rows, groups = 0, 0
        if os.path.exists(FINAL_CSV):
            with open(FINAL_CSV, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    groups += 1
                    try:
                        total_rows += int(row["video_rows"])
                    except (KeyError, ValueError):
                        pass
        self.card_vars["total_rows"].set(f"{total_rows:,}" if total_rows else "0")
        self.card_vars["groups"].set(f"{groups:,}" if groups else "0")

        rows = self._parse_benchmark_summary()
        if rows:
            fastest = min(rows, key=lambda r: r["time"])
            self.card_vars["fastest"].set(f"{fastest['time']:.2f}s")
        else:
            self.card_vars["fastest"].set("—")

        text = read_text(VALIDATION_TXT) or ""
        m = re.search(r"OVERALL: (.+)", text)
        if m:
            passed = "PASSED" in m.group(1)
            self.card_vars["validation"].set("PASSED" if passed else "FAILED")
            self.card_labels["validation"].configure(fg=GREEN if passed else RED)
        else:
            self.card_vars["validation"].set("NOT RUN")
            self.card_labels["validation"].configure(fg=NAVY_DARK)

    # -- Files & eligibility parsing --------------------------------------
    def _refresh_files_tab(self):
        self.files_tree.delete(*self.files_tree.get_children())
        text = read_text(PROFILE_TXT)
        self.files_raw.delete("1.0", "end")
        if not text:
            self.files_raw.insert("end", "(profile stage not run yet)")
            return
        self.files_raw.insert("end", text)

        blocks = re.split(r"(?=^== )", text, flags=re.M)
        csv_info = {}
        json_info = {}
        for block in blocks:
            m_csv = re.match(r"== (\w\w)videos\.csv ==", block)
            m_json = re.match(r"== (\w\w)_category_id\.json ==", block)
            if m_csv:
                country = m_csv.group(1)
                wc = re.search(r"wc -l row estimate\s*:\s*([\d,]+)", block)
                pd_rows = re.search(r"pandas row count\s*:\s*([\d,]+)", block)
                disc = re.search(r"discrepancy of ([\d,]+) rows", block)
                cols = re.search(r"columns=(\d+)", block)
                nulls = sum(int(n) for n in re.findall(r"nulls=(\d+)", block))
                csv_info[country] = {
                    "wc": wc.group(1) if wc else "—",
                    "pd": pd_rows.group(1) if pd_rows else "—",
                    "disc": disc.group(1) if disc else "0",
                    "cols": cols.group(1) if cols else "—",
                    "nulls": nulls,
                }
            elif m_json:
                country = m_json.group(1)
                items = re.search(r"items=(\d+)", block)
                json_info[country] = items.group(1) if items else "—"

        for country in COUNTRIES:
            ci = csv_info.get(country, {})
            self.files_tree.insert(
                "", "end",
                values=(
                    country, ci.get("pd", "—"), ci.get("wc", "—"), ci.get("disc", "0"),
                    ci.get("cols", "—"), ci.get("nulls", "—"), json_info.get(country, "—"),
                ),
            )

    # -- Join & partition key parsing --------------------------------------
    def _refresh_join_tab(self):
        self.join_tree.delete(*self.join_tree.get_children())
        if not os.path.exists(FINAL_CSV):
            return
        with open(FINAL_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 500:
                    break
                self.join_tree.insert(
                    "", "end",
                    values=(row.get("country_code", ""), row.get("category_title", ""),
                             row.get("total_views", ""), row.get("total_likes", ""),
                             row.get("video_rows", "")),
                )

    # -- Baseline vs parallel parsing --------------------------------------
    def _parse_benchmark_summary(self):
        text = read_text(BENCHMARK_TXT)
        if not text:
            return []
        m = re.search(r"=== Summary \(execution time in seconds\) ===\n(.+?)(?:\n\n|\Z)",
                       text, flags=re.S)
        if not m:
            return []
        lines = [ln for ln in m.group(1).splitlines() if ln.strip()]
        rows = []
        for ln in lines[1:]:  # skip header row
            m2 = re.match(r"(.{1,28})\s+([\d.]+)\s+(\d+)\s*$", ln)
            if m2:
                rows.append({
                    "run": m2.group(1).strip(),
                    "time": float(m2.group(2)),
                    "rows": int(m2.group(3)),
                })
        return rows

    def _refresh_bench_tab(self):
        self.bench_tree.delete(*self.bench_tree.get_children())
        self.bench_canvas.delete("all")
        text = read_text(BENCHMARK_TXT)
        self.bench_raw.delete("1.0", "end")
        if not text:
            self.bench_raw.insert("end", "(benchmark stage not run yet)")
            return
        self.bench_raw.insert("end", text)

        rows = self._parse_benchmark_summary()
        if not rows:
            return
        baseline = next((r for r in rows if "Sequential" in r["run"]), rows[0])
        fastest_time = min(r["time"] for r in rows)
        for r in rows:
            speedup = baseline["time"] / r["time"] if r["time"] > 0 else 0
            tag = "fastest" if r["time"] == fastest_time else ""
            self.bench_tree.insert(
                "", "end",
                values=(r["run"], f"{r['time']:.3f}", r["rows"], f"{speedup:.2f}x"),
                tags=(tag,) if tag else (),
            )

        # simple bar chart
        canvas = self.bench_canvas
        canvas.update_idletasks()
        width = max(canvas.winfo_width(), 800)
        margin_left = 220
        bar_h = 26
        gap = 14
        max_time = max(r["time"] for r in rows) or 1
        usable_w = width - margin_left - 80
        y = 14
        for r in rows:
            bar_w = max(4, (r["time"] / max_time) * usable_w)
            color = GREEN if r["time"] == fastest_time else NAVY
            canvas.create_text(margin_left - 10, y + bar_h / 2, text=r["run"], anchor="e",
                                font=(FONT_FAMILY, 9))
            canvas.create_rectangle(margin_left, y, margin_left + bar_w, y + bar_h,
                                     fill=color, outline="")
            canvas.create_text(margin_left + bar_w + 8, y + bar_h / 2,
                                text=f"{r['time']:.3f}s", anchor="w", font=(FONT_FAMILY, 9))
            y += bar_h + gap
        canvas.configure(height=max(y + 10, 120))

    # -- Correctness & output parsing ---------------------------------------
    def _refresh_correct_tab(self):
        self.rowcheck_tree.delete(*self.rowcheck_tree.get_children())
        self.cmp_tree.delete(*self.cmp_tree.get_children())
        text = read_text(VALIDATION_TXT)
        self.correct_raw.delete("1.0", "end")
        if not text:
            self.correct_raw.insert("end", "(validation stage not run yet)")
            self.overall_var.set("NOT RUN")
            self.overall_lbl.configure(fg=GREY_TXT)
            return
        self.correct_raw.insert("end", text)

        for m in re.finditer(r"^\s*(\w\w):\s*([\d,]+)\s*->\s*([\d,]+)\s+(OK|MISMATCH)",
                              text, flags=re.M):
            country, before, after, status = m.groups()
            self.rowcheck_tree.insert(
                "", "end", values=(country, before, after, status),
                tags=("ok" if status == "OK" else "mismatch",),
            )

        for m in re.finditer(
            r"=== (.+?) vs sequential ===\nrows match: (\w+)\nmax abs diff views: (\S+)\n"
            r"max abs diff likes: (\S+)\n(PASSED|FAILED)", text,
        ):
            label, rows_match, vdiff, ldiff, result = m.groups()
            self.cmp_tree.insert(
                "", "end", values=(label, rows_match, vdiff, ldiff, result),
                tags=("pass" if result == "PASSED" else "fail",),
            )

        m = re.search(r"OVERALL: (.+)", text)
        if m:
            passed = "PASSED" in m.group(1)
            self.overall_var.set(m.group(1))
            self.overall_lbl.configure(fg=GREEN if passed else RED)

    # -- Partition balance parsing -------------------------------------------
    def _refresh_balance_tab(self):
        self.balance_tree.delete(*self.balance_tree.get_children())
        self.topcat_tree.delete(*self.topcat_tree.get_children())
        text = read_text(SKEW_TXT)
        if not text:
            self.spread_var.set("Run the skew-analysis stage to see spread.")
            return

        for m in re.finditer(
            r"^(\w\w)\s{2,}([\d,]+)\s{2,}([\d,]+)\s{2,}([+-]?[\d.]+)%", text, flags=re.M,
        ):
            country, predicted, actual, pct = m.groups()
            tag = "above" if not pct.startswith("-") else "below"
            self.balance_tree.insert(
                "", "end", values=(country, predicted, actual, f"{pct}%"), tags=(tag,),
            )

        m_small = re.search(r"Smallest partition: (.+)", text)
        m_large = re.search(r"Largest partition:\s*(.+)", text)
        m_spread = re.search(r"Max/min spread: ([\d.]+)x", text)
        if m_small and m_large and m_spread:
            self.spread_var.set(
                f"Smallest: {m_small.group(1).strip()}   ·   "
                f"Largest: {m_large.group(1).strip()}   ·   "
                f"Max/min spread: {m_spread.group(1)}x"
            )

        for country_block in re.finditer(
            r"^\s*(\w\w):\n((?:\s+.+\n?)+?)(?=\n|\s*\w\w:|\Z)", text, flags=re.M,
        ):
            country = country_block.group(1)
            body = country_block.group(2)
            rank = 1
            for line in re.finditer(r"^\s+(.+?)\s+total_views=([\d,]+)", body, flags=re.M):
                cat, views = line.groups()
                self.topcat_tree.insert(
                    "", "end", values=(country, rank, cat.strip(), views),
                )
                rank += 1


def main():
    root = tk.Tk()
    app = PipelineGUI(root)  # noqa: F841
    root.mainloop()


if __name__ == "__main__":
    main()
