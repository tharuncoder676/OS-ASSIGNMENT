#!/usr/bin/env python3
"""CloudMatrix report - Section 2 Part I: CO3 memory management content."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_report as B
from docx.shared import Pt

from build_report import (FIG, SHOT, bullet, h1, h2, h3, image, mono, pagebreak,
                          para, table)


def section2_intro(doc):
    h1(doc, "Application of Course Knowledge", 2)
    para(doc,
         "This section answers the technical questions of the brief in the order it "
         "poses them. Part I covers memory management and virtual memory (CO3), "
         "Part II covers file systems, inode dynamics and disk scheduling (CO4), and "
         "Part III covers Linux administration, network services and virtualization "
         "(CO5). Every quantitative claim is followed by the console transcript that "
         "produced it and a pointer to the module and log file in the repository.")

    p = doc.add_paragraph()
    r = p.add_run("PART I — MEMORY MANAGEMENT, PAGING AND VIRTUAL MEMORY  (CO3)")
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = B.ACCENT


# ==========================================================================
def s21_page_table(doc):
    h2(doc, "2.1  Memory layout and two-level page table design")

    h3(doc, "Deriving the geometry")
    para(doc,
         "Everything downstream depends on four numbers, so they are derived rather "
         "than assumed. With 32 GB of physical memory and a 4 KB frame:")
    mono(doc,
         "physical frames  = 32 GB / 4 KB = 2^35 / 2^12 = 2^23 = 8,388,608 frames\n"
         "virtual pages    = 128 MB / 4 KB = 2^27 / 2^12 = 2^15 =    32,768 pages\n"
         "virtual address  = 27 bits  =  p (15 bits)  |  d (12 bits)\n"
         "physical address = 35 bits  =  f (23 bits)  |  d (12 bits)")
    para(doc,
         "A single-level page table for one process would therefore hold 32,768 "
         "entries of 4 bytes each — 128 KB, resident whether or not the process ever "
         "touches those pages. Across 1,200 guests that is 150 MB of physical memory "
         "spent on mostly-empty bookkeeping, which is why the brief asks for a "
         "multi-level design.")

    h3(doc, "Choosing the split")
    para(doc,
         "The 15-bit page number has to be divided between an outer and an inner "
         "index, and the division is not arbitrary. The standard technique is to size "
         "the inner table so that it occupies exactly one frame, because a table that "
         "fits in a page can itself be paged out. With 4-byte entries, one 4 KB frame "
         "holds 1,024 entries, so the inner index is log₂(1024) = 10 bits and the "
         "outer index takes the remaining 5 bits:")
    mono(doc,
         "| p1 = 5 bits |   p2 = 10 bits   |        d = 12 bits        |\n"
         "  outer index    inner index                offset\n"
         "  32 entries     1,024 entries              4,096 bytes\n"
         "  = 128 bytes    = 4 KB (one frame)")
    para(doc,
         "The saving is the point. A process that has touched only one region of its "
         "address space needs the 128-byte outer table plus a single 4 KB inner "
         "table — **4 KB in total against 128 KB for the flat design, a 32× "
         "reduction**. Across 1,200 sessions the resident page-table cost falls from "
         "150.00 MB to 4.83 MB. That reclaimed 145 MB is not a rounding error; it is "
         "roughly nine additional web-tier guests.")

    image(doc, FIG / "fig07_address_translation.png",
          "Two-level address translation on the CloudMatrix host. The TLB short-"
          "circuits the walk on 58.3 % of references in the measured trace; a miss "
          "costs two table reads before the datum, and an invalid entry costs an 8 ms "
          "page fault.", width=6.5)

    h3(doc, "Verifying the design by executing it")
    para(doc,
         "A bit-split written on paper is easy to get wrong, so it is implemented and "
         "run. The MemoryGeometry class derives every constant above from the four "
         "input parameters, and TwoLevelMMU performs real translations through a "
         "64-entry TLB, reporting where each reference was resolved.")

    image(doc, SHOT / "code01_page_table_geometry.png",
          "Source: MemoryGeometry derives frames, pages and the bit split from the "
          "host parameters — src/co3_memory/page_table.py, lines 32–74.",
          width=6.4, is_figure=False)

    image(doc, SHOT / "code02_mmu_translate.png",
          "Source: the two-level walk with TLB refill and demand-paging on an invalid "
          "entry — src/co3_memory/page_table.py, lines 139–178.",
          width=6.4, is_figure=False)

    image(doc, SHOT / "shot01_co3_page_table.png",
          "Console transcript: derived geometry and the live translation trace. "
          "Note that offsets pass through translation unchanged (0xABC in, 0xABC out) "
          "and that both references into page p1=1, p2=0 resolve to the same frame — "
          "two properties the test suite asserts independently. "
          "results/logs/co3_1_page_table.log", width=6.5, is_figure=False)

    h3(doc, "Effective access time")
    para(doc,
         "With a 1 ns TLB probe and 100 ns DRAM, a hit costs one memory reference and "
         "a miss costs three — the outer table, the inner table, and finally the "
         "datum. On the measured trace:")
    mono(doc,
         "EAT = 0.583 × (1 + 100) + 0.417 × (1 + 300)  =  184.33 ns\n"
         "without any TLB : 3 × 100                    =  300.00 ns")
    para(doc,
         "The brief asks for sub-millisecond translation latency. At 184 ns the design "
         "clears that bar by more than three orders of magnitude, which is worth "
         "stating plainly: **translation latency is not the binding constraint on this "
         "host**. The binding constraint is page-table residency and, beyond it, the "
         "8 ms cost of a fault that has to reach the swap device. Optimising the wrong "
         "one of those would be effort spent for no measurable benefit.")

    h3(doc, "Hugepages for the database tier")
    para(doc,
         "Covering a 128 MB working set with 4 KB pages needs 32,768 page-table "
         "entries and, worse, 32,768 distinct TLB entries. With 2 MB hugepages the "
         "same span needs 64. That is a 512× reduction in TLB pressure, which matters "
         "enormously for a database guest whose access pattern defeats locality, and "
         "matters not at all for a 16 MB web guest.")
    B.table(doc,
            ["Page size", "PTEs to cover 128 MB", "Page-table bytes", "TLB entries",
             "Recommended for"],
            [("4 KB", "32,768", "128.00 KB", "32,768",
              "Web / DNS and enterprise tiers"),
             ("2 MB hugepage", "64", "0.25 KB", "64",
              "Database guest VMs only")],
            "Hugepages are recommended selectively. They cut TLB pressure 512× but "
            "coarsen reclaim granularity, which would fight the balloon driver on the "
            "tiers that need fine-grained reclaim.",
            widths=[0.95, 1.5, 1.15, 0.9, 2.0], size=7.6)


# ==========================================================================
def s22_allocation(doc):
    h2(doc, "2.2  Dynamic storage allocation and dynamic linking")

    h3(doc, "The placement problem")
    para(doc,
         "When a guest is admitted, the hypervisor must find a hole in host memory "
         "large enough for its reservation. After a day of guests starting and "
         "stopping, host free memory is not one block but a list of holes. The "
         "experiment models a 32 GB host whose free list has been left in exactly that "
         "state, and pushes seven queued guest reservations through First-Fit, "
         "Best-Fit and Worst-Fit.")
    mono(doc,
         "free holes (MB) : [1200, 3400, 512, 2800, 900, 6100, 1500, 4200]  "
         "total 20,612 MB\n"
         "queued demand   : 850 + 4096 + 256 + 2900 + 1400 + 1100 + 3300 "
         "= 13,902 MB")



    h3(doc, "What the measurement shows")
    B.table(doc,
            ["Policy", "Guests placed", "Rejected", "Largest hole left",
             "Stranded < 256 MB", "Search cost"],
            [("First-Fit", "7 / 7", "0", "2,004 MB", "*94 MB", "O(1) amortised"),
             ("Best-Fit", "7 / 7", "0", "2,800 MB", "354 MB", "O(n) full scan"),
             ("Worst-Fit", "6 / 7", "*1", "2,000 MB", "0 MB", "O(n) full scan")],
            "Placement policy comparison. Worst-Fit is the only policy that fails to "
            "place a guest; Best-Fit succeeds but strands 3.8× more memory in holes "
            "too small to host anything.",
            widths=[0.95, 1.05, 0.75, 1.25, 1.25, 1.25], size=8.6, highlight={2})

    para(doc,
         "Three observations follow, and the second is the one that is usually stated "
         "backwards in textbooks.")
    bullet(doc, "**Best-Fit's virtue is its vice.** By always choosing the tightest "
                "hole it leaves the smallest possible remainder, and a remainder of "
                "50 MB or 100 MB cannot host any CloudMatrix guest — the smallest is "
                "256 MB. Best-Fit therefore manufactures unusable memory: 354 MB "
                "stranded against First-Fit's 94 MB.")
    bullet(doc, "**Worst-Fit fails outright.** It preserves large holes in principle, "
                "but it does so by consuming the biggest hole first, every time. By "
                "the seventh request the 6,100 MB hole has been eaten down to 1,044 MB "
                "and the 3,300 MB analytics guest has nowhere to go — even though "
                "10,010 MB remains free in aggregate. Preserving large holes and "
                "consuming large holes first are contradictory goals.")
    bullet(doc, "**First-Fit wins on the metric that was not being measured.** It "
                "places as many guests as Best-Fit and strands a quarter as much "
                "memory, and it does so without scanning the whole free list. VM "
                "admission is on a hot path; search cost is not free.")
    para(doc,
         "**Selected policy: First-Fit**, with the free list kept in address order and "
         "adjacent holes coalesced on release. Address-ordered First-Fit tends to "
         "concentrate allocations at low addresses and leave larger contiguous space "
         "at high addresses, which is exactly the shape that helps the next large "
         "guest.")

    h3(doc, "Dynamic linking and shared libraries")
    para(doc,
         "The second half of the memory-footprint problem is solved before the "
         "allocator ever sees it. Every guest in the fleet links the same handful of "
         "shared objects. If each linked them statically, each would carry a private "
         "copy in physical memory.")
    B.table(doc,
            ["Library", "Size", "Static × 1,200 guests", "Dynamically linked"],
            [("libc.so.6", "2.1 MB", "2,520 MB", "2.1 MB"),
             ("libssl.so.3", "1.4 MB", "1,680 MB", "1.4 MB"),
             ("libcrypto.so.3", "4.8 MB", "5,760 MB", "4.8 MB"),
             ("libstdc++.so.6", "2.2 MB", "2,640 MB", "2.2 MB"),
             ("libpython3.12.so", "6.4 MB", "7,680 MB", "6.4 MB"),
             ("*TOTAL", "*16.9 MB", "*20,280 MB  (19.8 GB)", "*16.9 MB")],
            "Shared-library footprint. Statically linked guests would need more memory "
            "for libraries alone (19.8 GB) than the host has left after the "
            "hypervisor reserve.",
            widths=[1.55, 0.95, 1.85, 1.55], size=8.6, highlight={5})
    para(doc,
         "The mechanism is worth stating precisely because the saving depends on it: "
         "the dynamic loader maps one physical copy of each object into every address "
         "space read-only and shared, and only the writable GOT, PLT and .data pages "
         "are private and copy-on-write. The **99.92 % saving** is therefore real "
         "physical memory, not an accounting trick — and without it this workload "
         "would not fit on this host at all.")


# ==========================================================================
def s23_replacement(doc):
    h2(doc, "2.3  Page replacement and Belady's anomaly")

    h3(doc, "The reference string")
    para(doc,
         "The brief asks for a trace of at least sixteen references. The CloudMatrix "
         "trace W has eighteen references over seven distinct pages, and it is "
         "constructed to represent a plausible guest execution rather than a random "
         "sequence:")
    mono(doc,
         "W = 2, 3, 4, 5, 2, 3, 1, 2, 3, 4, 5, 1, 6, 7, 6, 7, 6, 7\n\n"
         "pages 2–5 : enterprise application text and data pages\n"
         "page  1   : a shared libc page brought in late by the dynamic loader\n"
         "pages 6,7 : the batch-analytics scan phase, beginning at reference 13")
    para(doc,
         "The structure matters. The first twelve references cycle through a working "
         "set slightly larger than the frame allocation, which is the condition under "
         "which replacement policy actually decides anything. The last six references "
         "shift to a new locality, modelling the phase change that happens when a "
         "guest moves from serving requests to running a batch job.")

    image(doc, SHOT / "code04_replacement.png",
          "Source: FIFO evicts by arrival order, LRU by recency — the only difference "
          "is whether a hit reorders the list. src/co3_memory/page_replacement.py, "
          "lines 52–96.", width=6.4, is_figure=False)

    image(doc, SHOT / "code05_optimal.png",
          "Source: OPTIMAL evicts the resident page whose next use is furthest away, "
          "which requires knowledge of the future and therefore serves as a lower "
          "bound rather than an implementable policy. "
          "src/co3_memory/page_replacement.py, lines 97–128.",
          width=6.4, is_figure=False)

    h3(doc, "Results")
    B.table(doc,
            ["Algorithm", "Faults (3 frames)", "Faults (4 frames)", "Change",
             "Fault rate (4f)", "Hit ratio (4f)"],
            [("FIFO", "11", "*12", "*+1  ANOMALY", "66.67 %", "33.33 %"),
             ("LRU", "12", "10", "−2  improves", "55.56 %", "44.44 %"),
             ("OPTIMAL", "9", "8", "−1  improves", "44.44 %", "55.56 %")],
            "Page faults over the 18-reference trace W. FIFO is the only policy that "
            "gets worse when given more memory.",
            widths=[1.0, 1.15, 1.15, 1.25, 1.05, 1.0], size=8.8, highlight={0})

    image(doc, FIG / "fig1_page_replacement.png",
          "Page faults and fault rate by algorithm and frame allocation. The FIFO bar "
          "rising from 11 to 12 as memory increases is Belady's anomaly.", width=6.5)

    image(doc, SHOT / "shot03_co3_belady.png",
          "Console transcript: the summary table and the explicit anomaly test. "
          "results/logs/co3_3_page_replacement.log", width=6.5, is_figure=False)

    h3(doc, "Belady's anomaly, confirmed and explained")
    para(doc,
         "FIFO produces **11 faults with three frames and 12 with four**: adding "
         "physical memory made the system measurably worse, a 9.1 % regression. This "
         "is Belady's anomaly, and it is not a bug in the simulator — the test suite "
         "asserts it as a required property of the trace, and separately asserts that "
         "LRU and OPTIMAL never exhibit it.")
    para(doc,
         "The explanation is the inclusion property. LRU and OPTIMAL are **stack "
         "algorithms**: the set of pages resident with m frames is always a subset of "
         "the set resident with m+1 frames, so any page that would have been a hit "
         "with less memory is still a hit with more. FIFO has no such property, "
         "because its eviction order depends on arrival time rather than on the "
         "reference pattern, and adding a frame changes which page is oldest at every "
         "subsequent decision point. The eviction sequence is not merely different; it "
         "is unrelated.")
    para(doc,
         "**This single result decides the policy for CloudMatrix**, and it decides it "
         "for a reason that has nothing to do with which algorithm faulted least. Note "
         "that at three frames LRU is actually *worse* than FIFO on this trace — 12 "
         "faults against 11. A comparison that stopped at the fault count would "
         "therefore recommend FIFO. But CloudMatrix's balloon driver continuously "
         "resizes each guest's frame allocation in response to host pressure, which "
         "means the memory manager must answer a question the fault count cannot: "
         "*if I give this guest another frame, will it fault less?* Under FIFO there "
         "is no guarantee that it will. Under LRU there is a proof. A control loop "
         "cannot be built on a policy whose response to its actuator is "
         "non-monotonic.")
    para(doc,
         "**Selected policy: LRU**, implemented in practice as the Linux kernel's "
         "two-list active/inactive approximation with accessed-bit sampling, since "
         "true LRU requires a timestamp update on every memory reference and no "
         "hardware provides that. The approximation preserves the stack property, "
         "which is the property that was actually being purchased.")


# ==========================================================================
def s24_working_set(doc):
    h2(doc, "2.4  Demand paging, working set and thrashing")

    h3(doc, "The working-set model")
    para(doc,
         "Denning's working set W(t, Δ) is the set of pages referenced in the last Δ "
         "references. Its size WSS is the number of frames a process needs in order "
         "not to fault continuously. Rather than assume a value, the working set is "
         "measured directly from the sliding-window definition over a "
         "locality-structured trace of 60,000 references whose true locality is eight "
         "pages, drifting every 4,000 references.")
    B.table(doc,
            ["Window Δ", "Mean WSS", "Peak WSS", "Interpretation"],
            [("10", "5.89", "8", "Too short — undercounts the locality, starves the "
              "process"),
             ("25", "7.72", "15", "Too short"),
             ("50", "8.02", "15", "Tracks the true locality"),
             ("100", "8.09", "16", "*Tracks the true locality — operating point"),
             ("250", "8.24", "16", "Tracks the true locality"),
             ("500", "8.51", "16", "Too long — absorbs stale localities"),
             ("1000", "9.03", "16", "Too long — holds dead pages resident")],
            "Measured working-set size against window width. The usable band is "
            "Δ = 50–250; the generator's true locality of eight pages is recovered "
            "correctly inside it.",
            widths=[0.8, 0.9, 0.9, 3.6], size=8.6, highlight={3})
    para(doc,
         "The window choice is a genuine engineering decision with a cost on both "
         "sides. Too small a Δ under-reports demand and starves the process; too large "
         "a Δ keeps dead pages resident and wastes frames another guest needs. "
         "Δ = 100 references is adopted, and the demand figure D = Σ WSSᵢ used "
         "throughout §2.4 is computed with it.")


    h3(doc, "The lifetime curve")
    para(doc,
         "The page-fault frequency controller steers on the curve p(f) — faults per "
         "reference as a function of frames granted. That curve is measured, not "
         "sketched:")
    B.table(doc,
            ["Frames f", "Fault rate p(f)", "CPU burst C between faults", "Regime"],
            [("2", "0.748667", "0.534 ms", "Paging-bound"),
             ("4", "0.498217", "0.803 ms", "Paging-bound"),
             ("6", "0.249033", "1.606 ms", "Paging-bound"),
             ("7", "0.125167", "3.196 ms", "Paging-bound"),
             ("8", "*0.001450", "*275.862 ms", "*CPU-bound — the knee"),
             ("12", "0.001183", "338.028 ms", "CPU-bound"),
             ("32", "0.001183", "338.028 ms", "CPU-bound (saturated)"),
             ("64", "0.001067", "375.000 ms", "CPU-bound (saturated)")],
            "Measured lifetime curve. Between f = 7 and f = 8 the fault rate falls by "
            "a factor of 86 — the knee sits exactly at the locality size.",
            widths=[0.85, 1.25, 1.9, 2.2], size=8.6, highlight={4})
    para(doc,
         "The transition is not gradual. At seven frames the process faults every "
         "eight references and its mean CPU burst is 3.2 ms — shorter than the 8 ms it "
         "takes the swap device to service one fault, so the disk becomes the "
         "bottleneck. At eight frames the working set fits, the fault rate collapses "
         "by nearly two orders of magnitude, and the mean burst rises to 276 ms. "
         "**The knee is the working-set size**, which is precisely Denning's claim, "
         "recovered here as a measurement.")

    h3(doc, "Locating the thrashing point")
    para(doc,
         "A common way to present thrashing is a hand-drawn curve of CPU utilisation "
         "that rises and then falls. That curve is real, but it does not follow from "
         "the naive independent-blocking model, which is monotonically increasing in "
         "N and can never fall. The collapse comes from the paging device saturating, "
         "so it is derived here with operational analysis. Each guest alternates a CPU "
         "burst C = (1/p) · S · t_mem with a paging service D = 8 ms. With one CPU and "
         "one paging device the asymptotic throughput bound is:")
    mono(doc,
         "X(N)  ≤  min( N / (C + D) ,  1 / max(C, D) )\n"
         "U_cpu  =  X(N) · C          U_disk  =  X(N) · D")
    para(doc,
         "As N rises, each guest's share f = M/N shrinks, p(f) climbs the lifetime "
         "curve, C collapses, and utilisation falls off a cliff.")
    B.table(doc,
            ["N guests", "Frames each", "p(f)", "C (ms)", "U_cpu", "U_disk", "State"],
            [("1", "64", "0.001067", "375.0", "0.979", "0.021", "Healthy"),
             ("4", "16", "0.001183", "338.0", "1.000", "0.024", "Healthy"),
             ("8", "8", "0.001450", "275.9", "*1.000", "0.029", "*Healthy — knee"),
             ("9", "7", "0.125167", "3.20", "*0.399", "*1.000", "*THRASHING"),
             ("10", "6", "0.249033", "1.61", "0.201", "1.000", "THRASHING"),
             ("16", "4", "0.498217", "0.80", "0.100", "1.000", "THRASHING"),
             ("32", "2", "0.748667", "0.53", "0.067", "1.000", "THRASHING")],
            "Utilisation against degree of multiprogramming. Between N = 8 and N = 9 "
            "CPU utilisation falls from 1.000 to 0.399 while the paging device pins at "
            "1.000 — the operational signature of thrashing.",
            widths=[0.75, 0.95, 0.9, 0.75, 0.7, 0.7, 1.35], size=8.4,
            highlight={2, 3})

    image(doc, FIG / "fig2_thrashing.png",
          "The measured lifetime curve (left) and the thrashing cliff (right). The "
          "crossover where the paging-device curve reaches 1.000 and the CPU curve "
          "collapses is the admission-control limit.", width=6.5)

    image(doc, SHOT / "shot04_co3_thrashing.png",
          "Console transcript: lifetime curve and utilisation sweep. "
          "results/logs/co3_4_working_set.log", width=6.5, is_figure=False)

    para(doc,
         "The machine at N = 16 is not idle. It is 100 % busy — busy paging. That is "
         "the diagnostic subtlety that makes thrashing dangerous in production: every "
         "utilisation dashboard shows a fully loaded system while throughput has "
         "fallen by a factor of ten. The distinguishing signal is the ratio, not the "
         "level: **U_disk = 1.000 with U_cpu = 0.100 is thrashing; both near 1.0 is "
         "healthy saturation.**")

    h3(doc, "Frame allocation for 1,200 sessions")
    para(doc,
         "Applying the model to the real tier mix produces an uncomfortable answer. "
         "Total demand D = 9,420,800 frames (35.94 GB) against m = 7,549,748 frames "
         "(28.80 GB) available after a 10 % hypervisor and page-cache reserve. "
         "**D/m = 1.248** — the host is 24.8 % over-committed and, allocated naively, "
         "will thrash. Three reclaim mechanisms close the gap, applied in increasing "
         "order of disruption:")
    B.table(doc,
            ["Step", "Mechanism", "Frames reclaimed", "GB", "Running D/m"],
            [("0", "Naive allocation", "—", "—", "*1.248  ✘ thrashes"),
             ("1", "KSM page sharing across 900 near-identical web guests (35 %)",
              "1,290,240", "4.92", "1.077  ✘"),
             ("2", "Balloon reclaim of cold pages in the enterprise tier (10 %)",
              "294,912", "1.12", "1.038  ✘"),
             ("3", "Suspend the batch analytics tier when PFF exceeds the upper "
              "threshold", "819,200", "3.12", "*0.929  ✔ fits")],
            "Closing a 24.8 % over-commit. The three mechanisms are ordered by "
            "disruption: sharing is invisible to guests, ballooning is nearly so, and "
            "suspension is visible but is applied only to the tier with no interactive "
            "SLA.",
            widths=[0.45, 2.85, 1.15, 0.6, 1.4], size=8.4, highlight={0, 3})


    h3(doc, "The page-fault frequency control loop")
    para(doc,
         "Static allocation cannot hold, because working sets change as guests change "
         "phase. The PFF controller adjusts allocation continuously against a band:")
    mono(doc,
         "if  PFF_i > U = 0.50 faults/ms   ->  grant guest i more frames\n"
         "if  PFF_i < L = 0.10 faults/ms   ->  balloon frames back from guest i\n"
         "if  PFF_i > U and no free frame  ->  SUSPEND the lowest-priority guest\n\n"
         "frames_i = max( WSS_i(Δ) , (size_i / Σ size) × m )   subject to Σ frames_i ≤ m")
    para(doc,
         "Two details make this a design rather than a formula. First, the allocation "
         "has a **floor at the measured working-set size**: ballooning a guest below "
         "its working set converts host memory pressure into guest thrashing, which is "
         "strictly worse than the problem it was meant to solve. Second, the victim "
         "class for suspension is fixed in advance as batch analytics, because it "
         "carries no interactive SLA. Choosing the victim at the moment of crisis, "
         "under load, is how a memory shortage becomes an outage.")
