#!/usr/bin/env python3
"""CloudMatrix report - Section 2 Part II: CO4 storage content."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx.shared import Pt

import build_report as B
from build_report import (FIG, SHOT, bullet, h1, h2, h3, image, mono, pagebreak,
                          para)


def part2_header(doc):
    p = doc.add_paragraph()
    r = p.add_run("PART II — FILE SYSTEMS, INODE DYNAMICS AND DISK SCHEDULING  (CO4)")
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = B.ACCENT


# ==========================================================================
def s25_file_allocation(doc):
    h2(doc, "2.5  File allocation strategies")

    h3(doc, "Method and the fourth strategy")
    para(doc,
         "The brief asks for contiguous, sequential (linked) and indexed allocation "
         "across three file classes. A fourth method — **extent-based allocation** — "
         "is included alongside them, and the reason is quantitative rather than "
         "decorative. As §2.6 shows, a 50 GB virtual disk image addressed through the "
         "classical indirect chain requires 12,814 pointer blocks. Extents describe "
         "the same file in a handful of 12-byte descriptors inside the inode itself. "
         "ext4 and XFS both abandoned indirect chains for exactly this reason, so a "
         "recommendation for CloudMatrix's largest file class that ignored extents "
         "would be historically faithful and practically wrong.")
    para(doc,
         "Eight representative files spanning all four workload classes are allocated "
         "on a 500-block device with 4 KB blocks:")
    B.table(doc,
            ["File", "Size (bytes)", "Blocks", "Tail waste", "Access pattern"],
            [("named.conf", "2,100", "1", "1,996 B", "random"),
             ("dhcpd.conf", "3,400", "1", "696 B", "random"),
             ("syslog-2026-09.log", "163,840", "40", "0", "sequential"),
             ("nginx-access.log", "245,760", "60", "0", "sequential"),
             ("tenant-db.dump", "389,120", "95", "0", "random"),
             ("guest-win11.vmdk", "491,520", "120", "0", "sequential"),
             ("guest-ubuntu.img", "368,640", "90", "0", "sequential"),
             ("backup-snapshot.tar", "286,720", "70", "0", "sequential"),
             ("*TOTAL", "*1,951,100", "*477", "*2,692 B", "—")],
            "The representative CloudMatrix file set. Internal fragmentation is 2,692 "
            "bytes and is identical under every allocation method, because it is a "
            "property of the block size rather than of the allocator.",
            widths=[1.65, 1.15, 0.7, 0.95, 1.25], size=8.6, highlight={8})

    image(doc, SHOT / "code07_allocators.png",
          "Source: the four allocators. Contiguous searches free runs, linked takes "
          "any free blocks, indexed reserves an index block, and extent takes the "
          "largest runs first — src/co4_storage/file_allocation.py, lines 113–173.",
          width=6.4, is_figure=False)

    image(doc, SHOT / "shot06_co4_allocation_tables.png",
          "Console transcript: block maps produced by each method for the full file "
          "set. results/logs/co4_1_file_allocation.log", width=6.5, is_figure=False)

    h3(doc, "Allocation summary")
    B.table(doc,
            ["Method", "Files placed", "Blocks used", "Free", "Utilisation",
             "Metadata", "Internal frag."],
            [("Contiguous", "8 / 8", "477", "23", "95.4 %", "0 B", "2,692 B"),
             ("Linked", "8 / 8", "477", "23", "95.4 %", "1,908 B", "2,692 B"),
             ("Indexed", "8 / 8", "485", "15", "97.0 %", "32,768 B", "2,692 B"),
             ("Extent (ext4-style)", "8 / 8", "477", "23", "95.4 %", "0 B", "2,692 B")],
            "Allocation outcome on an empty device. All four methods succeed; the "
            "difference is entirely in metadata overhead. Indexed spends eight whole "
            "blocks (32 KB) on index blocks, including one for a 2 KB file.",
            widths=[1.4, 0.85, 0.85, 0.55, 0.9, 0.85, 0.95], size=7.6)
    para(doc,
         "On a clean device every method looks acceptable, which is exactly why a "
         "clean device is a misleading test. The interesting behaviour appears after "
         "churn.")

    h3(doc, "External fragmentation, measured")
    para(doc,
         "Three files are deleted — syslog-2026-09.log (40 blocks), tenant-db.dump "
         "(95) and guest-ubuntu.img (90) — modelling the routine tenant turnover the "
         "scenario describes. The free-space map afterwards:")
    mono(doc,
         "free blocks : 248 of 500\n"
         "free extents: (2, 40)  (102, 95)  (317, 90)  (477, 23)\n"
         "largest run : 95 blocks\n"
         "external fragmentation index : 1 − 95/248 = 0.617")
    para(doc,
         "A new 150-block virtual disk image, rebuild-2026.vmdk, is then requested. "
         "The disk holds 248 free blocks — comfortably more than the 150 needed:")
    B.table(doc,
            ["Method", "Outcome", "Reason"],
            [("Contiguous", "*FAILED", "*Needs 150 contiguous blocks; largest free run "
              "is 95"),
             ("Linked", "Allocated", "Needs 150 blocks anywhere; contiguity is never "
              "required"),
             ("Indexed", "Allocated", "150 data blocks + 1 index block from anywhere"),
             ("Extent (ext4-style)", "Allocated",
              "Two extents: [102…196] and [317…371]")],
            "The headline storage result. Contiguous allocation refuses a request the "
            "device can clearly satisfy, purely because the free space is not "
            "adjacent. External fragmentation stated as a measurement rather than a "
            "definition.",
            widths=[1.4, 1.0, 4.05], size=8.8, highlight={0})

    image(doc, SHOT / "shot07_co4_fragmentation.png",
          "Console transcript: the free-space bitmap before and after deletion, and "
          "the allocation attempt. '#' marks an allocated block, '.' a free one — the "
          "three gaps left by deletion are directly visible. "
          "results/logs/co4_1_file_allocation.log", width=6.5, is_figure=False)

    para(doc,
         "In production, recovering from this state under contiguous allocation "
         "requires compaction: relocating live files to coalesce free space, which "
         "means reading and rewriting gigabytes while the platform is serving tenants. "
         "Linked, indexed and extent allocation all degrade gracefully instead, which "
         "is the property that actually matters for a host with constant VM churn.")

    h3(doc, "Access cost")
    para(doc,
         "The counterweight to fragmentation resistance is access cost. Reading every "
         "fourth block of the 95-block tenant-db.dump in random order:")
    B.table(doc,
            ["Method", "Sequential I/Os", "Random I/Os", "Penalty", "Why"],
            [("Contiguous", "95", "23", "1.0×", "start + offset gives direct access"),
             ("Linked", "95", "*1,035", "*45.0×", "*each access re-walks the chain from "
              "the head"),
             ("Indexed", "96", "24", "1.0×", "one index read, then direct access"),
             ("Extent", "95", "23", "1.0×", "extent map lives in the inode itself")],
            "Access cost for the random-access workload. Linked allocation is the "
            "outlier by a factor of 45, because reaching block i costs i pointer hops "
            "and there is no way to shortcut the chain.",
            widths=[1.0, 1.05, 0.9, 0.75, 2.75], size=8.6, highlight={1})

    image(doc, FIG / "fig6_allocation.png",
          "Access cost by method (left, log scale) and the growth of indirect metadata "
          "against file size (right), showing why extents replaced indirect chains.",
          width=6.5)

    h3(doc, "Recommendation by file class")
    B.table(doc,
            ["File class", "Examples", "Recommended", "Justification"],
            [("(a) Config < 4 KB", "named.conf, dhcpd.conf, resolv.conf",
              "*Inline / direct blocks",
              "One block, one I/O. An index block costs a whole extra 4 KB for a 2 KB "
              "file — 200 % overhead. ext4 inlines such files in the inode's 60-byte "
              "i_block area, costing zero data I/Os."),
             ("(b) Web logs 10–100 MB", "nginx-access.log, syslog",
              "*Indexed (single + double indirect)",
              "Append-heavy, read sequentially, occasionally grepped at random "
              "offsets. Indexed gives O(1) random reach for ~0.1 % metadata overhead "
              "and grows without needing contiguous space."),
             ("(c) VM images > 50 GB", "guest-win11.vmdk, guest-ubuntu.img",
              "*Extent-based (ext4 / XFS)",
              "A 50 GB file is 13,107,200 blocks; a classical index needs 12,814 "
              "metadata blocks. Four extents describe it in 48 bytes inside the inode "
              "and keep the layout sequential for streaming reads.")],
            "Allocation recommendation per file class. No single method wins across "
            "all three, which is the substantive finding.",
            widths=[1.25, 1.35, 1.35, 2.55], size=7.2)
    para(doc,
         "**No single strategy wins.** That is not a hedge; it is the result. The "
         "correct design is a file system that switches strategy by file size, which "
         "is precisely what ext4 does — inline data for tiny files, indirect or extent "
         "mapping for medium ones, and extents for large ones. CloudMatrix should "
         "adopt ext4 with the extent and inline_data features enabled rather than "
         "pick a single textbook method and live with its worst case.")


# ==========================================================================
def s26_inode(doc):
    h2(doc, "2.6  UNIX inode dynamics and kernel system calls")

    h3(doc, "Inode structure and addressing reach")
    para(doc,
         "The System V inode holds ten direct block pointers, one single-indirect, one "
         "double-indirect and one triple-indirect pointer. With 4 KB blocks and 4-byte "
         "pointers, an indirect block holds 1,024 pointers, giving:")
    B.table(doc,
            ["Pointer tier", "Blocks reachable", "Bytes addressable",
             "Disk reads (cold)"],
            [("10 direct", "10", "40 KB", "1"),
             ("1 single indirect", "1,024", "4.000 MB", "2"),
             ("1 double indirect", "1,048,576", "4.000 GB", "3"),
             ("1 triple indirect", "1,073,741,824", "4.000 TB", "4"),
             ("*MAXIMUM FILE SIZE", "*1,074,791,434", "*4.004 TB", "—")],
            "Inode addressing reach. The asymmetry is deliberate: almost every real "
            "file fits in the ten direct pointers and costs one read, while the rare "
            "enormous file remains addressable at four reads per block.",
            widths=[1.5, 1.45, 1.35, 1.2], size=8.8, highlight={4})

    image(doc, SHOT / "code08_inode_reach.png",
          "Source: reach arithmetic, bmap() tier selection and the metadata cost "
          "calculation — src/co4_storage/inode_fs.py, lines 44–102.",
          width=6.4, is_figure=False)


    h3(doc, "The cost of a large VM image")
    para(doc,
         "The design is elegant for small files and expensive for large ones. Applying "
         "it to CloudMatrix's actual file mix:")
    B.table(doc,
            ["File", "Data blocks", "Indirect blocks", "Metadata overhead",
             "Cold reads per block"],
            [("named.conf (2 KB)", "1", "0", "0.000 %", "1"),
             ("nginx-access.log (80 MB)", "20,480", "21", "0.103 %", "2–3"),
             ("guest-ubuntu.img (8 GB)", "2,097,152", "2,051", "0.098 %", "3–4"),
             ("guest-win11.vmdk (50 GB)", "*13,107,200", "*12,814", "0.098 %", "*4")],
            "Metadata cost across the file mix. The percentage stays small, but the "
            "absolute figure — 12,814 blocks, 50 MB of pure pointers — is the number "
            "that matters, because that metadata must itself be cached.",
            widths=[1.85, 1.1, 1.1, 1.15, 1.3], size=8.6, highlight={3})
    para(doc,
         "Reaching one data block at the far end of that image costs four physical "
         "reads on a cold cache: the triple-indirect block, a second-level block, a "
         "bottom-level block, and finally the data. **This is the quantitative case "
         "for extents.** A single 12-byte extent descriptor covers up to 128 MB "
         "contiguously, so a well-laid-out 50 GB image needs only a few hundred "
         "descriptors, most of which fit in the inode itself.")

    h3(doc, "Kernel system calls traced through a guest lifecycle")
    para(doc,
         "The brief asks for a step-by-step trace of ialloc, ifree, namei, alloc and "
         "free during guest VM creation and deletion. Rather than describe them, a "
         "miniature System V file system implements them and logs every call. The "
         "super-block's free-inode cache is modelled properly, including the rescan "
         "when it empties — the detail that makes ialloc more than a counter.")

    image(doc, SHOT / "code09_kernel_calls.png",
          "Source: ialloc() draws from the super-block free-inode cache and rescans "
          "when it empties; ifree() releases data blocks, indirect blocks and the "
          "inode — src/co4_storage/inode_fs.py, lines 167–215.",
          width=6.4, is_figure=False)


    para(doc, "The four phases of the traced lifecycle:")
    B.table(doc,
            ["Phase", "Operation", "Kernel calls observed", "Outcome"],
            [("1", "Create /var/lib/cloudmatrix and the guest image",
              "ialloc × 6, alloc × 16, mkdir × 3",
              "inode 5 = guest-tenant7.img, 14 data blocks + 1 single-indirect block"),
             ("2", "Resolve the image path",
              "namei — 4 components",
              "5 physical I/Os cold, 1 warm via the dentry cache"),
             ("3", "Offboard the tenant (unlink)",
              "unlink, ifree, free × 15",
              "link count → 0; 15 blocks reclaimed (496 → 511 free)"),
             ("4", "Look the file up again",
              "namei — fails at the last component",
              "ENOENT; no stale pointer survives")],
            "Traced guest VM create/delete cycle. Phase 4 is the safety check: after "
            "ifree the block map is gone and the inode is back on the free list.",
            widths=[0.45, 1.85, 1.5, 2.65], size=7.4)

    image(doc, SHOT / "shot09_co4_syscall_trace.png",
          "Console transcript: the complete kernel-call trace. Note the super-block "
          "cache refill at scan #2 when the four-entry window empties, and block 10 "
          "being promoted to the single-indirect block when the file crosses the "
          "ten-direct-pointer limit. results/logs/co4_2_inode_fs.log",
          width=6.5, is_figure=False)

    para(doc,
         "Two details in that trace are worth drawing out. First, the file needed "
         "**15 blocks to hold 14 blocks of data**: crossing the direct-pointer limit "
         "silently costs a metadata block, which is invisible to the user and visible "
         "in the free-space accounting. Second, ifree released exactly those 15 "
         "blocks — the test suite asserts this, because releasing the data blocks and "
         "leaking the indirect block is one of the classic file-system bugs and it "
         "would be undetectable without the check.")

    h3(doc, "Buffer cache dynamics")
    para(doc,
         "The buffer cache sits between the file system and the disk, holding recently "
         "used blocks under LRU with delayed write. Its behaviour is measured over a "
         "20,000-operation trace shaped like CloudMatrix's real mix: 40 % hot metadata, "
         "22 % directory blocks, 18 % log appends, and 20 % streaming reads of VM "
         "images across a 59,000-block region.")
    B.table(doc,
            ["Cache size", "Cache MB", "Hits", "Misses", "Hit ratio",
             "Physical writes"],
            [("16", "0.06", "1,721", "18,279", "8.61 %", "3,564"),
             ("64", "0.25", "5,730", "14,270", "28.65 %", "3,414"),
             ("256", "1.00", "11,310", "8,690", "56.55 %", "2,586"),
             ("512", "2.00", "13,696", "6,304", "68.48 %", "1,583"),
             ("1024", "4.00", "15,389", "4,611", "*76.94 %", "*469"),
             ("2048", "8.00", "15,671", "4,329", "78.35 %", "243")],
            "Buffer cache hit ratio and write coalescing against cache size. The "
            "achievable ceiling is about 80 %, because 20 % of the trace streams an "
            "uncacheable region.",
            widths=[0.9, 0.85, 0.95, 0.95, 0.95, 1.3], size=8.6, highlight={4})

    image(doc, FIG / "fig5_buffer_cache.png",
          "Hit ratio and physical writes against cache size. The write curve is the "
          "quieter result: delayed write cuts physical writes 7.6× between 16 and "
          "1,024 buffers.", width=6.2)


    para(doc,
         "Reading the curve carefully changes the recommendation. **1,024 buffers "
         "(4 MB) reach 76.9 %, which is 96 % of everything achievable**; doubling the "
         "cache again buys 1.4 percentage points for another 4 MB. The residual misses "
         "are not a cache-sizing problem at all — they are 20 % of the trace streaming "
         "a region no cache can hold. The correct fix is therefore **O_DIRECT on VM "
         "image I/O**, so that streaming traffic stops evicting the metadata that does "
         "cache well, rather than buying more cache that cannot help.")
    para(doc,
         "The write column carries the reliability trade-off. Delayed write means a "
         "block modified many times reaches the platter once — physical writes fall "
         "from 3,564 to 469, a 7.6× reduction. It also means any block still dirty at "
         "the moment of a crash is lost. That is exactly the tension fsync() and the "
         "journal exist to arbitrate, and it is why the libvirt domain in §2.11 sets "
         "cache='none' for guest disks: a guest that calls fsync() must reach real "
         "stable storage, not stop in the host's page cache.")


# ==========================================================================
def s27_disk(doc):
    h2(doc, "2.7  Disk head movement and scheduling")

    h3(doc, "The specified problem")
    mono(doc,
         "disk       : 500 cylinders, numbered 0 – 499\n"
         "queue      : 86, 147, 312, 91, 177, 48, 409, 22, 130, 365, 220, 480\n"
         "head start : cylinder 125, moving towards higher cylinders\n"
         "seek model : 0.5 ms settle + 0.01 ms per cylinder")
    para(doc,
         "Six algorithms are evaluated. Five are named in the brief; **C-LOOK** is "
         "added because it is what the Linux mq-deadline scheduler actually "
         "approximates, and a recommendation for a Linux host that omitted it would be "
         "unsupported.")

    image(doc, SHOT / "code11_schedulers.png",
          "Source: all six schedulers. Each returns the full service path including "
          "the starting head position, so total movement is computed identically for "
          "every algorithm — src/co4_storage/disk_scheduling.py, lines 40–88.",
          width=6.4, is_figure=False)

    h3(doc, "Results on the static queue")
    B.table(doc,
            ["Algorithm", "Total head movement", "Average seek", "Seek time",
             "Worst wait", "vs FCFS"],
            [("FCFS", "*2,197 cyl", "183.08", "27.97 ms", "2,197 cyl", "—"),
             ("SSTF", "*813 cyl", "*67.75", "14.13 ms", "813 cyl", "−63.0 %"),
             ("SCAN", "851 cyl", "70.92", "15.01 ms", "851 cyl", "−61.3 %"),
             ("C-SCAN", "964 cyl", "80.33", "16.64 ms", "964 cyl", "−56.1 %"),
             ("LOOK", "*813 cyl", "*67.75", "14.13 ms", "813 cyl", "−63.0 %"),
             ("C-LOOK", "882 cyl", "73.50", "14.82 ms", "882 cyl", "−59.9 %")],
            "Total head movement on the specified queue. Every figure was verified "
            "against an independent hand calculation in the test suite.",
            widths=[0.95, 1.4, 0.95, 0.9, 0.95, 0.85], size=8.8, highlight={0, 1, 4})

    para(doc, "The service orders, for verification:")
    mono(doc,
         "FCFS   125→86→147→312→91→177→48→409→22→130→365→220→480\n"
         "       39+61+165+221+86+129+361+387+108+235+145+260 = 2197\n\n"
         "SSTF   125→130→147→177→220→312→365→409→480→91→86→48→22\n"
         "       5+17+30+43+92+53+44+71+389+5+38+26 = 813\n\n"
         "SCAN   125→130→147→177→220→312→365→409→480→499→91→86→48→22\n"
         "       5+17+30+43+92+53+44+71+19+408+5+38+26 = 851\n\n"
         "C-SCAN 125→130→…→480→499→0→22→48→86→91\n"
         "       5+17+30+43+92+53+44+71+19+499+22+26+38+5 = 964\n\n"
         "LOOK   125→130→147→177→220→312→365→409→480→91→86→48→22 = 813\n"
         "C-LOOK 125→130→…→480→22→48→86→91 = 882",
         size=7.2)

    image(doc, FIG / "fig3_disk_static.png",
          "Total seek distance (left) and the actual head trajectory of each algorithm "
          "(right). FCFS's zig-zag across the platter is visually obvious; the sweep "
          "algorithms trace a single pass.", width=6.5)

    image(doc, SHOT / "shot11_co4_disk_static.png",
          "Console transcript: service order and head movement, computed term by term. "
          "results/logs/co4_3_disk_scheduling.log", width=6.5, is_figure=False)


    h3(doc, "Two results worth pausing on")
    para(doc,
         "**SSTF and LOOK tie at exactly 813 cylinders.** This is not a coincidence "
         "and it is not a bug. On this queue, greedily choosing the nearest request "
         "happens to trace the same path as sweeping upward and then reversing, "
         "because the requests above the head are dense and those below are all "
         "further away than the next request above. The two algorithms agree here and "
         "diverge sharply under continuous arrivals — which is the whole reason for "
         "§2.7.4.")
    para(doc,
         "**C-SCAN is worse than SCAN on total movement** (964 against 851), because "
         "the return sweep to cylinder 0 is counted as head movement. That convention "
         "is stated explicitly in the code and in the results table, since some texts "
         "exclude the jump and report 465. C-SCAN is not chosen for total distance; it "
         "is chosen for uniform waiting time, which the next table quantifies.")

    h3(doc, "Fairness on the static queue")
    B.table(doc,
            ["Algorithm", "Wait spread (max − min)", "Reading"],
            [("SSTF", "808 cyl", "Low, but see the dynamic experiment"),
             ("LOOK", "808 cyl", "Low"),
             ("SCAN", "846 cyl", "Low"),
             ("C-LOOK", "877 cyl", "Uniform by construction"),
             ("C-SCAN", "959 cyl", "Most uniform treatment of far cylinders"),
             ("FCFS", "*2,158 cyl", "*Wildly unfair — cylinder 480 waits for the "
              "entire queue")],
            "Wait spread as a proxy for unfairness. On a static queue SSTF looks fair, "
            "because the queue drains. That impression does not survive continuous "
            "arrivals.",
            widths=[1.1, 1.6, 3.75], size=8.6, highlight={5})

    h3(doc, "2.7.4  The dynamic-arrival experiment")
    para(doc,
         "A static queue cannot demonstrate starvation, because it always drains no "
         "matter how unfairly it is ordered. Since the brief's scenario describes a "
         "continuously loaded platform, a second experiment was built: an event-driven "
         "simulation with 4,000 Poisson arrivals at 88 % device utilisation, where "
         "85 % of requests cluster in a drifting hot band (VM image streaming) and "
         "15 % scatter across the whole platter (metadata, syslog, backups).")

    image(doc, SHOT / "code12_dynamic_sim.png",
          "Source: the sweep scheduler with platter-edge waypoints. Modelling the ride "
          "to the edge is what makes SCAN and LOOK genuinely different rather than "
          "accidentally identical — src/co4_storage/disk_dynamic_experiment.py, "
          "lines 77–122.", width=6.4, is_figure=False)

    B.table(doc,
            ["Algorithm", "Mean", "Median", "p95", "p99", "Maximum", "Total seek"],
            [("FCFS", "44.6 ms", "24.0", "118.1", "*124.3", "133.9", "266,623"),
             ("SSTF", "*5.2 ms", "3.5", "14.6", "27.9", "*71.2", "193,717"),
             ("SCAN", "12.3 ms", "10.8", "27.0", "36.7", "54.6", "254,927"),
             ("C-SCAN", "10.5 ms", "8.8", "24.7", "31.3", "49.9", "234,695"),
             ("LOOK", "6.0 ms", "4.3", "16.2", "*23.7", "40.3", "*193,217"),
             ("C-LOOK", "7.1 ms", "5.0", "19.4", "28.2", "*40.1", "203,923")],
            "Response-time distribution under continuous arrivals at 88 % load. "
            "Measuring the distribution rather than the mean is what exposes the "
            "trade-off.",
            widths=[0.95, 0.8, 0.75, 0.65, 0.7, 0.85, 1.0], size=8.6,
            highlight={0, 1})

    B.table(doc,
            ["Algorithm", "Cold-request mean", "Cold-request worst",
             "Tail ratio (max/mean)", "Fairness verdict"],
            [("FCFS", "46.4 ms", "133.9 ms", "3.0", "Bounded but uniformly terrible"),
             ("SSTF", "9.6 ms", "*71.2 ms", "*13.6", "*STARVATION"),
             ("SCAN", "15.2 ms", "47.9 ms", "4.4", "Bounded"),
             ("C-SCAN", "11.7 ms", "49.9 ms", "4.7", "Bounded"),
             ("LOOK", "7.5 ms", "40.3 ms", "6.7", "Acceptable"),
             ("C-LOOK", "8.6 ms", "*32.8 ms", "*5.7", "*Bounded — best worst case")],
            "Starvation profile of the far-edge 'cold' requests. SSTF's low mean is "
            "purchased by deferring exactly the requests that are furthest away.",
            widths=[0.95, 1.25, 1.25, 1.3, 1.75], size=8.6, highlight={1, 5})

    image(doc, FIG / "fig4_disk_dynamic.png",
          "Latency distribution at 88 % load (left) and p99 against offered load "
          "(right). The algorithms are nearly indistinguishable at light load and "
          "separate sharply at saturation.", width=6.5)

    image(doc, SHOT / "shot13_co4_disk_dynamic.png",
          "Console transcript: the dynamic experiment and the load-sensitivity sweep. "
          "results/logs/co4_3b_disk_dynamic.log", width=6.5, is_figure=False)

    h3(doc, "Load sensitivity")
    B.table(doc,
            ["Offered rate", "Load", "FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK",
             "C-LOOK"],
            [("0.15 req/ms", "24 %", "8.1", "7.4", "15.9", "15.0", "7.6", "8.3"),
             ("0.25 req/ms", "40 %", "10.9", "9.6", "18.8", "17.0", "9.8", "10.7"),
             ("0.35 req/ms", "56 %", "14.8", "12.1", "24.0", "20.4", "12.7", "14.6"),
             ("0.45 req/ms", "72 %", "25.3", "16.3", "28.1", "24.7", "16.4", "18.8"),
             ("0.55 req/ms", "88 %", "*122.7", "29.9", "40.0", "32.6", "*23.1",
              "27.9")],
            "p99 response time (ms) against offered load. At light load the choice "
            "barely matters; at saturation FCFS degrades 15× while LOOK degrades 3×.",
            widths=[1.1, 0.55, 0.75, 0.7, 0.7, 0.75, 0.7, 0.75], size=8.6,
            highlight={4})
    para(doc,
         "This sweep is the most useful single table in the storage study, because it "
         "shows that an algorithm comparison performed at the wrong load point would "
         "have reached the wrong conclusion. At 24 % load FCFS (8.1 ms) beats SCAN "
         "(15.9 ms) and one might reasonably ship it. At 88 % load — the regime the "
         "brief specifies — FCFS collapses to 122.7 ms while LOOK degrades gracefully "
         "to 23.1 ms. **Algorithms must be compared in the regime where they will "
         "actually run.**")


# ==========================================================================
def s28_io_arch(doc):
    h2(doc, "2.8  I/O system architecture")
    para(doc,
         "The block layer that the scheduler sits in is one of two device families the "
         "kernel maintains, and the distinction determines which structure a driver "
         "registers with.")
    B.table(doc,
            ["Aspect", "Block devices", "Character devices"],
            [("Access unit", "Fixed-size blocks (4 KB here)", "Byte stream"),
             ("Addressing", "Random, by block number", "Usually sequential"),
             ("Buffering", "Through the buffer / page cache", "Typically unbuffered"),
             ("Scheduler", "Yes — merging and reordering (C-LOOK / mq-deadline)",
              "No reordering; ordering is semantic"),
             ("Switch table", "bdevsw — block device switch",
              "cdevsw — character device switch"),
             ("Kernel entry points", "open, close, strategy, size",
              "open, close, read, write, ioctl"),
             ("CloudMatrix examples", "/dev/sda, /dev/nvme0n1, LVM volumes, .qcow2 "
              "backing files", "/dev/tty, /dev/random, /dev/net/tun for guest vNICs"),
             ("Failure mode if confused", "Reordering corrupts write ordering",
              "Buffering breaks interactive latency")],
            "Block versus character devices and their switch tables.",
            widths=[1.35, 2.6, 2.55], size=7.4)
    para(doc,
         "The switch tables are the indirection that makes the kernel extensible: "
         "bdevsw and cdevsw are arrays indexed by major device number, each entry "
         "holding function pointers into a driver. Opening /dev/sda dispatches through "
         "bdevsw[major].d_open without the file system knowing anything about SATA. "
         "**Streams** generalise the character path into a stack of pushable "
         "processing modules, which is how TTY line discipline and network protocol "
         "processing are composed.")
    para(doc,
         "For CloudMatrix the practical consequence is direct. A guest's virtual disk "
         "is a block device and therefore inherits the host's scheduler — which is why "
         "the C-LOOK recommendation in §2.7 applies to guest I/O and not merely to the "
         "host's own. A guest's virtual NIC is a character device (/dev/net/tun) and "
         "is not reordered, which is why network fairness has to be enforced by the "
         "traffic-shaping parameters in the domain XML rather than by the I/O "
         "scheduler.")
