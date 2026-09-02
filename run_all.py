#!/usr/bin/env python3
"""
CloudMatrix - reproduce every result in the report
==================================================

Runs the full simulation suite, captures each module's console output into
results/logs/, regenerates every figure, and runs the validation tests. The
report quotes these logs verbatim, so a marker can regenerate the whole
evidence base with one command and diff it against what was submitted.

Run:  python run_all.py
"""

from __future__ import annotations

import io
import platform
import subprocess
import sys
import time
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "results" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)

BANNER = "=" * 78


def header(text: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"{BANNER}\n"
        f" CloudMatrix Operating Systems Assignment - CSA04 (CO3 / CO4 / CO5)\n"
        f" {text}\n"
        f" Generated : {stamp}\n"
        f" Python    : {platform.python_version()} on "
        f"{platform.system()} {platform.release()}\n"
        f" Repository: https://github.com/tharuncoder676/OS-ASSIGNMENT\n"
        f"{BANNER}\n\n"
    )


def capture(name: str, title: str, fn) -> float:
    """Run `fn`, tee its stdout to the console and to results/logs/<name>."""
    print(f"\n>>> {title}")
    started = time.perf_counter()
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn()
    elapsed = time.perf_counter() - started
    body = buf.getvalue()
    path = LOGS / name
    path.write_text(header(title) + body +
                    f"\n{BANNER}\n Completed in {elapsed:.3f} s\n{BANNER}\n",
                    encoding="utf-8")
    lines = body.count("\n")
    print(f"    {lines:>5} lines -> results/logs/{name}   ({elapsed:.3f} s)")
    return elapsed


def main() -> int:
    print(BANNER)
    print(" CloudMatrix - regenerating the complete evidence base")
    print(BANNER)

    from co3_memory import page_table, page_replacement, dynamic_allocation, working_set
    from co4_storage import disk_scheduling, file_allocation, inode_fs
    from co4_storage import disk_dynamic_experiment

    total = 0.0
    total += capture("co3_1_page_table.log",
                     "CO3.1  Memory layout, two-level page table, TLB",
                     page_table.demo)
    total += capture("co3_2_dynamic_allocation.log",
                     "CO3.2  First-Fit / Best-Fit / Worst-Fit, dynamic linking",
                     dynamic_allocation.report)
    total += capture("co3_3_page_replacement.log",
                     "CO3.3  FIFO / LRU / OPTIMAL and Belady's anomaly",
                     page_replacement.run)
    total += capture("co3_4_working_set.log",
                     "CO3.4  Working set, PFF control and the thrashing knee",
                     working_set.main)
    total += capture("co4_1_file_allocation.log",
                     "CO4.1  Contiguous / Linked / Indexed / Extent allocation",
                     file_allocation.main)
    total += capture("co4_2_inode_fs.log",
                     "CO4.2  Inode dynamics, kernel calls, buffer cache",
                     inode_fs.main)
    total += capture("co4_3_disk_scheduling.log",
                     "CO4.3  FCFS / SSTF / SCAN / C-SCAN / LOOK / C-LOOK",
                     disk_scheduling.main)
    total += capture("co4_3b_disk_dynamic.log",
                     "CO4.3b Dynamic-arrival scheduling and load sensitivity",
                     disk_dynamic_experiment.main)

    print("\n>>> Regenerating figures")
    subprocess.run([sys.executable, str(ROOT / "src" / "make_figures.py")],
                   check=True)

    print("\n>>> Running the validation test suite")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT, capture_output=True, text=True)
    (LOGS / "test_results.log").write_text(
        header("Validation test suite (unittest)") +
        result.stdout + result.stderr, encoding="utf-8")
    tail = (result.stderr or result.stdout).strip().splitlines()[-3:]
    for line in tail:
        print("    " + line)

    print()
    print(BANNER)
    print(f" Simulation time    : {total:.3f} s")
    print(f" Logs               : {len(list(LOGS.glob('*.log')))} files in results/logs/")
    print(f" Figures            : "
          f"{len(list((ROOT / 'results' / 'figures').glob('*.png')))} files in results/figures/")
    print(f" Tests              : {'PASSED' if result.returncode == 0 else 'FAILED'}")
    print(BANNER)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
