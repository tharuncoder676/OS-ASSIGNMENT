#!/usr/bin/env python3
"""
CloudMatrix - CO3 : Memory Layout and Two-Level Page Table Design
=================================================================

Derives the frame/page geometry of the CloudMatrix virtualization host and
implements a working two-level page-table walker, so the bit-splitting quoted
in the report can actually be executed and checked rather than asserted.

Host parameters (Section D of the assignment brief):
    Physical RAM           : 32 GB
    Page / frame size      : 4 KB   (2 MB hugepages evaluated separately)
    Per-process logical AS : 128 MB

Run:  python src/co3_memory/page_table.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

KB = 1024
MB = 1024 * KB
GB = 1024 * MB


# --------------------------------------------------------------------------
# 1. Geometry derivation
# --------------------------------------------------------------------------

@dataclass
class MemoryGeometry:
    """Every number the report quotes, derived rather than hard-coded."""

    physical_ram: int = 32 * GB
    page_size: int = 4 * KB
    logical_as: int = 128 * MB
    pte_size: int = 4  # bytes per page-table entry

    def __post_init__(self) -> None:
        self.frames = self.physical_ram // self.page_size
        self.pages = self.logical_as // self.page_size
        self.offset_bits = int(math.log2(self.page_size))
        self.page_number_bits = int(math.log2(self.pages))
        self.virtual_bits = self.offset_bits + self.page_number_bits
        self.physical_bits = int(math.log2(self.physical_ram))
        self.frame_bits = self.physical_bits - self.offset_bits

        # An inner table is sized to occupy exactly one page -- the standard
        # trick that lets page tables themselves be paged.
        self.entries_per_page = self.page_size // self.pte_size
        self.inner_bits = int(math.log2(self.entries_per_page))
        self.outer_bits = self.page_number_bits - self.inner_bits

        self.flat_table_bytes = self.pages * self.pte_size
        self.inner_tables = 1 << self.outer_bits
        self.outer_table_bytes = self.inner_tables * self.pte_size

    def report(self) -> str:
        gb = self.physical_ram // GB
        sparse = self.outer_table_bytes + self.page_size
        full = self.outer_table_bytes + self.inner_tables * self.page_size
        return "\n".join([
            "=" * 78,
            " CO3.1  MEMORY LAYOUT AND PAGE TABLE GEOMETRY - CloudMatrix host",
            "=" * 78,
            f"  Physical RAM                  : {gb} GB = 2^{self.physical_bits} bytes",
            f"  Page / frame size             : {self.page_size // KB} KB = 2^{self.offset_bits} bytes",
            f"  TOTAL PHYSICAL FRAMES         : {self.frames:,}  (2^{int(math.log2(self.frames))})",
            f"  Logical AS per process        : {self.logical_as // MB} MB = 2^{int(math.log2(self.logical_as))} bytes",
            f"  VIRTUAL PAGES PER PROCESS     : {self.pages:,}  (2^{self.page_number_bits})",
            "",
            f"  Virtual address width         : {self.virtual_bits} bits"
            f"   [ p = {self.page_number_bits} bits | d = {self.offset_bits} bits ]",
            f"  Physical address width        : {self.physical_bits} bits"
            f"   [ f = {self.frame_bits} bits | d = {self.offset_bits} bits ]",
            "",
            "  --- Two-level split (inner table sized to exactly one page) ---",
            f"  PTE size                      : {self.pte_size} bytes",
            f"  Entries per 4 KB table page   : {self.entries_per_page}"
            f"  ->  inner index p2 = {self.inner_bits} bits",
            f"  Outer index p1                : {self.page_number_bits} - {self.inner_bits}"
            f" = {self.outer_bits} bits",
            f"  VA layout                     : | p1 = {self.outer_bits} | p2 = {self.inner_bits}"
            f" | d = {self.offset_bits} |",
            f"  Outer page table              : {self.inner_tables} entries"
            f" = {self.outer_table_bytes} bytes",
            f"  Each inner page table         : {self.entries_per_page} entries"
            f" = {self.page_size // KB} KB (exactly one frame)",
            "",
            "  --- Space cost of the design decision ---",
            f"  Single-level (flat) table     : {self.flat_table_bytes // KB} KB per process,"
            " resident whether or not the pages are touched",
            f"  Two-level, fully populated    : {full // KB} KB per process",
            f"  Two-level, sparse (1 inner)   : {sparse // KB} KB per process",
            f"  1,200 sessions x sparse cost  : {1200 * sparse / MB:.2f} MB out of the {gb} GB pool",
            f"  1,200 sessions x flat cost    : {1200 * self.flat_table_bytes / MB:.2f} MB"
            " (32x worse, and mostly never referenced)",
        ])


# --------------------------------------------------------------------------
# 2. Executable two-level MMU with a TLB in front of it
# --------------------------------------------------------------------------

@dataclass
class TwoLevelMMU:
    geo: MemoryGeometry
    tlb_entries: int = 64

    outer: dict = field(default_factory=dict)   # p1 -> {p2: frame}
    tlb: dict = field(default_factory=dict)     # page -> frame, ordered = LRU
    next_free_frame: int = 0
    stats: dict = field(default_factory=lambda: {
        "translations": 0, "tlb_hit": 0, "tlb_miss": 0,
        "page_fault": 0, "memory_reads": 0,
    })

    def split(self, va: int) -> tuple[int, int, int]:
        d = va & (self.geo.page_size - 1)
        page = va >> self.geo.offset_bits
        p2 = page & (self.geo.entries_per_page - 1)
        p1 = page >> self.geo.inner_bits
        return p1, p2, d

    def map_page(self, page: int, frame: int) -> None:
        p1 = page >> self.geo.inner_bits
        p2 = page & (self.geo.entries_per_page - 1)
        self.outer.setdefault(p1, {})[p2] = frame

    def _tlb_insert(self, page: int, frame: int) -> None:
        if page in self.tlb:
            del self.tlb[page]
        elif len(self.tlb) >= self.tlb_entries:
            self.tlb.pop(next(iter(self.tlb)))
        self.tlb[page] = frame

    def translate(self, va: int, verbose: bool = False) -> int:
        self.stats["translations"] += 1
        p1, p2, d = self.split(va)
        page = (p1 << self.geo.inner_bits) | p2

        if page in self.tlb:
            self.stats["tlb_hit"] += 1
            frame = self.tlb.pop(page)
            self.tlb[page] = frame            # refresh recency
            self.stats["memory_reads"] += 1   # the datum only
            path = "TLB hit           (1 memory ref)"
        else:
            self.stats["tlb_miss"] += 1
            inner = self.outer.get(p1)
            self.stats["memory_reads"] += 3   # outer + inner + datum
            if inner is None or p2 not in inner:
                self.stats["page_fault"] += 1
                frame = self.next_free_frame
                self.next_free_frame += 1
                self.map_page(page, frame)
                path = "PAGE FAULT        (frame allocated)"
            else:
                frame = inner[p2]
                path = "TLB miss          (2 table walks)"
            self._tlb_insert(page, frame)

        pa = (frame << self.geo.offset_bits) | d
        if verbose:
            print(f"   VA 0x{va:07X}  p1={p1:<3} p2={p2:<5} d=0x{d:03X}"
                  f"  ->  frame {frame:<4} PA 0x{pa:09X}   {path}")
        return pa

    def effective_access_time(self, tlb_ns: float = 1.0, mem_ns: float = 100.0) -> float:
        total = self.stats["tlb_hit"] + self.stats["tlb_miss"]
        if total == 0:
            return 0.0
        h = self.stats["tlb_hit"] / total
        return h * (tlb_ns + mem_ns) + (1 - h) * (tlb_ns + 3 * mem_ns)


# --------------------------------------------------------------------------

def demo() -> None:
    geo = MemoryGeometry()
    print(geo.report())

    print()
    print("=" * 78)
    print(" CO3.1  LIVE ADDRESS TRANSLATION TRACE (two-level walk + 64-entry TLB)")
    print("=" * 78)
    mmu = TwoLevelMMU(geo)
    # A hot code page referenced repeatedly, plus a strided scan of a database
    # buffer that deliberately crosses into a second outer-table entry.
    trace = [0x0000000, 0x0000ABC, 0x0001000, 0x0000ABC,
             0x0400000, 0x0400FFF, 0x0401000, 0x0400010,
             0x07FF000, 0x07FFFFF, 0x0000ABC, 0x0400010]
    for va in trace:
        mmu.translate(va, verbose=True)

    s = mmu.stats
    hit_pct = s["tlb_hit"] / s["translations"] * 100
    print()
    print(f"   Translations        : {s['translations']}")
    print(f"   TLB hits / misses   : {s['tlb_hit']} / {s['tlb_miss']}   (hit ratio {hit_pct:.1f}%)")
    print(f"   Page faults         : {s['page_fault']}")
    print(f"   Physical memory refs: {s['memory_reads']}")
    print(f"   Effective access time (TLB 1 ns, RAM 100 ns) : "
          f"{mmu.effective_access_time():.2f} ns")
    print("   With no TLB at all, every reference costs 3 x 100 = 300.00 ns")
    print("   -> the sub-millisecond translation latency required by Section D is met")
    print("      by four orders of magnitude; the design constraint is not latency")
    print("      but page-table residency, which the two-level split addresses.")

    print()
    print("=" * 78)
    print(" CO3.1  4 KB PAGES vs 2 MB HUGEPAGES for the 128 MB working set")
    print("=" * 78)
    for name, psz in (("4 KB pages", 4 * KB), ("2 MB hugepages", 2 * MB)):
        pages = geo.logical_as // psz
        print(f"   {name:<16}: {pages:>7,} PTEs cover 128 MB, "
              f"page tables = {pages * 4 / KB:8.2f} KB, "
              f"TLB entries needed = {pages:,}")
    print("   -> hugepages cut TLB pressure 512x for the database tier, at the cost")
    print("      of coarser reclaim granularity; recommended for the DB VMs only.")


if __name__ == "__main__":
    demo()
