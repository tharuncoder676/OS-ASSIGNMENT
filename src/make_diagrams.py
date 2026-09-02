#!/usr/bin/env python3
"""
CloudMatrix - report diagrams
=============================

Draws the four schematic diagrams the report needs: the two-level address
translation path, the integrated CO3/CO4/CO5 subsystem architecture, the
network and virtualization topology, and the file-read request flow.

These are schematics rather than plots, so they are drawn explicitly rather
than derived from data. Every label, however, carries a figure that the
simulators produced, so the diagrams and the measurements agree.

Output: results/figures/fig07..fig10 (300 dpi)

Run:  python src/make_diagrams.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "results" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

CO3 = "#dbe9f6"; CO3E = "#1f4e79"
CO4 = "#fde9d9"; CO4E = "#c55a11"
CO5 = "#e2f0d9"; CO5E = "#2e7d32"
NEUT = "#f2f2f2"; NEUTE = "#7f7f7f"
HOT = "#fbdcdc"; HOTE = "#c00000"

plt.rcParams.update({"font.family": "DejaVu Sans", "savefig.dpi": 300})


def box(ax, x, y, w, h, text, fc=NEUT, ec=NEUTE, fs=8.5, bold=False, r=0.02):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle=f"round,pad=0.004,rounding_size={r}",
                                facecolor=fc, edgecolor=ec, linewidth=1.3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", linespacing=1.45, zorder=5)


def arrow(ax, p1, p2, colour="#404040", style="-|>", lw=1.4, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=13,
                                 linewidth=lw, color=colour, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=2, shrinkB=2, zorder=4))


def canvas(w, h, title):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 10); ax.set_ylim(0, h / w * 10)
    ax.axis("off")
    ax.set_title(title, fontsize=11.5, fontweight="bold", pad=12)
    return fig, ax


def save(fig, name):
    fig.savefig(FIG / name, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"   wrote results/figures/{name}")


# ==========================================================================
# Figure 7 - two-level address translation
# ==========================================================================

def fig_translation():
    fig, ax = canvas(11, 5.4, "Figure 7  -  CO3 two-level address translation on the "
                              "CloudMatrix host (27-bit VA, 35-bit PA)")
    Y = 4.9

    # the virtual address, split into its three fields
    ax.text(0.05, Y - 0.05, "Virtual address  (27 bits)", fontsize=9,
            fontweight="bold", color=CO3E)
    box(ax, 0.05, Y - 0.85, 1.55, 0.62, "p1\n5 bits", CO3, CO3E, 8.5, True)
    box(ax, 1.60, Y - 0.85, 2.30, 0.62, "p2\n10 bits", CO3, CO3E, 8.5, True)
    box(ax, 3.90, Y - 0.85, 2.60, 0.62, "d  (offset)\n12 bits", "#ffffff", CO3E, 8.5, True)
    ax.text(6.65, Y - 0.54, "0x0400ABC  →  p1=1, p2=0, d=0xABC",
            fontsize=8, color="#404040", va="center", style="italic")

    # TLB fast path
    box(ax, 0.05, Y - 2.05, 2.9, 0.78,
        "TLB  (64 entries)\nmeasured hit ratio 58.3%", CO5, CO5E, 8.5)
    arrow(ax, (0.8, Y - 0.85), (0.9, Y - 1.27), CO5E)
    arrow(ax, (2.95, Y - 1.66), (7.55, Y - 1.66), CO5E, rad=-0.12)
    ax.text(5.2, Y - 1.42, "TLB hit → 1 memory reference", fontsize=8,
            color=CO5E, ha="center")

    # the walk
    box(ax, 0.05, Y - 3.35, 2.9, 0.86,
        "Outer page table\n32 entries × 4 B = 128 B\n(PTBR + p1)", CO3, CO3E, 8)
    box(ax, 3.35, Y - 3.35, 3.0, 0.86,
        "Inner page table\n1,024 entries × 4 B = 4 KB\n(exactly one frame)", CO3, CO3E, 8)
    arrow(ax, (1.5, Y - 2.05), (1.5, Y - 2.49), CO3E)
    arrow(ax, (2.95, Y - 2.92), (3.35, Y - 2.92), CO3E)
    ax.text(1.5, Y - 2.22, "TLB miss", fontsize=7.5, color=HOTE, ha="center")

    # outcome
    box(ax, 6.85, Y - 2.05, 3.1, 0.78,
        "Physical address (35 bits)\nframe 23 bits | offset 12 bits", CO3, CO3E, 8.5, True)
    arrow(ax, (6.35, Y - 2.92), (8.4, Y - 2.05), CO3E, rad=0.18)
    ax.text(7.6, Y - 2.72, "valid", fontsize=7.5, color=CO3E)

    box(ax, 6.85, Y - 3.45, 3.1, 0.86,
        "PAGE FAULT\n8 ms NVMe swap service\nLRU victim (stack algorithm)", HOT, HOTE, 8)
    arrow(ax, (6.35, Y - 3.05), (6.85, Y - 3.05), HOTE)
    ax.text(6.6, Y - 3.28, "invalid", fontsize=7.5, color=HOTE, ha="center")
    arrow(ax, (8.4, Y - 3.45), (8.4, Y - 2.05), HOTE, rad=0.35, ls="--", lw=1.1)

    # footnote of measured results
    ax.text(0.05, 0.28,
            "Measured (results/logs/co3_1_page_table.log):  effective access time "
            "184.33 ns with the TLB, 300.00 ns without.\n"
            "Page-table residency per process: 128 KB flat  →  4 KB sparse two-level, "
            "a 32× reduction across 1,200 guests.",
            fontsize=8, color="#404040", linespacing=1.6)
    save(fig, "fig07_address_translation.png")


# ==========================================================================
# Figure 8 - integrated subsystem architecture
# ==========================================================================

def fig_architecture():
    fig, ax = canvas(11, 7.4, "Figure 8  -  CloudMatrix integrated subsystem "
                              "architecture: one request path through CO3, CO4 and CO5")
    H = 7.4 / 11 * 10

    # tenants
    ax.add_patch(FancyBboxPatch((0.15, H - 1.25), 9.7, 0.95,
                                boxstyle="round,pad=0.01,rounding_size=0.04",
                                facecolor="#ffffff", edgecolor=NEUTE, ls="--"))
    ax.text(0.32, H - 0.45, "Tenant workloads  —  1,200 concurrent sessions",
            fontsize=8.5, fontweight="bold", color="#404040")
    for i, (t, n) in enumerate([("Web / DNS", "900 × 16 MB"),
                                ("Enterprise app", "240 × 48 MB"),
                                ("Database VM", "40 × 192 MB"),
                                ("Batch analytics", "20 × 160 MB")]):
        box(ax, 0.35 + i * 2.4, H - 1.12, 2.15, 0.5, f"{t}\n{n} WSS", "#ffffff",
            NEUTE, 7.6)

    # CO5
    ax.add_patch(FancyBboxPatch((0.15, H - 2.62), 9.7, 1.12,
                                boxstyle="round,pad=0.01,rounding_size=0.04",
                                facecolor=CO5, edgecolor=CO5E, alpha=0.45))
    ax.text(0.30, H - 1.66, "CO5  Virtualization and network services",
            fontsize=8.5, fontweight="bold", color=CO5E)
    for i, t in enumerate(["Xen / KVM hypervisor\nCPU pinning · ballooning · sVirt",
                           "br0 virtual bridge\nvirtio-net · anti-spoof filter",
                           "BIND9 + ISC DHCP\n10.20.30.0/24 · TSIG transfers"]):
        box(ax, 0.35 + i * 3.2, H - 2.50, 2.95, 0.68, t, "#ffffff", CO5E, 7.6)

    # CO3
    ax.add_patch(FancyBboxPatch((0.15, H - 4.05), 4.72, 1.20,
                                boxstyle="round,pad=0.01,rounding_size=0.04",
                                facecolor=CO3, edgecolor=CO3E, alpha=0.45))
    ax.text(0.30, H - 3.02, "CO3  Virtual memory subsystem", fontsize=8.5,
            fontweight="bold", color=CO3E)
    for i, t in enumerate(["TLB\n64 entries", "Two-level PT\n5 | 10 | 12",
                           "8,388,608\nframes"]):
        box(ax, 0.33 + i * 1.53, H - 3.92, 1.42, 0.68, t, "#ffffff", CO3E, 7.4)

    # CO4
    ax.add_patch(FancyBboxPatch((5.13, H - 4.05), 4.72, 1.20,
                                boxstyle="round,pad=0.01,rounding_size=0.04",
                                facecolor=CO4, edgecolor=CO4E, alpha=0.45))
    ax.text(5.28, H - 3.02, "CO4  File system and block layer", fontsize=8.5,
            fontweight="bold", color=CO4E)
    for i, t in enumerate(["VFS / namei()\ndentry cache", "Inode + bmap()\n10 dir + 3 ind",
                           "Buffer cache\n76.9% hit"]):
        box(ax, 5.31 + i * 1.53, H - 3.92, 1.42, 0.68, t, "#ffffff", CO4E, 7.4)

    # control loop + scheduler
    box(ax, 0.35, H - 5.15, 4.35, 0.72,
        "PFF controller   U = 0.50 / L = 0.10 faults per ms\n"
        "balloon · KSM · suspend batch tier   (D/m 1.248 → 0.929)", CO3, CO3E, 7.6)
    box(ax, 5.31, H - 5.15, 4.35, 0.72,
        "I/O scheduler   C-LOOK (Linux mq-deadline)\n"
        "bounded wait: one sweep · p99 28.2 ms at 88% load", CO4, CO4E, 7.6)

    box(ax, 2.95, H - 6.25, 4.10, 0.66,
        "500-cylinder block store  +  NVMe swap (8 ms service)", "#e7e6e6", "#404040",
        8, True)

    # arrows
    arrow(ax, (5.0, H - 1.25), (5.0, H - 1.50), "#404040")
    arrow(ax, (2.5, H - 2.62), (2.5, H - 2.88), CO3E)
    arrow(ax, (7.5, H - 2.62), (7.5, H - 2.88), CO4E)
    arrow(ax, (4.87, H - 3.45), (5.13, H - 3.45), "#404040")
    ax.text(5.0, H - 3.34, "page fault", fontsize=7, ha="center", color=HOTE)
    arrow(ax, (2.5, H - 4.05), (2.5, H - 4.43), CO3E)
    arrow(ax, (7.5, H - 4.05), (7.5, H - 4.43), CO4E)
    arrow(ax, (2.5, H - 5.15), (4.2, H - 5.59), CO3E, rad=-0.15)
    arrow(ax, (7.5, H - 5.15), (5.9, H - 5.59), CO4E, rad=0.15)
    arrow(ax, (3.4, H - 5.59), (1.5, H - 5.15), "#404040", rad=0.25, ls="--", lw=1.0)

    ax.text(0.15, 0.12,
            "Solid arrows: the request path.  Dashed: feedback into the frame "
            "allocator.  Every quoted figure is produced by a module in src/ and "
            "captured in results/logs/.",
            fontsize=7.6, color="#404040")
    save(fig, "fig08_architecture.png")


# ==========================================================================
# Figure 9 - network and virtualization topology
# ==========================================================================

def fig_topology():
    fig, ax = canvas(11, 6.2, "Figure 9  -  CloudMatrix Linux multifunction server: "
                              "network topology and tenant isolation boundaries")
    H = 6.2 / 11 * 10

    box(ax, 0.15, H - 0.95, 1.75, 0.62, "Internet", "#ffffff", NEUTE, 8.5)
    box(ax, 2.30, H - 0.95, 2.05, 0.62, "gw\n10.20.30.1", "#ffffff", NEUTE, 8)
    arrow(ax, (1.90, H - 0.64), (2.30, H - 0.64))

    # host
    ax.add_patch(FancyBboxPatch((0.15, H - 3.55), 5.35, 2.30,
                                boxstyle="round,pad=0.01,rounding_size=0.04",
                                facecolor="#fafafa", edgecolor="#404040", ls="--"))
    ax.text(0.32, H - 1.48, "CloudMatrix host  10.20.30.5  (Ubuntu 24.04, kernel 6.x)",
            fontsize=8.2, fontweight="bold", color="#404040")
    box(ax, 0.35, H - 2.30, 2.35, 0.62, "eno1\nno IP · enslaved", "#ffffff", NEUTE, 7.6)
    box(ax, 2.95, H - 2.30, 2.35, 0.62, "br0  10.20.30.5/24\nSTP on", CO5, CO5E, 7.6, True)
    box(ax, 0.35, H - 3.40, 2.35, 0.72,
        "Xen / libvirt\nxl list · virsh list", CO5, CO5E, 7.6)
    box(ax, 2.95, H - 3.40, 2.35, 0.72,
        "br1  tenant overlay\nno host IP, no route", HOT, HOTE, 7.6, True)
    arrow(ax, (2.70, H - 1.99), (2.95, H - 1.99), CO5E)
    arrow(ax, (1.52, H - 3.40), (1.52, H - 2.30), CO5E, rad=0.0)
    arrow(ax, (2.70, H - 3.04), (2.95, H - 3.04), HOTE)
    arrow(ax, (3.35, H - 0.95), (4.12, H - 1.68), NEUTE, rad=-0.15)

    # services
    ax.add_patch(FancyBboxPatch((5.85, H - 2.55), 4.0, 1.30,
                                boxstyle="round,pad=0.01,rounding_size=0.04",
                                facecolor=CO5, edgecolor=CO5E, alpha=0.4))
    ax.text(6.0, H - 1.45, "Network services", fontsize=8.2, fontweight="bold",
            color=CO5E)
    box(ax, 6.0, H - 2.42, 1.18, 0.78, "ns1\nBIND9\nprimary\n.10", "#ffffff", CO5E, 7)
    box(ax, 7.32, H - 2.42, 1.18, 0.78, "ns2\nBIND9\nsecondary\n.11", "#ffffff", CO5E, 7)
    box(ax, 8.64, H - 2.42, 1.18, 0.78, "dhcp\nISC\npool .100\n-.199", "#ffffff", CO5E, 7)
    arrow(ax, (7.18, H - 2.03), (7.32, H - 2.03), CO5E, style="<|-|>", lw=1.1)
    ax.text(7.25, H - 1.80, "AXFR\nTSIG", fontsize=6.4, ha="center", color=CO5E)
    arrow(ax, (5.30, H - 1.99), (5.85, H - 1.90), CO5E)

    # guests
    ax.add_patch(FancyBboxPatch((5.85, H - 4.45), 4.0, 1.62,
                                boxstyle="round,pad=0.01,rounding_size=0.04",
                                facecolor="#ffffff", edgecolor=NEUTE, ls="--"))
    ax.text(6.0, H - 3.05, "Guest virtual machines", fontsize=8.2,
            fontweight="bold", color="#404040")
    for i, (n, ip) in enumerate([("vm-web-01", ".101"), ("vm-db-02", ".102"),
                                 ("vm-win11-07", ".107")]):
        box(ax, 6.0 + i * 1.32, H - 3.85, 1.18, 0.58, f"{n}\n{ip}", "#ffffff", CO5E, 6.8)
    box(ax, 6.0, H - 4.35, 3.82, 0.42, "tenant-a  ·  10.20.40.0/24  (isolated on br1)",
        HOT, HOTE, 7.2)
    arrow(ax, (5.30, H - 2.30), (6.0, H - 3.55), CO5E, rad=-0.2)
    arrow(ax, (5.30, H - 3.15), (6.0, H - 4.14), HOTE, rad=-0.15)

    ax.text(0.15, 0.42,
            "Isolation boundaries proved in tools/validate_co5.sh:  br1 carries no host "
            "address and no default route, so overlay guests have no layer-2 path to the\n"
            "management LAN.  Each vNIC carries a clean-traffic filter bound to its "
            "assigned IP.  Zone transfers are TSIG-authenticated.  Forward/reverse "
            "consistency: 15 A records ↔ 15 PTR records, all matched.",
            fontsize=7.5, color="#404040", linespacing=1.6)
    save(fig, "fig09_topology.png")


# ==========================================================================
# Figure 10 - file read request flow
# ==========================================================================

def fig_request_flow():
    fig, ax = canvas(11, 4.6, "Figure 10  -  CO4 request flow: a guest file read from "
                              "pathname to physical block, with measured costs")
    H = 4.6 / 11 * 10

    stages = [
        ("Guest VM\nread(path, off)", "#ffffff", NEUTE, "", ""),
        ("namei()\npath resolution", CO4, CO4E, "5 I/Os cold", "1 I/O warm"),
        ("inode + bmap()\ntier selection", CO4, CO4E, "1 read direct", "4 reads triple"),
        ("Buffer cache\nLRU, delayed write", CO5, CO5E, "76.9% hit", "1,024 buffers"),
        ("I/O scheduler\nC-LOOK sweep", CO4, CO4E, "bounded wait", "one sweep"),
        ("Disk\nseek + transfer", "#e7e6e6", "#404040", "0.5 ms settle", "0.01 ms/cyl"),
    ]
    w, gap = 1.44, 0.28
    x = 0.15
    for i, (label, fc, ec, m1, m2) in enumerate(stages):
        box(ax, x, H - 1.85, w, 0.92, label, fc, ec, 7.6, True)
        if m1:
            ax.text(x + w / 2, H - 2.10, m1, fontsize=7, ha="center", color=ec)
            ax.text(x + w / 2, H - 2.34, m2, fontsize=7, ha="center", color="#707070")
        if i < len(stages) - 1:
            arrow(ax, (x + w, H - 1.39), (x + w + gap, H - 1.39), "#404040")
        x += w + gap

    # the cache short-circuit
    arrow(ax, (5.30, H - 0.93), (1.60, H - 0.93), CO5E, rad=-0.16, ls="--")
    ax.text(3.45, H - 0.62, "cache hit: no disk I/O at all  (76.9% of reads)",
            fontsize=7.6, ha="center", color=CO5E, style="italic")

    ax.text(0.15, H - 3.10,
            "Worst case on a cold cache: 4 directory reads + 1 inode read + 3 indirect "
            "reads + 1 data read = 9 physical I/Os for one byte of a 50 GB image.",
            fontsize=8, color="#404040")
    ax.text(0.15, H - 3.45,
            "This is the number that justifies both the dentry/inode cache and the move "
            "from indirect chains to extents for large files.",
            fontsize=8, color="#404040")
    save(fig, "fig10_request_flow.png")


def main():
    print("Drawing report diagrams ...")
    fig_translation()
    fig_architecture()
    fig_topology()
    fig_request_flow()
    print("Done.")


if __name__ == "__main__":
    main()
