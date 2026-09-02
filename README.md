# CloudMatrix — Operating Systems Assignment (CSA04, CO3 · CO4 · CO5)

**Design, Memory Optimization, and System Administration of an Enterprise Cloud & Virtualization Platform**

| | |
|---|---|
| **Course** | CSA04 — Operating Systems |
| **Course Outcomes** | CO3 (Virtual Memory & Paging) · CO4 (File Systems, Inodes & Disk Scheduling) · CO5 (Linux Administration, Network Services & Virtualization) |
| **Bloom's Levels** | L3 Apply · L4 Analyse · L5 Evaluate |
| **Student** | Tharunkumar S — Reg. No. 192511416 |
| **Academic Year** | 2026–2027 |
| **Marks** | 100 |

---

## The report

The full assignment report (43 pages, 10 figures, 43 tables) is in this repository:

- **[CSA04_OS_Assignment_CO3_CO4_CO5_Tharunkumar_S_192511416.docx](docs/CSA04_OS_Assignment_CO3_CO4_CO5_Tharunkumar_S_192511416.docx)** — Word
- **[CSA04_OS_Assignment_CO3_CO4_CO5_Tharunkumar_S_192511416.pdf](docs/CSA04_OS_Assignment_CO3_CO4_CO5_Tharunkumar_S_192511416.pdf)** — PDF
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — integrated architecture, diagrams and decision matrices

It is itself generated from this repository: `python tools/build_report_twopass.py`
rebuilds it, pulling every figure and evidence image from `results/` and
`screenshots/`, and measuring the real page numbers for the contents page in a
second pass. The report therefore cannot quote a number the code does not
produce.

---

## What this repository is

CloudMatrix is a hypothetical enterprise virtualization host: 32 GB of RAM, a 500-cylinder
block store, Linux 6.x, Xen/KVM hypervisors, and 1,200 concurrent tenant workloads. The
assignment asks for memory calculations, page-replacement traces, inode dynamics, disk-head
analysis, Linux service configuration and hypervisor design.

This repository contains **executable answers**. Every number quoted in the written report is
produced by a program in `src/`, captured into `results/logs/`, plotted into
`results/figures/`, and checked by a test in `tests/`. Nothing in the report is asserted
without a runnable artefact behind it.

Reproduce the entire evidence base with one command:

```bash
python run_all.py
```

---

## Repository layout

```
.
├── run_all.py                      # regenerates every log, figure and test result
├── src/
│   ├── make_figures.py             # renders all six report figures from the simulators
│   ├── co3_memory/                 # CO3 — virtual memory and paging
│   │   ├── page_table.py           #   frame/page geometry + two-level MMU with a TLB
│   │   ├── dynamic_allocation.py   #   First-Fit / Best-Fit / Worst-Fit + shared libraries
│   │   ├── page_replacement.py     #   FIFO / LRU / OPTIMAL + Belady's anomaly test
│   │   └── working_set.py          #   WSS, lifetime curve, PFF control, thrashing knee
│   ├── co4_storage/                # CO4 — file systems and disk scheduling
│   │   ├── file_allocation.py      #   Contiguous / Linked / Indexed / Extent allocation
│   │   ├── inode_fs.py             #   inode reach, bmap, ialloc/ifree/namei/alloc/free,
│   │   │                           #   buffer cache with delayed write
│   │   ├── disk_scheduling.py      #   FCFS / SSTF / SCAN / C-SCAN / LOOK / C-LOOK
│   │   └── disk_dynamic_experiment.py  # continuous-arrival starvation + load sweep
│   └── co5_linux/                  # CO5 — Linux services and virtualization
│       ├── dns/                    #   BIND9: named.conf, forward + reverse zones
│       ├── dhcp/                   #   ISC DHCP: pools, reservations, PXE class
│       ├── scripts/                #   backup, tenant lifecycle, health check, logrotate,
│       │                           #   netplan bridge definition
│       └── virtualization/         #   Xen guest cfg, libvirt domain XML, bridge setup
├── tests/test_simulators.py        # 65 tests: hand-computed values + textbook invariants
├── results/
│   ├── logs/                       # verbatim console output of every module
│   └── figures/                    # six 300-dpi figures used in the report
├── docs/                           # architecture notes and the written report
└── screenshots/                    # execution evidence
```

---

## Headline results

### CO3 — Virtual memory and paging

| Quantity | Value | Where |
|---|---|---|
| Physical frames (32 GB / 4 KB) | **8,388,608** = 2²³ | `page_table.py` |
| Virtual pages per process (128 MB / 4 KB) | **32,768** = 2¹⁵ | `page_table.py` |
| Virtual address split | `p1 = 5 │ p2 = 10 │ d = 12` (27 bits) | `page_table.py` |
| Page-table cost, flat vs sparse two-level | 128 KB → **4 KB** per process (32×) | `page_table.py` |
| Page faults, reference string W (18 refs) | FIFO 11→**12**, LRU 12→10, OPT 9→8 | `page_replacement.py` |
| **Belady's anomaly** | **Confirmed for FIFO** (+1 fault with 4 frames) | `page_replacement.py` |
| Thrashing knee | N = **8** guests; past it CPU utilisation collapses 100% → 40% → 20% | `working_set.py` |
| Over-commit closure | D/m = 1.248 → **0.929** after KSM + ballooning + batch suspension | `working_set.py` |

### CO4 — File systems, inodes and disk scheduling

