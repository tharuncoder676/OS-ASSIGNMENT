#!/usr/bin/env python3
"""
CloudMatrix - figure generation
===============================

Renders every chart used in the report directly from the simulators, so no
figure can drift away from the numbers it is supposed to depict. Re-running
this script regenerates the whole figure set from scratch.

Output: results/figures/*.png  (300 dpi, print quality)

Run:  python src/make_figures.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
FIG = ROOT / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

from co3_memory import page_replacement, working_set          # noqa: E402
from co4_storage import disk_scheduling, inode_fs             # noqa: E402
from co4_storage import disk_dynamic_experiment as dyn        # noqa: E402

# A restrained, print-safe palette. Colour is used to separate series, never
# as the only channel carrying meaning -- markers and labels do that too.
C = {
    "primary": "#1f4e79", "accent": "#c00000", "green": "#2e7d32",
    "amber": "#ed7d31", "purple": "#7030a0", "grey": "#7f7f7f",
    "light": "#d9e2f3",
}
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 300, "font.size": 10,
    "font.family": "DejaVu Sans", "axes.grid": True,
    "grid.alpha": 0.25, "grid.linestyle": "--", "axes.axisbelow": True,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.autolayout": False,
})


def save(fig, name: str) -> None:
    path = FIG / name
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"   wrote {path.relative_to(ROOT)}")


# ==========================================================================
# Figure 1 - page faults: FIFO vs LRU vs OPT at 3 and 4 frames
# ==========================================================================

def fig_page_faults():
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        table = page_replacement.run(verbose=False)

    algos = ["FIFO", "LRU", "OPTIMAL"]
    f3 = [table[(a, 3)].faults for a in algos]
    f4 = [table[(a, 4)].faults for a in algos]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 4.2),
                                  gridspec_kw={"width_ratios": [1.15, 1]})
    x = range(len(algos))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], f3, w, label="3 frames",
                color=C["primary"], edgecolor="white")
    b2 = ax.bar([i + w / 2 for i in x], f4, w, label="4 frames",
                color=C["amber"], edgecolor="white")
    for bars in (b1, b2):
        ax.bar_label(bars, padding=2, fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels(algos)
    ax.set_ylabel("Page faults (out of 18 references)")
    ax.set_title("Page faults by algorithm and frame allocation", fontsize=11)
    ax.set_ylim(0, max(f3 + f4) * 1.42)
    ax.legend(frameon=False, loc="upper left", fontsize=9)

    # annotate the anomaly
    ax.annotate("Belady's anomaly:\nMORE memory, MORE faults",
                xy=(0 + w / 2, f4[0] + 0.25), xytext=(1.88, 15.0),
                fontsize=9, color=C["accent"], ha="center", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=C["accent"], lw=1.4,
                                connectionstyle="arc3,rad=-0.18"))

    # right panel: fault rate
    rates3 = [table[(a, 3)].fault_rate for a in algos]
    rates4 = [table[(a, 4)].fault_rate for a in algos]
    ax2.plot(algos, rates3, "o-", color=C["primary"], lw=2, label="3 frames")
    ax2.plot(algos, rates4, "s--", color=C["amber"], lw=2, label="4 frames")
    for a, r in zip(algos, rates4):
        ax2.annotate(f"{r:.1%}", (a, r), textcoords="offset points",
                     xytext=(0, 8), ha="center", fontsize=8.5)
    ax2.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax2.set_ylabel("Page-fault rate")
    ax2.set_title("Fault rate: only FIFO moves the wrong way", fontsize=11)
    ax2.legend(frameon=False)
    ax2.set_ylim(0.35, 0.80)

    fig.suptitle("Figure 1  -  CO3 page replacement on the CloudMatrix trace W",
                 fontsize=12, y=1.02)
    save(fig, "fig1_page_replacement.png")


# ==========================================================================
# Figure 2 - lifetime curve and the thrashing knee
# ==========================================================================

def fig_thrashing():
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        res = working_set.main()

    curve = res["curve"]
    util = res["util"]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.3))

    frames = sorted(curve)
    faults = [curve[f] for f in frames]
    ax.plot(frames, faults, "o-", color=C["primary"], lw=2, ms=5)
    ax.set_xlabel("Frames granted to the process, f")
    ax.set_ylabel("Page-fault rate p(f)  [faults per reference]")
    ax.set_yscale("log")
    ax.set_title("Lifetime curve: the knee is the working-set size", fontsize=11)
    ax.axvline(8, color=C["accent"], ls=":", lw=1.6)
    ax.annotate("knee at f = 8\n(= locality size)", xy=(8, curve[8]),
                xytext=(14, 0.05), fontsize=8.5, color=C["accent"],
                arrowprops=dict(arrowstyle="->", color=C["accent"], lw=1.2))
    ax.fill_betweenx([1e-4, 1], 0, 8, color=C["accent"], alpha=0.07)
    ax.text(4.2, 0.0025, "paging-bound", fontsize=8.5, color=C["accent"],
            ha="center", style="italic")

    ns = sorted(util)
    ucpu = [util[n][4] for n in ns]
    udisk = [util[n][5] for n in ns]
    ax2.plot(ns, ucpu, "o-", color=C["primary"], lw=2.2, ms=5,
             label="CPU utilisation")
    ax2.plot(ns, udisk, "s--", color=C["accent"], lw=1.8, ms=4,
             label="Paging-device utilisation")
    ax2.set_xlabel("Degree of multiprogramming, N guests")
    ax2.set_ylabel("Utilisation")
    ax2.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax2.set_title("Thrashing: CPU collapses as the disk saturates", fontsize=11)
    ax2.axvline(res["best_n"], color=C["green"], ls=":", lw=1.6)
    ax2.annotate(f"admission cap\nN = {res['best_n']}",
                 xy=(res["best_n"], 1.0), xytext=(res["best_n"] + 3.5, 0.78),
                 fontsize=8.5, color=C["green"],
                 arrowprops=dict(arrowstyle="->", color=C["green"], lw=1.2))
    ax2.legend(frameon=False, loc="center right", fontsize=9)
    ax2.set_ylim(-0.03, 1.10)

    fig.suptitle("Figure 2  -  CO3 working-set lifetime curve and the thrashing knee",
                 fontsize=12, y=1.02)
    save(fig, "fig2_thrashing.png")


# ==========================================================================
# Figure 3 - disk scheduling head movement (static queue)
# ==========================================================================

def fig_disk_static():
    import io
    from contextlib import redirect_stdout
    with redirect_stdout(io.StringIO()):
        results = disk_scheduling.main()

    names = [r["name"] for r in results]
    totals = [r["total"] for r in results]
    colours = [C["accent"] if t == max(totals) else
               C["green"] if t == min(totals) else C["primary"] for t in totals]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.4),
                                  gridspec_kw={"width_ratios": [1, 1.25]})
    bars = ax.barh(names, totals, color=colours, edgecolor="white", height=0.62)
    ax.bar_label(bars, fmt="%d", padding=4, fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Total head movement (cylinders)")
    ax.set_title("Total seek distance, 12-request queue", fontsize=11)
    ax.set_xlim(0, max(totals) * 1.18)

    # head-movement traces
    for r, colour in zip(results, [C["accent"], C["green"], C["primary"],
                                   C["amber"], C["purple"], C["grey"]]):
        ax2.plot(r["path"], range(len(r["path"])), "o-", ms=3.2, lw=1.4,
                 color=colour, label=f"{r['name']} ({r['total']})", alpha=0.88)
    ax2.invert_yaxis()
    ax2.set_xlabel("Cylinder")
    ax2.set_ylabel("Service step")
    ax2.set_title("Head trajectory (head starts at cylinder 125)", fontsize=11)
    ax2.legend(frameon=False, fontsize=8, ncol=2, loc="lower right")
    ax2.set_xlim(-15, 515)

    fig.suptitle("Figure 3  -  CO4 disk scheduling on the 500-cylinder store, "
                 "queue = [86,147,312,91,177,48,409,22,130,365,220,480]",
                 fontsize=11.5, y=1.02)
    save(fig, "fig3_disk_static.png")


# ==========================================================================
# Figure 4 - dynamic arrivals: latency distribution and load sensitivity
# ==========================================================================

def fig_disk_dynamic():
    workload = dyn.generate_workload()
    names, means, p99s, maxs = [], [], [], []
    for name, picker in dyn.SCHEDULERS:
        resp, _ = dyn.simulate(workload, picker)
        times = [r for r, _, _ in resp]
        names.append(name)
        means.append(sum(times) / len(times))
        p99s.append(dyn.pct(times, 99))
        maxs.append(max(times))

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.4))
    x = range(len(names))
    w = 0.27
    ax.bar([i - w for i in x], means, w, label="mean",
           color=C["primary"], edgecolor="white")
    ax.bar(list(x), p99s, w, label="p99", color=C["amber"], edgecolor="white")
    ax.bar([i + w for i in x], maxs, w, label="maximum",
           color=C["accent"], edgecolor="white")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=18, ha="right")
    ax.set_ylabel("Response time (ms)")
    ax.set_title("Latency distribution under continuous arrivals (88% load)",
                 fontsize=11)
    ax.axhline(10, color=C["green"], ls="--", lw=1.4)
    ax.text(len(names) - 0.4, 12, "Section D target: 10 ms",
            fontsize=8.5, color=C["green"], ha="right")
    ax.legend(frameon=False, fontsize=9)

    # load sensitivity
    rates = [0.15, 0.25, 0.35, 0.45, 0.55]
    series = {n: [] for n, _ in dyn.SCHEDULERS}
    original = dyn.ARRIVAL_RATE
    for rate in rates:
        dyn.ARRIVAL_RATE = rate
        wl = dyn.generate_workload(n=2500)
        for n, picker in dyn.SCHEDULERS:
            resp, _ = dyn.simulate(wl, picker)
            series[n].append(dyn.pct([r for r, _, _ in resp], 99))
    dyn.ARRIVAL_RATE = original

    styles = [(C["grey"], "o-"), (C["accent"], "s-"), (C["primary"], "^-"),
              (C["purple"], "v--"), (C["green"], "D-"), (C["amber"], "P--")]
    for (n, _), (colour, st) in zip(dyn.SCHEDULERS, styles):
        ax2.plot(rates, series[n], st, color=colour, lw=1.8, ms=5, label=n)
    ax2.axhline(10, color=C["green"], ls="--", lw=1.4)
    ax2.set_xlabel("Offered arrival rate (requests / ms)")
    ax2.set_ylabel("p99 response time (ms)")
    ax2.set_yscale("log")
    ax2.set_title("Load sensitivity: the algorithms separate only at saturation",
                  fontsize=11)
    ax2.legend(frameon=False, fontsize=8, ncol=2)

    fig.suptitle("Figure 4  -  CO4 dynamic-arrival disk scheduling experiment "
                 "(4,000 requests, seed 192511416)", fontsize=11.5, y=1.02)
    save(fig, "fig4_disk_dynamic.png")


# ==========================================================================
# Figure 5 - buffer cache hit ratio
# ==========================================================================

def fig_buffer_cache():
    trace = inode_fs.block_trace()
    sizes = [16, 32, 64, 128, 256, 512, 1024, 2048, 4096]
    ratios, writes = [], []
    for s in sizes:
        c = inode_fs.BufferCache(s)
        for op, blk in trace:
            (c.read if op == "r" else c.write)(blk)
        c.sync()
        ratios.append(c.hit_ratio)
        writes.append(c.writes_to_disk)

    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    ax.plot(sizes, ratios, "o-", color=C["primary"], lw=2.2, ms=6,
            label="Buffer-cache hit ratio")
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Buffer cache size (4 KB buffers)")
    ax.set_ylabel("Hit ratio")
    ax.yaxis.set_major_formatter(PercentFormatter(1.0))
    ax.axhline(0.80, color=C["accent"], ls="--", lw=1.4)
    ax.text(20, 0.815, "achievable ceiling ~80% (20% of the trace streams "
                       "an uncacheable 59,000-block region)",
            fontsize=8, color=C["accent"])
    ax.set_ylim(0, 0.95)

    ax2 = ax.twinx()
    ax2.plot(sizes, writes, "s--", color=C["amber"], lw=1.8, ms=5,
             label="Physical writes (delayed write)")
    ax2.set_ylabel("Physical disk writes", color=C["amber"])
    ax2.tick_params(axis="y", colors=C["amber"])
    ax2.grid(False)

    lines = ax.get_lines() + ax2.get_lines()
    ax.legend(lines, [l.get_label() for l in lines],
              frameon=False, fontsize=9, loc="center right")
    ax.set_title("Figure 5  -  CO4 buffer-cache hit ratio and write coalescing",
                 fontsize=11.5)
    save(fig, "fig5_buffer_cache.png")


# ==========================================================================
# Figure 6 - file allocation access cost
# ==========================================================================

def fig_allocation_cost():
    from co4_storage import file_allocation as fa
    methods = ["Contiguous", "Linked", "Indexed", "Extent (ext4-style)"]
    n = 95      # tenant-db.dump
    seq = [fa.access_costs(m, n)[0] for m in methods]
    rnd = [fa.access_costs(m, n)[1] for m in methods]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.3),
                                  gridspec_kw={"width_ratios": [1.15, 1]})
    x = range(len(methods))
    w = 0.36
    b1 = ax.bar([i - w / 2 for i in x], seq, w, label="Sequential read",
                color=C["primary"], edgecolor="white")
    b2 = ax.bar([i + w / 2 for i in x], rnd, w, label="Random read (every 4th block)",
                color=C["accent"], edgecolor="white")
    ax.bar_label(b1, fmt="%d", padding=2, fontsize=8.5)
    ax.bar_label(b2, fmt="%d", padding=2, fontsize=8.5)
    ax.set_yscale("log")
    ax.set_xticks(list(x))
    ax.set_xticklabels([m.replace(" (ext4-style)", "\n(ext4-style)")
                        for m in methods], fontsize=9)
    ax.set_ylabel("Block I/Os (log scale)")
    ax.set_title("Access cost for tenant-db.dump (95 blocks)", fontsize=11)
    ax.legend(frameon=False, fontsize=9)

    # metadata overhead as file size grows
    sizes = [4 * fa.KB, 1 * fa.MB, 80 * fa.MB, 1 * fa.GB, 8 * fa.GB, 50 * fa.GB]
    labels = ["4 KB", "1 MB", "80 MB", "1 GB", "8 GB", "50 GB"]
    meta = [inode_fs.metadata_blocks_for(s)["meta_blocks"] for s in sizes]
    ax2.plot(range(len(sizes)), [max(m, 0.5) for m in meta], "o-",
             color=C["purple"], lw=2, ms=6, label="Classical indirect chain")
    ax2.plot(range(len(sizes)), [1] * len(sizes), "s--", color=C["green"],
             lw=2, ms=5, label="Extent map (fits in the inode)")
    ax2.set_yscale("log")
    ax2.set_xticks(range(len(sizes)))
    ax2.set_xticklabels(labels)
    ax2.set_xlabel("File size")
    ax2.set_ylabel("Indirect metadata blocks (log scale)")
    ax2.set_title("Why ext4 replaced indirect blocks with extents", fontsize=11)
    ax2.annotate(f"{meta[-1]:,} indirect blocks\n= 50 MB of pure pointers",
                 xy=(5, meta[-1]), xytext=(2.1, 120), fontsize=8.5,
                 color=C["purple"], ha="center",
                 arrowprops=dict(arrowstyle="->", color=C["purple"], lw=1.2,
                                 connectionstyle="arc3,rad=0.22"))
    ax2.legend(frameon=False, fontsize=8.5, loc="upper left")

    fig.suptitle("Figure 6  -  CO4 file allocation: access cost and metadata overhead",
                 fontsize=11.5, y=1.02)
    save(fig, "fig6_allocation.png")


# ==========================================================================

def main():
    print("Generating figures into results/figures/ ...")
    fig_page_faults()
    fig_thrashing()
    fig_disk_static()
    fig_disk_dynamic()
    fig_buffer_cache()
    fig_allocation_cost()
    print("All figures generated.")


if __name__ == "__main__":
    main()
