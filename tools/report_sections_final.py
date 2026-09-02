#!/usr/bin/env python3
"""CloudMatrix report - Sections 5 to 9 and appendices."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_report as B
from build_report import (FIG, NAME, REGNO, REPO, SHOT, bullet, h1, h2, h3, image,
                          link, mono, pagebreak, para)


# ==========================================================================
def section5(doc):
    h1(doc, "Results and Validation", 5)

    h2(doc, "5.1  Consolidated results")
    para(doc,
         "Every headline number produced by the study, with the module that computed "
         "it and the log file that records it.")

    B.table(doc,
            ["#", "Result", "Value", "Source module", "Log file"],
            [("1", "Physical frames (32 GB / 4 KB)", "8,388,608 = 2²³",
              "page_table.py", "co3_1"),
             ("2", "Virtual pages (128 MB / 4 KB)", "32,768 = 2¹⁵",
              "page_table.py", "co3_1"),
             ("3", "Virtual address split", "p1=5 | p2=10 | d=12",
              "page_table.py", "co3_1"),
             ("4", "Page-table residency, flat → sparse", "128 KB → 4 KB (32×)",
              "page_table.py", "co3_1"),
             ("5", "Effective access time with TLB", "184.33 ns (vs 300 ns)",
              "page_table.py", "co3_1"),
             ("6", "Worst-Fit placement failures", "1 of 7 guests rejected",
              "dynamic_allocation.py", "co3_2"),
             ("7", "Shared-library saving", "19.8 GB (99.92 %)",
              "dynamic_allocation.py", "co3_2"),
             ("8", "Page faults, FIFO 3 → 4 frames", "11 → 12  ANOMALY",
              "page_replacement.py", "co3_3"),
             ("9", "Page faults, LRU 3 → 4 frames", "12 → 10",
              "page_replacement.py", "co3_3"),
             ("10", "Page faults, OPT 3 → 4 frames", "9 → 8",
              "page_replacement.py", "co3_3"),
             ("11", "Lifetime-curve knee", "f = 8 frames = locality size",
              "working_set.py", "co3_4"),
             ("12", "Thrashing threshold", "N = 8 guests; U 1.000 → 0.399",
              "working_set.py", "co3_4"),
             ("13", "Over-commit before / after reclaim", "D/m 1.248 → 0.929",
              "working_set.py", "co3_4"),
             ("14", "Contiguous allocation after churn",
              "REFUSED 150 blocks with 248 free", "file_allocation.py", "co4_1"),
             ("15", "Linked random-access penalty", "1,035 vs 23 I/Os (45×)",
              "file_allocation.py", "co4_1"),
             ("16", "Maximum inode-addressable file", "4.004 TB",
              "inode_fs.py", "co4_2"),
             ("17", "50 GB image indirect metadata", "12,814 blocks (50 MB)",
              "inode_fs.py", "co4_2"),
             ("18", "Blocks reclaimed by ifree()", "15 of 15 (no leak)",
              "inode_fs.py", "co4_2"),
             ("19", "Buffer cache hit ratio", "76.94 % at 1,024 buffers",
              "inode_fs.py", "co4_2"),
             ("20", "Physical writes, delayed write", "3,564 → 469 (7.6×)",
              "inode_fs.py", "co4_2"),
             ("21", "Head movement, FCFS", "2,197 cylinders",
              "disk_scheduling.py", "co4_3"),
             ("22", "Head movement, SSTF and LOOK", "813 cylinders (−63.0 %)",
              "disk_scheduling.py", "co4_3"),
             ("23", "SSTF starvation tail at 88 % load", "71.2 ms max, ratio 13.6",
              "disk_dynamic_experiment.py", "co4_3b"),
             ("24", "Best p99 at 88 % load", "LOOK 23.7 ms",
              "disk_dynamic_experiment.py", "co4_3b"),
             ("25", "FCFS degradation, 24 % → 88 % load", "8.1 → 122.7 ms (15×)",
              "disk_dynamic_experiment.py", "co4_3b"),
             ("26", "Forward/reverse DNS consistency", "15 A ↔ 15 PTR, all matched",
              "validate_co5.sh", "co5"),
             ("27", "Validation suite", "65 / 65 pass", "test_simulators.py",
              "test_results")],
            "Consolidated results. Log files are in results/logs/ with the prefix "
            "shown.",
            widths=[0.3, 2.15, 1.75, 1.5, 0.85], size=7.8)

    h2(doc, "5.2  Validation strategy")
    para(doc,
         "A simulator that produces confident nonsense is worse than no simulator, "
         "because it lends false authority to a wrong conclusion. The 65 tests check "
         "two distinct classes of claim, and the second class is the one that catches "
         "the bugs spot-checking would miss.")

    h3(doc, "Class 1 — hand-computed values")
    para(doc,
         "Numbers computed independently on paper and asserted in the test suite, so "
         "the report cannot silently drift from the code: the frame and page counts "
         "and the bit split; all six page-fault counts; all six head-movement totals; "
         "the 12,814-block metadata figure; and the 1,035-versus-24 I/O gap.")

    image(doc, SHOT / "code13_tests_disk.png",
          "Source: head-movement totals asserted against the hand calculation, plus "
          "the structural checks every scheduler must satisfy — "
          "tests/test_simulators.py, lines 236–279.", width=6.4, is_figure=False)

    h3(doc, "Class 2 — invariants that must hold for any correct implementation")
    bullet(doc, "OPTIMAL is a lower bound on every online policy. If FIFO or LRU ever "
                "beats it, OPTIMAL is wrong.")
    bullet(doc, "LRU and OPTIMAL are stack algorithms and can never regress with more "
                "frames — the property FIFO demonstrably lacks, tested at every frame "
                "count from 1 to 7.")
    bullet(doc, "A page offset must survive translation untouched, and split then "
                "reassemble must round-trip for every address.")
    bullet(doc, "LOOK can never travel further than SCAN; every scheduler must serve "
                "each request exactly once and never leave the platter.")
    bullet(doc, "No two files may share a block; block accounting must balance; a "
                "**refused allocation must consume nothing**.")
    bullet(doc, "ifree() must return every block including the indirect ones — the "
                "leak this test caught during development is described below.")
    bullet(doc, "A larger LRU buffer cache can never have a lower hit ratio.")
    bullet(doc, "Empty and single-request queues must not crash any scheduler.")


    h3(doc, "A bug the invariants caught")
    para(doc,
         "The value of Class 2 is not hypothetical. An early version of the inode "
         "simulator promoted blocks to the single- and double-indirect pointers "
         "correctly but did not record the data blocks reached *through* them. The "
         "console output looked entirely plausible — the file was created, the trace "
         "read sensibly — and the block leak was invisible. The invariant "
         "*unlink must reclaim exactly the blocks that create consumed* failed, the "
         "allocator was corrected to track indirect data blocks explicitly, and the "
         "reclaim count moved from 12 to the correct 15. A test that only compared "
         "against an expected printed number would have passed against the wrong "
         "expectation.")

    image(doc, SHOT / "shot15_test_suite.png",
          "Console transcript: the full validation suite. 65 tests, 0 failures, "
          "0.513 s. results/logs/test_results.log", width=6.5, is_figure=False)

    h2(doc, "5.3  Stress behaviour")
    B.table(doc,
            ["Stress condition", "Observed behaviour", "Design response"],
            [("Memory over-commit, D/m = 1.248",
              "Aggregate working set exceeds physical memory",
              "KSM + ballooning + batch suspension bring D/m to 0.929"),
             ("Multiprogramming past the knee (N > 8)",
              "U_cpu collapses 1.000 → 0.399 → 0.201 while U_disk pins at 1.000",
              "Admission control caps N at the knee; PFF enforces it dynamically"),
             ("Frame allocation below the working set (f < 8)",
              "Fault rate rises 86× between f = 8 and f = 7",
              "Balloon floor fixed at the measured WSS"),
             ("Free-space fragmentation after churn",
              "248 blocks free, largest run 95, contiguous allocation refused",
              "Extent-based allocation; no compaction required"),
             ("Disk load raised from 24 % to 88 %",
              "FCFS p99 degrades 15× (8.1 → 122.7 ms); LOOK degrades 3×",
              "C-LOOK selected; RAID-10 or NVMe recommended beyond 45 % load"),
             ("Continuous arrivals with a hot band",
              "SSTF defers far-edge requests; tail ratio 13.6",
              "Sweep-based scheduler bounds the wait to one sweep"),
             ("Streaming I/O against a small cache",
              "20 % of the trace is uncacheable; hit ratio ceiling ≈ 80 %",
              "O_DIRECT on VM image I/O rather than a larger cache")],
            "Stress conditions, measured behaviour and the design response to each.",
            widths=[1.75, 2.35, 2.5], size=7.2)


# ==========================================================================
def section6(doc):
    h1(doc, "Analysis and Engineering Decisions", 6)

    h2(doc, "6.1  Page replacement for multi-tenant ballooning")
    para(doc,
         "**Decision: LRU, approximated by the kernel's active/inactive list scheme.**")
    para(doc,
         "The straightforward reading of the fault counts would recommend FIFO, "
         "because at three frames FIFO produces 11 faults and LRU produces 12. That "
         "reading is wrong, and understanding why is the most transferable lesson in "
         "this study.")
    para(doc,
         "CloudMatrix's balloon driver continuously resizes each guest's frame "
         "allocation in response to host pressure. That makes memory an actuator in a "
         "control loop, and a control loop requires a monotonic response: if the "
         "controller grants a guest another frame, the fault rate must not rise. "
         "**FIFO provides no such guarantee** — §2.3 measured it violating exactly "
         "that property, producing 12 faults with four frames against 11 with three. "
         "A controller built on FIFO can grant memory, observe the fault rate "
         "increase, grant more memory in response, and oscillate.")
    para(doc,
         "LRU and OPTIMAL are stack algorithms: the inclusion property μ(m) ⊆ μ(m+1) "
         "holds, so more memory can never mean more faults. That is a proof, not a "
         "measurement, and it is what a control loop can be built on. The 8.3 "
         "percentage-point advantage LRU holds at four frames (55.6 % against 66.7 % "
         "fault rate) is a bonus; **the monotonicity guarantee is the purchase**.")
    para(doc,
         "True LRU is not implementable — it would require a timestamp write on every "
         "memory reference — so Linux approximates it with two lists and periodic "
         "accessed-bit sampling. The approximation preserves the stack property, which "
         "is the property that mattered.")

    h2(doc, "6.2  Disk scheduling for cloud block storage")
    para(doc, "**Decision: C-LOOK, matching the Linux mq-deadline scheduler.**")
    para(doc,
         "On the static queue SSTF and LOOK tie at 813 cylinders and both beat "
         "everything else. On that evidence alone SSTF would be a defensible choice. "
         "The dynamic experiment shows why it is not.")
    B.table(doc,
            ["Criterion", "SSTF", "LOOK", "C-LOOK", "Decision driver"],
            [("Static total movement", "813 ✔", "813 ✔", "882", "Tie — not decisive"),
             ("Mean latency at 88 % load", "5.2 ms ✔", "6.0 ms", "7.1 ms",
              "SSTF marginally ahead"),
             ("p99 at 88 % load", "27.9 ms", "23.7 ms ✔", "28.2 ms",
              "LOOK ahead"),
             ("Worst case at 88 % load", "*71.2 ms", "40.3 ms", "*40.1 ms ✔",
              "*C-LOOK ahead by 1.8×"),
             ("Cold-request tail ratio", "*13.6 STARVES", "6.7", "*5.7 ✔",
              "*Decisive"),
             ("Wait bounded by construction", "No", "One sweep", "One sweep ✔",
              "Decisive for an SLA"),
             ("Matches production Linux", "No", "Partly", "Yes ✔",
              "Deployability")],
            "SSTF against the sweep schedulers. SSTF wins the average and loses the "
            "guarantee.",
            widths=[1.6, 1.05, 0.95, 1.05, 1.85], size=8.4, highlight={3, 4})
    para(doc,
         "SSTF's 5.2 ms mean is genuinely the best in the study. It is purchased by "
         "keeping the head inside the hot band and deferring the far-edge requests — "
         "and those far-edge requests are tenant backups, syslog writes and metadata "
         "reads. Its maximum response time reaches 71.2 ms, 1.8× worse than C-LOOK's "
         "40.1 ms, and its tail ratio of 13.6 is the numerical signature of "
         "starvation. Under a queue that never empties, SSTF offers no argument that a "
         "far request will ever be served.")
    para(doc,
         "C-LOOK bounds the wait by construction: a request waits at most one sweep. "
         "That is a property an SLA can be written against, and it is what "
         "mq-deadline provides in production. **The 1.9 ms of mean latency given up "
         "relative to SSTF buys a worst case that is 31 ms better** — an excellent "
         "trade for a platform that must answer to tenants rather than to a benchmark.")

    h2(doc, "6.3  Hypervisor architecture")
    para(doc, "**Decision: Type-1 (Xen) for production; KVM/libvirt for the lab.**")
    para(doc,
         "The performance argument favours Type-1 — 2–5 % overhead against 10–20 % — "
         "and at 1,200 guests that difference is worth roughly 150 guests of capacity. "
         "But the decisive argument is the trust boundary. A Type-2 hypervisor runs as "
         "a process on a general-purpose host operating system, which places that "
         "entire OS — its shell, its package manager, its unrelated daemons — inside "
         "the boundary that separates one tenant from another. A single host-level "
         "compromise takes every guest with it. For a platform hosting public and "
         "private sector tenants under ISO/IEC 27001, that boundary is not defensible "
         "regardless of the performance numbers.")

    h2(doc, "6.4  An honest finding: the 10 ms target is not reachable")
    para(doc,
         "Section D requires sub-10 ms service response under 90 %+ load. The "
         "measurements do not support a claim that this design meets it, and the "
         "report says so rather than quietly reporting the mean instead of the "
         "percentile.")
    B.table(doc,
            ["Offered load", "Best p99 achieved", "By", "Meets 10 ms?"],
            [("24 %", "7.4 ms", "SSTF", "Yes ✔"),
             ("40 %", "9.6 ms", "SSTF", "Yes ✔"),
             ("56 %", "12.1 ms", "SSTF", "*No"),
             ("72 %", "16.3 ms", "SSTF", "*No"),
             ("88 %", "23.1 ms", "LOOK", "*No — 2.3× over target")],
            "Best achievable p99 at each load point, across all six schedulers. The "
            "target holds to roughly 45 % load and is unreachable at the specified "
            "design point.",
            widths=[1.2, 1.5, 1.1, 2.7], size=8.6, highlight={2, 3, 4})
    para(doc,
         "The conclusion is not that the scheduling analysis failed; it is that "
         "**scheduling is the wrong lever for this requirement**. At 88 % utilisation "
         "a single spindle is queue-bound, and no reordering policy can create service "
         "capacity that does not exist. The gap between the best and worst schedulers "
         "at that load is 99 ms — real and worth having — but the gap between the best "
         "scheduler and the target is another 13 ms that reordering cannot close.")
    para(doc, "The remedy is architectural, and there are three options:")
    bullet(doc, "**Reduce per-device load below ~45 %** by striping the block tier "
                "across a RAID-10 set. Four spindles at 22 % load each comfortably "
                "meet the target with the same scheduler.")
    bullet(doc, "**Eliminate the seek term** by moving the tier to NVMe. With no head "
                "to move, the scheduler's job reduces to merging and fairness, and "
                "the p99 becomes a queueing property rather than a mechanical one.")
    bullet(doc, "**Renegotiate the requirement** so that it applies to the tiers that "
                "need it. A 10 ms p99 for interactive tenants is reasonable; the same "
                "target for batch analytics is not, and holding it there forces "
                "capacity spending that buys nothing.")
    para(doc,
         "The recommended combination is RAID-10 striping plus per-tier SLA "
         "differentiation, retaining C-LOOK as the scheduler because its bounded worst "
         "case remains the right property regardless of the underlying device.")

    h2(doc, "6.5  Trade-offs accepted")
    B.table(doc,
            ["Decision", "Gained", "Given up", "Why the trade is right"],
            [("LRU over FIFO", "Monotonic response to ballooning",
              "1 extra fault at 3 frames; higher bookkeeping cost",
              "A control loop cannot use a non-monotonic actuator"),
             ("C-LOOK over SSTF", "Worst case 1.8× better; bounded wait",
              "1.9 ms of mean latency",
              "Tenants experience the tail, not the mean"),
             ("Extent over indexed", "12,814 → a few hundred metadata blocks",
              "More complex allocator; extent fragmentation possible",
              "Large images dominate the storage footprint"),
             ("First-Fit over Best-Fit", "3.8× less stranded memory; O(1) search",
              "Slightly smaller largest remaining hole",
              "VM admission is on a hot path"),
             ("Hugepages, database tier only", "512× less TLB pressure",
              "Coarser reclaim granularity",
              "Fine reclaim is needed where the balloon operates"),
             ("cache='none' on guest disks", "fsync() reaches stable storage",
              "Lower raw throughput",
              "A durability lie is not a performance optimisation"),
             ("Suspend batch under pressure", "Protects interactive SLAs",
              "Batch jobs take longer",
              "Batch has no user waiting on it"),
             ("Type-1 over Type-2", "Small attack surface; 2–5 % overhead",
              "Harder to deploy; needs dom0 tuning",
              "Tenant isolation is the product")],
            "Trade-offs accepted, stated as costs rather than as benefits only.",
            widths=[1.35, 1.7, 1.7, 1.85], size=7.2)


# ==========================================================================
def section7(doc):
    h1(doc, "Broader Considerations", 7)

    h2(doc, "7.1  Sustainability and energy efficiency")
    para(doc,
         "The efficiency argument here is not decorative, because the measured numbers "
         "translate directly into hardware that does not have to be bought or powered.")
    bullet(doc, "**Consolidation.** Type-1 virtualization at 2–5 % overhead rather than 10–20 % fits roughly 150 more guests on the same host. At a typical 400 W draw, one avoided server is about 3,500 kWh per year.")
    bullet(doc, "**Page sharing.** KSM deduplicates 4.92 GB across the web tier — 15 % of the machine's memory recovered without buying a module.")
    bullet(doc, "**Reduced write amplification.** Delayed write cuts physical writes 7.6× (3,564 → 469), meaning less disk activity, less flash wear and longer replacement intervals.")
    bullet(doc, "**Fragmentation avoidance.** Extent allocation avoids periodic compaction, which on a multi-terabyte store means hours of full-power I/O producing no user-visible work.")
    bullet(doc, "**Honest capacity planning.** The §6.4 finding argues for RAID-10 "
                "striping rather than over-provisioning CPU to compensate for I/O "
                "latency, which is the more common and far less efficient response.")

    h2(doc, "7.2  Reliability and data integrity")
    bullet(doc, "**Snapshot before copy.** cm-backup.sh takes a virsh snapshot before "
                "copying any guest image, with qemu-guest-agent quiesce where "
                "available. Copying a running qcow2 without one produces an archive "
                "that appears valid and restores to nothing.")
    bullet(doc, "**Verify before trusting.** Checksums are written, forced to stable "
                "storage with sync -f, and then verified. An archive still resident in "
                "the page cache has not been written anywhere.")
    bullet(doc, "**Honest fsync.** cache='none' on guest disks means a guest's fsync() "
                "reaches real stable storage. Writeback caching would let fsync() "
                "return once data reached the host page cache — precisely the "
                "durability lie that converts a host power failure into tenant data "
                "loss.")
    bullet(doc, "**Atomic metadata operations.** The traced ifree() releases data "
                "blocks, indirect blocks and the inode as one operation, and the test "
                "suite asserts that every block is reclaimed. Partial reclaim is how "
                "file systems leak space until they are unmountable.")
    bullet(doc, "**Failing loudly.** The administration scripts run under "
                "set -euo pipefail and hold an flock, so a partial backup aborts "
                "visibly rather than producing a plausible-looking archive.")

    h2(doc, "7.3  Security, privacy and professional responsibility")
    bullet(doc, "**Tenant isolation in depth.** sVirt gives each guest a distinct "
                "SELinux category pair, so even a QEMU process escape cannot open "
                "another tenant's image. Per-tenant groups, 0700 homes and default "
                "ACLs enforce the same boundary on shared storage. Isolation is a set "
                "of independent controls, each failing closed.")
    bullet(doc, "**DNS abuse prevention.** Recursion restricted by ACL, DNSSEC "
                "validation, randomised source ports and response rate limiting. An "
                "open resolver is an amplification weapon aimed at third parties who "
                "never consented to be involved — this is an obligation to people "
                "outside the platform.")
    bullet(doc, "**Anti-spoofing between tenants.** Every vNIC carries a "
                "clean-traffic filter bound to its assigned IP, so a compromised guest "
                "cannot impersonate the gateway and intercept a neighbour's traffic.")
    bullet(doc, "**GDPR-aware logging.** DNS query logs identify which client asked "
                "for which name and are personal data under Article 4. They are kept "
                "30 days in a dedicated channel at 0640 root:bind, separate from "
                "security logs which are retained 52 weeks as ISO 27001 evidence. "
                "Retention is a per-stream decision because the data classes differ.")
    bullet(doc, "**Credentials never in configuration.** VNC passwords are set at "
                "deploy time via xl vncpasswd, and VNC listens only on 127.0.0.1. The "
                "TSIG key in the committed configuration is a placeholder.")
    bullet(doc, "**Accountability.** Account creation and removal are logged with "
                "timestamps, offboarded home directories are archived before deletion "
                "for audit, and cm-usermgmt.sh audit reports any account holding a "
                "usable password or any world-readable tenant home.")

    h2(doc, "7.4  Accessibility and fairness of service")
    para(doc,
         "Fairness in this design is a scheduling property, not a policy statement. "
         "C-LOOK guarantees that a tenant whose data sits at the far edge of the "
         "platter waits at most one sweep, so a small tenant's backup is not "
         "indefinitely deferred behind a large tenant's streaming workload. Per-guest "
         "IOPS and bandwidth caps stop one noisy tenant inflating everyone else's "
         "latency. And the working-set floor on ballooning ensures that a quiet guest "
         "is not squeezed into thrashing to satisfy a loud one. Each of these is a "
         "measurable guarantee rather than an aspiration.")


# ==========================================================================
def section8(doc):
    h1(doc, "Conclusion and Reflection", 8)

    h2(doc, "8.1  Summary of the design")
    para(doc,
         "CloudMatrix is specified across three subsystems, with each decision "
         "supported by a measurement rather than by a citation of convention.")
    B.table(doc,
            ["Subsystem", "Decision", "Decisive evidence"],
            [("Address translation", "Two-level page table, p1=5 | p2=10 | d=12, "
              "64-entry TLB", "128 KB → 4 KB residency; EAT 184.33 ns"),
             ("Memory placement", "Address-ordered First-Fit with coalescing",
              "Same placements as Best-Fit, ¼ the stranded memory, O(1) search"),
             ("Page replacement", "LRU (kernel two-list approximation)",
              "FIFO exhibits Belady's anomaly: 11 → 12 faults"),
             ("Frame allocation", "Working-set floor + proportional share + PFF band",
              "Thrashing knee at N = 8; D/m 1.248 → 0.929"),
             ("File allocation", "ext4 with extents and inline_data, by file class",
              "Contiguous refuses 150 blocks with 248 free"),
             ("Large-file mapping", "Extents rather than indirect chains",
              "12,814 indirect blocks for a 50 GB image"),
             ("Buffer cache", "1,024 buffers plus O_DIRECT on VM image I/O",
              "76.9 % hit = 96 % of the achievable ceiling"),
             ("Disk scheduling", "C-LOOK (mq-deadline)",
              "SSTF tail ratio 13.6; C-LOOK worst case 1.8× better"),
             ("Block tier hardware", "RAID-10 striping or NVMe",
              "No scheduler meets 10 ms p99 at 88 % load"),
             ("Network services", "BIND 9 with TSIG and rate limiting; ISC DHCP with "
              "reservations", "15 A ↔ 15 PTR consistency; all configs validate"),
             ("Virtualization", "Type-1 Xen; pinning, ballooning floors, sVirt, "
              "cache='none'", "Attack surface and the fsync durability argument")],
            "Design summary and the evidence behind each decision.",
            widths=[1.35, 2.5, 2.75], size=7.2)

    h2(doc, "8.2  Limitations")
    para(doc,
         "Four limitations are worth stating plainly, because a report that claims "
         "none is not being careful.")
    bullet(doc, "**The traces are synthetic.** They are structured to resemble the "
                "scenario — locality with drift for memory, a hot band plus scattered "
                "cold requests for disk — but they are not captured from a running "
                "platform. A real trace would almost certainly show heavier tails.")
    bullet(doc, "**The sub-sampling factor is a modelling assumption.** S = 4,000 sets "
                "the wall-clock scale of the thrashing analysis. It is stated in the "
                "module header rather than hidden, but a different factor would move "
                "the absolute utilisation numbers, though not the shape of the curve "
                "or the location of the knee.")
    bullet(doc, "**The seek model is linear.** Real drives have non-linear seek "
                "profiles with settle and rotational components that depend on "
                "distance. Since the same model is applied to all six algorithms, the "
                "comparison is fair even though the absolute milliseconds are "
                "approximate.")
    bullet(doc, "**The Linux services are validated structurally, not operationally.** "
                "The configurations are syntactically and structurally verified and "
                "the shell scripts genuinely parse, but they were not deployed against "
                "a live BIND 9 and ISC DHCP instance on a running host. That is the "
                "first thing to do with more time.")

    h2(doc, "8.3  Future work")
    bullet(doc, "Deploy the CO5 configuration on a real Ubuntu host and capture "
                "named-checkconf, dig, dhcpd -t and virsh output under load.")
    bullet(doc, "Replay a real block trace and a real memory trace in place of the "
                "synthetic generators, and check whether the knee and the tail "
                "behaviour survive.")
    bullet(doc, "Implement a hybrid adaptive scheduler that runs SSTF within a "
                "deadline window and falls back to a sweep when any request exceeds "
                "it — capturing SSTF's mean without its tail.")
    bullet(doc, "Model the RAID-10 configuration recommended in §6.4 and confirm "
                "quantitatively that four spindles at 22 % load each meet the 10 ms "
                "p99 target.")
    bullet(doc, "Add a machine-learning working-set predictor so the balloon "
                "controller can act before the fault rate rises rather than after.")

    h2(doc, "8.4  Reflection")
    para(doc,
         "The most useful thing this assignment taught me was how often the textbook "
         "ordering of algorithms is not the answer to an engineering question. Three "
         "moments in particular changed how I approached the rest of the work.")
    para(doc,
         "The first was discovering that **LRU produced more faults than FIFO** at "
         "three frames on my own trace. My instinct was that I had a bug. I wrote "
         "tests to prove it, and the tests said the implementation was correct — LRU "
         "genuinely is worse on that trace. What made LRU the right choice turned out "
         "to have nothing to do with the fault count: it was the stack property, which "
         "is what a balloon-driven control loop actually needs. I would not have found "
         "that by comparing the two numbers, and I nearly recommended FIFO before "
         "thinking about what the number was for.")
    para(doc,
         "The second was realising that **the static disk queue could not demonstrate "
         "the thing I wanted to claim**. I had computed the head movements, SSTF had "
         "the lowest total, and I was ready to write that SSTF starves far requests — "
         "which is what the textbook says. But my own fairness table showed SSTF tying "
         "LOOK for worst-case wait. A static queue always drains, so starvation cannot "
         "appear in one. I had to build the dynamic-arrival experiment to test the "
         "claim honestly, and only then did the 13.6 tail ratio appear. Choosing an "
         "experiment that can actually falsify your claim is a separate skill from "
         "implementing the algorithm.")
    para(doc,
         "The third was the **10 ms target that could not be met**. It would have been "
         "easy to report the mean latency, which comfortably clears 10 ms, and move "
         "on. Reporting the p99 instead meant admitting the design misses a stated "
         "requirement by 2.3×. Working out *why* — that a saturated spindle is "
         "queue-bound and reordering cannot manufacture capacity — produced the most "
         "genuinely useful recommendation in the report, which is about hardware "
         "rather than algorithms. A negative result that is understood is worth more "
         "than a positive one that is not.")
# ==========================================================================
def section9(doc):
    h1(doc, "References", 9)
    refs = [
        "A. Silberschatz, P. B. Galvin and G. Gagne, *Operating System Concepts*, "
        "10th ed. Hoboken, NJ, USA: Wiley, 2018.",
        "M. J. Bach, *The Design of the UNIX Operating System*. Englewood Cliffs, NJ, "
        "USA: Prentice Hall, 1986.",
        "A. S. Tanenbaum and H. Bos, *Modern Operating Systems*, 4th ed. Boston, MA, "
        "USA: Pearson, 2015.",
        "R. Love, *Linux Kernel Development*, 3rd ed. Upper Saddle River, NJ, USA: "
        "Addison-Wesley, 2010.",
        "P. J. Denning, “The working set model for program behavior,” "
        "*Communications of the ACM*, vol. 11, no. 5, pp. 323–333, May 1968.",
        "P. J. Denning, “Thrashing: its causes and prevention,” in *Proc. AFIPS Fall "
        "Joint Computer Conference*, vol. 33, 1968, pp. 915–922.",
        "L. A. Belady, R. A. Nelson and G. S. Shedler, “An anomaly in space-time "
        "characteristics of certain programs running in a paging machine,” "
        "*Communications of the ACM*, vol. 12, no. 6, pp. 349–353, Jun. 1969.",
        "L. A. Belady, “A study of replacement algorithms for a virtual-storage "
        "computer,” *IBM Systems Journal*, vol. 5, no. 2, pp. 78–101, 1966.",
        "R. L. Mattson, J. Gecsei, D. R. Slutz and I. L. Traiger, “Evaluation "
        "techniques for storage hierarchies,” *IBM Systems Journal*, vol. 9, no. 2, "
        "pp. 78–117, 1970.",
        "P. J. Denning and J. P. Buzen, “The operational analysis of queueing network "
        "models,” *ACM Computing Surveys*, vol. 10, no. 3, pp. 225–261, Sep. 1978.",
        "M. Seltzer, P. Chen and J. Ousterhout, “Disk scheduling revisited,” in "
        "*Proc. USENIX Winter Technical Conference*, 1990, pp. 313–323.",
        "B. L. Worthington, G. R. Ganger and Y. N. Patt, “Scheduling algorithms for "
        "modern disk drives,” in *Proc. ACM SIGMETRICS*, 1994, pp. 241–251.",
        "A. Mathur, M. Cao, S. Bhattacharya, A. Dilger, A. Tomas and L. Vivier, "
        "“The new ext4 filesystem: current status and future plans,” in "
        "*Proc. Linux Symposium*, vol. 2, 2007, pp. 21–33.",
        "M. K. McKusick, W. N. Joy, S. J. Leffler and R. S. Fabry, “A fast file "
        "system for UNIX,” *ACM Transactions on Computer Systems*, vol. 2, no. 3, "
        "pp. 181–197, Aug. 1984.",
        "P. Barham, B. Dragovic, K. Fraser, S. Hand, T. Harris, A. Ho, R. Neugebauer, "
        "I. Pratt and A. Warfield, “Xen and the art of virtualization,” in "
        "*Proc. 19th ACM SOSP*, 2003, pp. 164–177.",
        "C. A. Waldspurger, “Memory resource management in VMware ESX Server,” in "
        "*Proc. 5th USENIX OSDI*, 2002, pp. 181–194.",
        "A. Kivity, Y. Kamay, D. Laor, U. Lublin and A. Liguori, “KVM: the Linux "
        "virtual machine monitor,” in *Proc. Linux Symposium*, vol. 1, 2007, "
        "pp. 225–230.",
        "J. E. Smith and R. Nair, “The architecture of virtual machines,” "
        "*Computer*, vol. 38, no. 5, pp. 32–38, May 2005.",
        "P. Mockapetris, “Domain names — implementation and specification,” "
        "RFC 1035, IETF, Nov. 1987.",
        "R. Arends, R. Austein, M. Larson, D. Massey and S. Rose, “DNS security "
        "introduction and requirements,” RFC 4033, IETF, Mar. 2005.",
        "P. Vixie, O. Gudmundsson, D. Eastlake and B. Wellington, “Secret key "
        "transaction authentication for DNS (TSIG),” RFC 2845, IETF, May 2000.",
        "R. Droms, “Dynamic Host Configuration Protocol,” RFC 2131, IETF, Mar. 1997.",
        "D. Kaminsky, “Black ops 2008: it's the end of the cache as we know it,” "
        "presented at Black Hat USA, Las Vegas, NV, USA, Aug. 2008.",
        "Internet Systems Consortium, *BIND 9 Administrator Reference Manual*, "
        "version 9.18, 2024. [Online]. Available: https://bind9.readthedocs.io",
        "The Linux Kernel Organization, *Linux Kernel Documentation — Block Layer "
        "and Memory Management*, v6.x, 2024. [Online]. Available: "
        "https://docs.kernel.org",
        "libvirt Project, *libvirt Domain XML Format Reference*, 2024. [Online]. "
        "Available: https://libvirt.org/formatdomain.html",
        "IEEE, *IEEE Standard for Information Technology — Portable Operating System "
        "Interface (POSIX)*, IEEE Std 1003.1-2017, 2018.",
        "ISO/IEC, *Information Security, Cybersecurity and Privacy Protection — "
        "Information Security Management Systems — Requirements*, "
        "ISO/IEC 27001:2022, 2022.",
        "European Parliament and Council, *Regulation (EU) 2016/679 — General Data "
        "Protection Regulation*, Official Journal of the European Union, Apr. 2016.",
        f"T. S, *CloudMatrix — Operating Systems Assignment Implementation (CO3, CO4, "
        f"CO5)*, GitHub repository, 2026. [Online]. Available: {REPO}",
    ]
    for i, r in enumerate(refs, 1):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = B.Inches(0.42)
        p.paragraph_format.first_line_indent = B.Inches(-0.42)
        p.paragraph_format.space_after = B.Pt(5)
        parts = r.split("*")
        run = p.add_run(f"[{i}]  ")
        run.font.size = B.Pt(9.5)
        run.bold = True
        for j, seg in enumerate(parts):
            if not seg:
                continue
            run = p.add_run(seg)
            run.font.size = B.Pt(9.5)
            run.italic = (j % 2 == 1)

    doc.add_paragraph()
    h2(doc, "Declaration on the use of AI-assisted tools")
    para(doc,
         "An AI coding assistant was used during development for code scaffolding, "
         "for review of the simulator implementations, and for editorial assistance "
         "in drafting this report. All algorithmic design decisions, workload "
         "parameters, experiment designs and engineering conclusions are the author's "
         "own. Every numerical result reported here was produced by executing the "
         "committed code, and the full implementation and its execution logs are "
         "public so that any claim can be independently verified.", size=9.0)


# ==========================================================================
def appendix(doc):
    h1(doc, "Appendix A — Repository Map and Reproduction")
    link(doc, REPO, REPO, prefix="Repository:  ")

    h2(doc, "A.1  Repository structure")
    mono(doc,
         "OS-ASSIGNMENT/\n"
         "├── run_all.py                       regenerates every log, figure and test\n"
         "├── README.md                        headline results and reproduction steps\n"
         "├── requirements.txt   LICENSE   .gitignore\n"
         "├── src/\n"
         "│   ├── make_figures.py              six result charts\n"
         "│   ├── make_diagrams.py             four schematic diagrams\n"
         "│   ├── make_transcripts.py          console transcript rendering\n"
         "│   ├── co3_memory/\n"
         "│   │   ├── page_table.py            geometry + two-level MMU + TLB\n"
         "│   │   ├── dynamic_allocation.py    First / Best / Worst-Fit\n"
         "│   │   ├── page_replacement.py      FIFO / LRU / OPTIMAL + Belady test\n"
         "│   │   └── working_set.py           WSS, lifetime curve, PFF, thrashing\n"
         "│   ├── co4_storage/\n"
         "│   │   ├── file_allocation.py       contiguous / linked / indexed / extent\n"
         "│   │   ├── inode_fs.py              inode, bmap, ialloc/ifree/namei, cache\n"
         "│   │   ├── disk_scheduling.py       six schedulers, static queue\n"
         "│   │   └── disk_dynamic_experiment.py   arrivals, starvation, load sweep\n"
         "│   └── co5_linux/\n"
         "│       ├── dns/                     named.conf + forward and reverse zones\n"
         "│       ├── dhcp/                    dhcpd.conf\n"
         "│       ├── scripts/                 backup, usermgmt, healthcheck,\n"
         "│       │                            logrotate, netplan\n"
         "│       └── virtualization/          Xen cfg, libvirt XML, bridge setup\n"
         "├── tests/test_simulators.py         65 validation tests\n"
         "├── tools/\n"
         "│   ├── validate_co5.sh              CO5 configuration validation\n"
         "│   ├── make_code_shots.py           source-code screenshots\n"
         "│   ├── make_github_evidence.py      live repository evidence\n"
         "│   └── build_report.py + report_*   this document\n"
         "├── results/logs/                    verbatim console output (10 files)\n"
         "├── results/figures/                 300-dpi charts and diagrams (10 files)\n"
         "├── screenshots/                     transcripts, code and GitHub evidence\n"
         "└── docs/                            architecture document and this report",
         size=7.0)

    h2(doc, "A.2  Reproducing every result")
    mono(doc,
         "# clone and install\n"
         "git clone https://github.com/tharuncoder676/OS-ASSIGNMENT.git\n"
         "cd OS-ASSIGNMENT && pip install -r requirements.txt\n\n"
         "# regenerate the complete evidence base\n"
         "python run_all.py\n\n"
         "# or run any single experiment\n"
         "python src/co3_memory/page_replacement.py\n"
         "python src/co3_memory/working_set.py\n"
         "python src/co4_storage/file_allocation.py\n"
         "python src/co4_storage/inode_fs.py\n"
         "python src/co4_storage/disk_scheduling.py\n"
         "python src/co4_storage/disk_dynamic_experiment.py\n\n"
         "# validation\n"
         "python -m unittest discover -s tests -v      # 65 tests\n"
         "bash tools/validate_co5.sh                   # CO5 artefacts\n\n"
         "# on a host with the real Linux tooling installed\n"
         "named-checkconf src/co5_linux/dns/named.conf\n"
         "named-checkzone cloudmatrix.local src/co5_linux/dns/db.cloudmatrix.local\n"
         "dhcpd -t -cf src/co5_linux/dhcp/dhcpd.conf\n"
         "virsh define src/co5_linux/virtualization/libvirt-vm-web-01.xml",
         size=7.0)

    h2(doc, "A.3  Evidence index")
    B.table(doc,
            ["Report section", "Evidence file", "Produced by"],
            [("§2.1 Page table", "results/logs/co3_1_page_table.log",
              "src/co3_memory/page_table.py"),
             ("§2.2 Placement policies", "results/logs/co3_2_dynamic_allocation.log",
              "src/co3_memory/dynamic_allocation.py"),
             ("§2.3 Replacement, Belady", "results/logs/co3_3_page_replacement.log",
              "src/co3_memory/page_replacement.py"),
             ("§2.4 Working set, thrashing", "results/logs/co3_4_working_set.log",
              "src/co3_memory/working_set.py"),
             ("§2.5 File allocation", "results/logs/co4_1_file_allocation.log",
              "src/co4_storage/file_allocation.py"),
             ("§2.6 Inode and buffer cache", "results/logs/co4_2_inode_fs.log",
              "src/co4_storage/inode_fs.py"),
             ("§2.7 Disk scheduling", "results/logs/co4_3_disk_scheduling.log",
              "src/co4_storage/disk_scheduling.py"),
             ("§2.7.4 Dynamic experiment", "results/logs/co4_3b_disk_dynamic.log",
              "src/co4_storage/disk_dynamic_experiment.py"),
             ("§2.9 CO5 validation", "results/logs/co5_config_validation.log",
              "tools/validate_co5.sh"),
             ("§5.2 Validation suite", "results/logs/test_results.log",
              "tests/test_simulators.py")],
            "Evidence index. Each report section names the log file that supports it "
            "and the module that produced that log.",
            widths=[1.75, 2.5, 2.35], size=7.4)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = B.WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("— End of report —")
    r.font.size = B.Pt(10)
    r.italic = True
    r.font.color.rgb = B.GREY
    p2 = doc.add_paragraph()
    p2.alignment = B.WD_ALIGN_PARAGRAPH.CENTER
    r2 = p2.add_run(f"{NAME}  ·  Reg. No. {REGNO}  ·  CSA04 Operating Systems  ·  "
                    f"CO3 · CO4 · CO5")
    r2.font.size = B.Pt(9)
    r2.font.color.rgb = B.GREY