Queue `[86, 147, 312, 91, 177, 48, 409, 22, 130, 365, 220, 480]`, head at cylinder 125,
moving towards higher cylinders, 500-cylinder disk (0–499):

| Algorithm | Total head movement | Average seek | vs FCFS |
|---|---:|---:|---:|
| FCFS | 2,197 cyl | 183.08 | — |
| **SSTF** | **813 cyl** | 67.75 | −63.0% |
| SCAN | 851 cyl | 70.92 | −61.3% |
| C-SCAN | 964 cyl | 80.33 | −56.1% |
| **LOOK** | **813 cyl** | 67.75 | −63.0% |
| C-LOOK | 882 cyl | 73.50 | −59.9% |

The static queue is not the whole story. Under **continuous arrivals at 88% device load**
(4,000 requests, `disk_dynamic_experiment.py`), SSTF's attractive mean hides a starvation tail:

| Algorithm | Mean | p99 | Maximum | Verdict |
|---|---:|---:|---:|---|
| FCFS | 44.6 ms | 124.3 ms | 133.9 ms | collapses under load |
| SSTF | **5.2 ms** | 27.9 ms | 71.2 ms | fastest mean, **starves far requests** |
| LOOK | 6.0 ms | **23.7 ms** | 40.3 ms | best balance |
| C-LOOK | 7.1 ms | 28.2 ms | **40.1 ms** | bounded worst case |

Other CO4 results: maximum inode-addressable file **4.004 TB**; a 50 GB VM image needs
**12,814 indirect blocks** (50 MB of pure pointers), which is the quantitative case for
extents; contiguous allocation **refuses a 150-block file while 248 blocks are free** — external
fragmentation measured, not merely defined; linked allocation costs **1,035 I/Os** where indexed
costs 24 for the same random read pattern (**45× penalty**).

### CO5 — Linux services and virtualization

Production-shaped configurations, not toy snippets: BIND9 with TSIG-authenticated zone
transfers, DNSSEC validation, response rate limiting and a GDPR-aware 30-day query-log
retention; ISC DHCP with reservations, a PXE class and a relayed tenant subnet; a bridge
topology where the host address lives on `br0`; a backup script that snapshots before it
copies and verifies checksums before it trusts; a libvirt domain with `cache='none'`,
per-guest IOPS throttling, MAC/IP anti-spoof filters, CPU pinning and sVirt labelling.

---

## Reproducing the results

```bash
git clone https://github.com/tharuncoder676/OS-ASSIGNMENT.git
cd OS-ASSIGNMENT
pip install -r requirements.txt
python run_all.py
```

Run any single module directly:

```bash
python src/co3_memory/page_replacement.py
python src/co4_storage/disk_scheduling.py
python src/co4_storage/disk_dynamic_experiment.py
```

Run the validation suite:

```bash
python -m unittest discover -s tests -v
```

Validate the Linux configurations on a host that has the tools installed:

```bash
named-checkconf src/co5_linux/dns/named.conf
named-checkzone cloudmatrix.local src/co5_linux/dns/db.cloudmatrix.local
dhcpd -t -cf src/co5_linux/dhcp/dhcpd.conf
bash -n src/co5_linux/scripts/cm-backup.sh
```

---

## Validation

`tests/test_simulators.py` contains **65 tests** and passes clean. They check two kinds of
thing:

1. **Hand-computed values** — the six page-fault counts, all six head-movement totals, the
   frame and page counts, the 12,814-block metadata figure. If a simulator drifts, a test
   fails and the report's numbers are known to be stale.
2. **Textbook invariants that must hold for any correct implementation** — OPT is a lower
   bound on every online policy; LRU and OPT are stack algorithms and can never regress with
   more frames; LOOK can never travel further than SCAN; no two files may share a block; a
   refused allocation must consume nothing; `ifree()` must return every block including the
   indirect ones; a larger LRU cache can never have a lower hit ratio.

```
Ran 65 tests in 0.51s

OK
```

---

## Design decisions worth stating up front

- **Extent allocation is included** alongside the three classical methods, because for a
  50 GB `.vmdk` the classical indirect chain costs 12,814 metadata blocks and ext4/XFS
  genuinely use extents instead. Answering only with the three textbook methods would be
  historically accurate and practically wrong.
- **C-LOOK is included** alongside the five named algorithms, because it is what the Linux
  `mq-deadline` scheduler approximates, and a recommendation that ignores it is unsupported.
- **A dynamic-arrival experiment supplements the static queue**, because starvation is
  invisible in a queue that drains. The static queue answers the question as asked; the
  dynamic experiment answers the question the scenario actually poses.
- **The trace sub-sampling factor (S = 4,000) is stated explicitly** in `working_set.py`
  rather than hidden, because the thrashing model's wall-clock numbers depend on it.
- **The honest negative result is reported**: at the 90%+ load design point, *no* scheduling
  policy meets a 10 ms p99 on a single spindle. Scheduling alone is insufficient; the block
  tier must be striped or moved to NVMe. That conclusion is in the report because the data
  says so, not despite it.

---

## Environment

Python 3.12.10 · matplotlib 3.x · Windows 11 (the simulators are pure Python and
platform-independent). The CO5 configurations target Ubuntu Server 24.04 LTS with BIND 9.18,
ISC DHCP 4.4, libvirt 10.x and Xen 4.17.

## Licence

MIT — see [LICENSE](LICENSE).
