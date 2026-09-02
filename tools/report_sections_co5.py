#!/usr/bin/env python3
"""CloudMatrix report - Section 2 Part III (CO5) and Sections 3-4."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx.shared import Pt

import build_report as B
from build_report import (FIG, REPO, SHOT, bullet, h1, h2, h3, image, link, mono,
                          pagebreak, para)


def part3_header(doc):
    p = doc.add_paragraph()
    r = p.add_run("PART III — LINUX ADMINISTRATION, NETWORK SERVICES AND "
                  "VIRTUALIZATION  (CO5)")
    r.bold = True
    r.font.size = Pt(11.5)
    r.font.color.rgb = B.ACCENT


# ==========================================================================
def s29_linux_server(doc):
    h2(doc, "2.9  Linux multifunction server configuration")

    h3(doc, "Network plan")
    para(doc,
         "The host serves two networks with deliberately different trust properties. "
         "The management LAN carries infrastructure and general-purpose guests; the "
         "tenant overlay is a separate broadcast domain with no host address and no "
         "default route, so guests on it have no layer-2 path to the management "
         "segment at all.")
    B.table(doc,
            ["Element", "Address", "Role"],
            [("Management LAN", "10.20.30.0/24", "Infrastructure and general guests"),
             ("Tenant overlay", "10.20.40.0/24", "Isolated tenant workloads (br1)"),
             ("Gateway", "10.20.30.1", "Default route"),
             ("Host / hypervisor (br0)", "10.20.30.5", "Bridge carries the host IP"),
             ("ns1 — BIND 9 primary", "10.20.30.10", "Authoritative + recursive"),
             ("ns2 — BIND 9 secondary", "10.20.30.11", "AXFR target, TSIG-authenticated"),
             ("dhcp — ISC DHCP", "10.20.30.12", "Pool .100–.199 plus reservations"),
             ("Guest VMs", "10.20.30.101–.107", "MAC-keyed DHCP reservations")],
            "CloudMatrix network plan.",
            widths=[1.85, 1.5, 3.05], size=7.6)

    image(doc, FIG / "fig09_topology.png",
          "Network topology and isolation boundaries. The tenant overlay bridge br1 "
          "carries no host address, which is the isolation property rather than a "
          "diagram convention.", width=6.5)

    h3(doc, "DNS — BIND 9")
    para(doc,
         "The configuration set comprises named.conf, named.conf.options, "
         "named.conf.local, a forward zone and three reverse zones. Four decisions in "
         "it are security decisions rather than functional ones, and each is worth "
         "justifying:")
    bullet(doc, "**Recursion is restricted by ACL** to 10.20.30.0/24 and "
                "10.20.40.0/24. A resolver that recurses for the whole internet is an "
                "amplification reflector — an attacker sends a small spoofed query and "
                "the victim receives a large response. This is not hardening; it is "
                "the difference between a resolver and a weapon.")
    bullet(doc, "**Zone transfers are TSIG-authenticated** with an hmac-sha256 key "
                "shared only with ns2. Without it, any host on the LAN can AXFR the "
                "zone and obtain a complete map of the estate — every hostname, every "
                "address, every service.")
    bullet(doc, "**DNSSEC validation is enabled** and query source ports are "
                "randomised across 1024–65535, which is what makes Kaminsky-style "
                "cache poisoning computationally impractical rather than merely "
                "inconvenient.")
    bullet(doc, "**Response rate limiting** (15 responses/second, slip 2) blunts "
                "reflection attacks that survive the ACL, and the version string is "
                "suppressed so the server does not advertise its own CVE list.")
    para(doc,
         "Query logging deserves separate mention because it is a data-protection "
         "decision. DNS query logs record which client asked for which name, which is "
         "personal data under GDPR Article 4. They are therefore written to a "
         "dedicated channel with **30-day retention** and 0640 root:bind permissions, "
         "not merged into the general syslog stream where they would inherit a much "
         "longer retention by accident. Security logs, by contrast, are kept 52 weeks "
         "because they are the evidence trail an ISO/IEC 27001 audit expects.")
    mono(doc,
         "acl cloudmatrix-internal { 127.0.0.0/8; 10.20.30.0/24; 10.20.40.0/24; };\n\n"
         "options {\n"
         "    allow-query     { cloudmatrix-internal; };\n"
         "    allow-recursion { cloudmatrix-internal; };\n"
         "    allow-transfer  { 10.20.30.11; };      // ns2 only\n"
         "    allow-update    { none; };\n"
         "    dnssec-validation auto;\n"
         "    use-v4-udp-ports { range 1024 65535; };\n"
         "    rate-limit { responses-per-second 15; window 5; slip 2; };\n"
         "    version \"not disclosed\";  hostname none;  server-id none;\n"
         "};\n\n"
         "key \"cloudmatrix-xfer\" { algorithm hmac-sha256; secret \"…\"; };\n"
         "zone \"cloudmatrix.local\" {\n"
         "    type master;  file \"/etc/bind/zones/db.cloudmatrix.local\";\n"
         "    allow-transfer { key cloudmatrix-xfer; };  also-notify { 10.20.30.11; };\n"
         "};",
         size=7.0)

    h3(doc, "DHCP — ISC")
    para(doc,
         "The pool is deliberately narrower than the subnet. Addresses .1–.99 are "
         "reserved for infrastructure and MAC-keyed guest reservations, .100–.199 is "
         "the dynamic pool, and .200–.254 is held back as headroom so the pool can be "
         "widened later without renumbering anything. Guests that need a stable "
         "identity — the ones with DNS records — get reservations rather than leases, "
         "which is what keeps the forward and reverse zones truthful across reboots.")
    mono(doc,
         "subnet 10.20.30.0 netmask 255.255.255.0 {\n"
         "    option routers 10.20.30.1;\n"
         "    option domain-name-servers 10.20.30.10, 10.20.30.11;\n"
         "    range 10.20.30.100 10.20.30.199;\n"
         "    host vm-web-01 { hardware ethernet 52:54:00:a1:01:01;\n"
         "                     fixed-address 10.20.30.101; }\n"
         "}\n"
         "class \"xen-pv-guests\" {\n"
         "    match if substring(option vendor-class-identifier, 0, 9) = \"PXEClient\";\n"
         "    next-server 10.20.30.5;  filename \"pxelinux.0\";\n"
         "}", size=7.0)

    h3(doc, "System administration scripts")
    B.table(doc,
            ["Script", "Purpose", "The decision worth noting"],
            [("cm-backup.sh", "Nightly backup of configs, zones and guest images",
              "Snapshots each guest with virsh before copying. Copying a live qcow2 "
              "without a snapshot is the commonest way to produce an archive that "
              "looks fine and restores to nothing. Checksums are written, forced to "
              "stable storage with sync -f, then verified — an archive still in the "
              "page cache is not a backup."),
             ("cm-usermgmt.sh", "Tenant account lifecycle",
              "Key-only accounts with the password explicitly locked, 0700 homes, "
              "quotas as an availability control, and default ACLs so files created "
              "later stay inside the tenant. Offboarding locks, kills sessions, "
              "archives, then deletes — deleting a live account leaves orphaned "
              "processes holding descriptors to data that is supposed to be gone."),
             ("cm-healthcheck.sh", "Service and resource validation",
              "Collects the evidence this report cites: dig forward and reverse "
              "resolution, query latency against the 10 ms target, named-checkconf, "
              "dhcpd -t, virsh and xl status, bridge state, page-fault and KSM "
              "counters, and the block queue scheduler."),
             ("cloudmatrix.logrotate", "Log retention policy",
              "Per-stream retention rather than one global rule: 30 days for query "
              "logs (GDPR minimisation), 52 weeks for security logs (ISO 27001 "
              "evidence), 90 days for application logs."),
             ("cm-netplan-br0.yaml", "Host network definition",
              "The host address lives on br0, not on eno1. That is what lets guests "
              "and host share one broadcast domain without NAT, so DHCP works and the "
              "reverse zone describes reality.")],
            "The CO5 administration script set and the reasoning behind each.",
            widths=[1.3, 1.6, 3.5], size=7.2)

    h3(doc, "Validation")
    para(doc,
         "Every CO5 artefact is validated by tools/validate_co5.sh. Where the real "
         "Linux tools are present the script defers to them (named-checkconf, "
         "named-checkzone, dhcpd -t); on a workstation without them it runs structural "
         "equivalents that catch the same failure modes. **bash -n is a genuine parse "
         "of every administration script and runs everywhere**, so shell validation is "
         "never a fallback.")
    para(doc,
         "The script also performs a check that neither named-checkzone nor a human "
         "reviewer reliably catches: that **every A record in the forward zone has a "
         "matching PTR in the reverse zone**. It reports 15 A records against 15 PTR "
         "records with every address matched. Reverse DNS drifting out of step with "
         "forward DNS is a classic slow failure, and it breaks exactly the tooling — "
         "mail servers, logging, access control — that trusts it.")

    image(doc, SHOT / "shot14_co5_validation.png",
          "Console transcript: full CO5 validation. Every script parses, all three "
          "zones are structurally valid, the DHCP brace balance and MAC uniqueness "
          "check out, the libvirt XML is well-formed, and forward/reverse DNS is "
          "consistent. results/logs/co5_config_validation.log", width=6.5,
          is_figure=False)


# ==========================================================================
def s210_hypervisor(doc):
    h2(doc, "2.10  Hypervisor and virtualization architecture")

    h3(doc, "Type-1 against Type-2")
    B.table(doc,
            ["Criterion", "Type-1 bare-metal (Xen, ESXi)",
             "Type-2 hosted (VMware Workstation, VirtualBox)"],
            [("Position", "Runs directly on hardware; owns ring 0",
              "Runs as a process on a host OS"),
             ("Privileged domain", "dom0 — a minimal Linux with driver access",
              "The full host OS"),
             ("I/O path", "Guest → paravirtual driver → dom0 → hardware",
              "Guest → hypervisor → host OS → hardware"),
             ("CPU / memory overhead", "2–5 %", "10–20 %"),
             ("Attack surface", "Small: hypervisor plus dom0",
              "Large: hypervisor plus the entire host OS and everything on it"),
             ("Blast radius of host compromise", "dom0 is hardened and minimal",
              "A host compromise takes every guest with it"),
             ("Live migration", "Native, with shared storage", "Limited or absent"),
             ("Density", "Hundreds of guests per host", "Tens"),
             ("Suits", "*Production multi-tenant infrastructure",
              "Development and test on a workstation")],
            "Type-1 versus Type-2 virtualization.",
            widths=[1.35, 2.35, 2.8], size=7.2)

    para(doc,
         "**Selected: Type-1 (Xen) for CloudMatrix production.** The decisive argument "
         "is not the 2–5 % against 10–20 % overhead, though at 1,200 guests that "
         "difference is real. It is the attack surface. A Type-2 hypervisor places the "
         "entire host operating system — with its shell, its package manager, its "
         "unrelated services — inside the trust boundary that separates one tenant "
         "from another. For a platform hosting public and private sector tenants under "
         "an ISO/IEC 27001 regime, that is not an acceptable boundary. KVM with "
         "libvirt is used in the lab configuration because it is a Type-1 architecture "
         "in practice (the hypervisor is the kernel itself) while remaining "
         "straightforward to deploy.")

    h3(doc, "Xen installation and guest deployment")
    mono(doc,
         "# 1. install the hypervisor and toolstack on the Linux host\n"
         "apt install xen-hypervisor-amd64 xen-tools xen-utils\n\n"
         "# 2. make Xen the default boot entry, then reboot into dom0\n"
         "sed -i 's/GRUB_DEFAULT=.*/GRUB_DEFAULT=\"Xen 4.17\"/' /etc/default/grub\n"
         "update-grub && reboot\n\n"
         "# 3. confirm dom0 is running under the hypervisor\n"
         "xl info          # hypervisor version, total memory, NUMA topology\n"
         "xl list          # Domain-0 present and running\n\n"
         "# 4. pin dom0 and cap its memory so it cannot be starved by guests\n"
         "xl vcpu-pin 0 all 0-3\n"
         "xl mem-set 0 4096\n\n"
         "# 5. define and start a guest from its configuration file\n"
         "xl create /etc/xen/vm-db-02.cfg\n"
         "xl console vm-db-02\n"
         "xl vcpu-list vm-db-02      # verify the pinning took effect\n\n"
         "# libvirt equivalent for the KVM lab path\n"
         "virsh define libvirt-vm-web-01.xml\n"
         "virsh start vm-web-01\n"
         "virsh dominfo vm-web-01 ; virsh domstats vm-web-01", size=7.0)

    para(doc,
         "Reserving and pinning dom0's own resources at step 4 is not optional. dom0 "
         "performs the physical I/O for every guest, so a dom0 starved of CPU by its "
         "own guests degrades all of them simultaneously — a failure mode that looks "
         "like a storage problem and is actually a scheduling one.")


# ==========================================================================
def s211_isolation(doc):
    h2(doc, "2.11  Resource isolation and VM management")

    h3(doc, "CPU pinning")
    para(doc,
         "The database guest's four vCPUs are pinned to physical cores 8–11 on NUMA "
         "node 0, where its memory is allocated, and given weight 512 against the "
         "default 256 so it outranks the batch tier. Allowing the scheduler to migrate "
         "a database vCPU across NUMA nodes costs roughly 30 % of its memory "
         "bandwidth, because every subsequent access becomes a remote one. Pinning is "
         "what makes the sub-10 ms interactive target achievable at all.")

    h3(doc, "Memory ballooning")
    para(doc,
         "The balloon driver inflates inside a guest to return frames to the host and "
         "deflates to reclaim them. The Xen configuration sets memory = 8192 MB as the "
         "floor and maxmem = 16384 MB as the ceiling, and **the floor is set at the "
         "measured working-set size, not lower**. This is the single most important "
         "line in the file. Ballooning a guest below its working set does not relieve "
         "memory pressure; it converts host memory pressure into guest thrashing, "
         "which by §2.4 costs a factor of ten in throughput. The balloon is a "
         "redistribution mechanism, not a compression mechanism.")

    h3(doc, "Virtual bridge networking")
    para(doc,
         "Guests attach to br0 through virtio-net taps. Three configuration choices "
         "matter: STP is enabled because a host with many taps can genuinely form a "
         "loop; bridge netfilter is disabled because filtering every guest-to-guest "
         "frame through iptables costs CPU on the hot path and breaks the layer-2 "
         "semantics tenants expect; and reverse-path filtering is strict, so a guest "
         "cannot source-spoof another guest's address.")
    para(doc,
         "Above that, each domain carries a clean-traffic filter bound to its assigned "
         "IP. This is the control that stops a compromised guest impersonating the "
         "gateway or another tenant on the shared segment — a bridge alone provides "
         "connectivity, not isolation.")

    h3(doc, "Storage passthrough and I/O isolation")
    para(doc,
         "The database guest's data volume is a raw LVM logical volume passed straight "
         "through, with no qcow2 layer and no host page cache. Double-caching wastes "
         "host memory the hypervisor needs elsewhere: the database already maintains "
         "its own buffer pool, and a second copy of the same blocks in the host page "
         "cache buys nothing. The OS volume, which benefits from caching, stays as a "
         "cached qcow2 file.")
    para(doc,
         "Guest disks are configured cache='none' so that a guest's fsync() reaches "
         "real stable storage. With writeback caching, fsync() returns once the data "
         "reaches the host page cache — which is exactly the durability lie that turns "
         "a host power failure into tenant data loss. Per-guest IOPS and bandwidth "
         "caps (3,000 IOPS, 200 MB/s) prevent one tenant monopolising the queue and "
         "inflating everyone else's latency past the SLA.")

    B.table(doc,
            ["Mechanism", "Configured as", "Protects against"],
            [("CPU pinning", "cpus = [\"8\",\"9\",\"10\",\"11\"], weight 512",
              "NUMA-remote memory access; batch jobs stealing DB cycles"),
             ("Memory ballooning", "memory 8192 floor / maxmem 16384 ceiling",
              "Host memory pressure — without pushing the guest into thrashing"),
             ("KSM page sharing", "35 % of the web tier deduplicated",
              "Redundant identical pages across 900 near-identical guests"),
             ("Bridge + filters", "br0 with clean-traffic bound to each guest IP",
              "MAC/IP spoofing and gateway impersonation between tenants"),
             ("Overlay isolation", "br1 with no host IP and no default route",
              "Tenant overlay guests reaching the management LAN at layer 2"),
             ("Storage passthrough", "raw LVM for DB data, qcow2 for OS volumes",
              "Double-caching the same blocks in host and guest"),
             ("Write durability", "cache='none' on all guest disks",
              "fsync() returning before data reaches stable storage"),
             ("I/O throttling", "3,000 IOPS / 200 MB/s per guest",
              "One noisy tenant inflating every other tenant's latency"),
             ("sVirt / SELinux", "dynamic label, distinct category pair per guest",
              "A QEMU process escape opening another tenant's image file"),
             ("Secure Boot", "OVMF with secboot firmware",
              "A guest loading an unsigned or tampered kernel")],
            "Isolation mechanisms and the specific threat each addresses. Isolation is "
            "not one setting; it is a set of independent controls that each fail "
            "closed.",
            widths=[1.3, 2.25, 2.95], size=7.2)


# ==========================================================================
def section3(doc):
    h1(doc, "Solution, Design and Methodology", 3)

    h2(doc, "3.1  Integrated architecture")
    para(doc,
         "The three course outcomes are not three separate answers. They are three "
         "layers of a single request path, and the interesting engineering lives at "
         "the boundaries between them. A tenant read descends through the "
         "virtualization layer (CO5), is translated by the memory subsystem (CO3), and "
         "if it misses, is served by the file system and block layer (CO4) — whose "
         "latency then feeds back into the memory subsystem as the cost of a page "
         "fault.")

    image(doc, FIG / "fig08_architecture.png",
          "Integrated subsystem architecture. Solid arrows follow the request path; "
          "the dashed arrow is the feedback that makes the PFF controller a closed "
          "loop rather than a static policy.", width=6.5)

    para(doc,
         "The feedback edge is the part that a layered description usually omits. The "
         "8 ms page-fault service time in the CO3 thrashing model is not a constant of "
         "nature — it is the CO4 disk subsystem's response time. Choosing a scheduler "
         "that raises p99 latency therefore lowers the multiprogramming level at which "
         "the memory subsystem thrashes. The two subsystems cannot be tuned "
         "independently, which is precisely why the recommendation in §6 treats them "
         "as one decision.")

    image(doc, FIG / "fig10_request_flow.png",
          "The file-read request path with measured costs at each stage. The dashed "
          "return is the 76.9 % of reads that never reach the disk at all.",
          width=6.5)

    h2(doc, "3.2  Design methodology")
    para(doc,
         "The same four-step method was applied to every design decision in this "
         "report, and stating it explicitly is what keeps the conclusions falsifiable:")
    bullet(doc, "**Implement every candidate**, not only the one expected to win. "
                "Six disk schedulers were implemented rather than three, and four "
                "allocation strategies rather than three.")
    bullet(doc, "**Measure on a workload derived from the scenario**, not on a "
                "convenient one. The dynamic disk experiment exists because the "
                "static queue could not exercise the property being claimed.")
    bullet(doc, "**Test the implementation against independent references** — "
                "hand calculations and textbook invariants — so that a confident "
                "wrong answer is caught before it is published.")
    bullet(doc, "**Report the result even when it contradicts the expected "
                "ordering.** LRU faulting more than FIFO at three frames, and the "
                "10 ms target being unreachable at 90 % load, are both reported.")

    h2(doc, "3.3  Decision matrices")
    para(doc,
         "Scores are 1 (worst) to 5 (best), assigned from the measured logs rather "
         "than from opinion. Weights reflect CloudMatrix's stated priorities: "
         "performance 30 %, overhead 20 %, isolation/predictability 25 %, "
         "reliability 25 %.")

    B.table(doc,
            ["Page replacement", "Performance", "Overhead", "Predictability",
             "Reliability", "Weighted", "Verdict"],
            [("FIFO", "2", "5", "1", "2", "2.45",
              "Rejected — anomaly breaks ballooning"),
             ("*LRU (approximated)", "4", "3", "5", "5", "*4.30", "*SELECTED"),
             ("OPTIMAL", "5", "1", "5", "5", "4.20",
              "Not implementable — used as the bound")],
            "Page replacement decision matrix. LRU is selected on predictability, not "
            "on raw fault count — at three frames it is worse than FIFO on this trace.",
            widths=[1.5, 0.85, 0.75, 1.0, 0.8, 0.75, 1.75], size=8.2, highlight={1})

    B.table(doc,
            ["Disk scheduling", "Mean latency", "Tail (p99)", "Fairness",
             "Implementable", "Weighted", "Verdict"],
            [("FCFS", "1", "1", "5", "5", "2.60", "Rejected — 122.7 ms p99 at load"),
             ("SSTF", "5", "3", "1", "4", "3.20", "Rejected — starves far requests"),
             ("SCAN", "3", "3", "4", "4", "3.45", "Viable"),
             ("C-SCAN", "3", "3", "5", "4", "3.70", "Viable"),
             ("LOOK", "4", "5", "4", "5", "4.45", "Strong"),
             ("*C-LOOK", "4", "4", "5", "5", "*4.50", "*SELECTED")],
            "Disk scheduling decision matrix. LOOK and C-LOOK are close; C-LOOK wins "
            "on the uniformity of its worst case, which is what an SLA is written "
            "against.",
            widths=[1.35, 0.9, 0.8, 0.8, 1.0, 0.75, 1.8], size=8.2, highlight={5})

    B.table(doc,
            ["Hypervisor", "Performance", "Overhead", "Isolation", "Reliability",
             "Weighted", "Verdict"],
            [("*Type-1 — Xen", "5", "5", "5", "4", "*4.75", "*SELECTED"),
             ("Type-2 — VMware Workstation", "3", "2", "2", "3", "2.55",
              "Development and test only")],
            "Hypervisor decision matrix. Isolation dominates: a Type-2 host places an "
            "entire general-purpose OS inside the tenant trust boundary.",
            widths=[1.9, 0.9, 0.8, 0.8, 0.85, 0.75, 1.55], size=8.2, highlight={0})

    h2(doc, "3.4  Requirement traceability")
    B.table(doc,
            ["Section D requirement", "Satisfied by", "Evidence"],
            [("Sub-millisecond translation latency",
              "Two-level page table + 64-entry TLB",
              "184.33 ns — co3_1_page_table.log"),
             ("High availability, zero data loss on crash",
              "Snapshot-before-copy backup, checksum verification, cache='none'",
              "cm-backup.sh, libvirt-vm-web-01.xml"),
             ("Strict multi-tenant isolation",
              "sVirt labels, per-tenant ACLs and quotas, br1 separation, "
              "anti-spoof filters",
              "§2.11 table, cm-usermgmt.sh"),
             ("Sub-10 ms response at 90 %+ load",
              "C-LOOK scheduling — **target met only to ≈45 % load**",
              "*co4_3b_disk_dynamic.log — see §6.4"),
             ("Accurate free-block tracking",
              "Bitmap and free list, conservation asserted by tests",
              "65/65 tests pass"),
             ("Memory parameters (32 GB, 4 KB, 128 MB)",
              "Derived geometry, hugepages evaluated separately",
              "co3_1_page_table.log"),
             ("Storage parameters (500 cylinders, 12 requests)",
              "All six schedulers on the specified queue",
              "co4_3_disk_scheduling.log"),
             ("POSIX / SELinux / ISO 27001",
              "Key-only accounts, TSIG, retention policy, audit trail",
              "co5_config_validation.log"),
             ("Version control with full documentation",
              "Public Git repository, 10 commits, README and architecture doc",
              REPO)],
            "Requirement traceability. Eight of nine constraints are fully satisfied; "
            "the ninth is partially satisfied and analysed in §6.4 rather than "
            "glossed over.",
            widths=[1.85, 2.4, 2.35], size=8.2, highlight={3})


# ==========================================================================
def section4(doc):
    h1(doc, "Use of Modern Tools", 4)

    h2(doc, "4.1  Toolchain")
    B.table(doc,
            ["Tool", "Version", "Used for", "Artefact"],
            [("Python", "3.12.10", "All eight simulators and the test suite",
              "src/, tests/"),
             ("matplotlib", "3.x", "Six result charts and four schematic diagrams",
              "results/figures/"),
             ("Pillow", "11.x", "Console transcript and source-code rendering",
              "screenshots/"),
             ("unittest", "stdlib", "65-test validation suite", "tests/"),
             ("Git / GitHub", "2.x", "Version control, commit history, public "
              "publication", REPO),
             ("GitHub CLI", "2.x", "Live repository state for the evidence pages",
              "tools/make_github_evidence.py"),
             ("Bash", "5.3", "Administration scripts and CO5 validation",
              "src/co5_linux/scripts/, tools/"),
             ("BIND 9", "9.18 target", "Authoritative and recursive DNS",
              "src/co5_linux/dns/"),
             ("ISC DHCP", "4.4 target", "Address allocation and PXE",
              "src/co5_linux/dhcp/"),
             ("Xen / libvirt", "4.17 / 10.x", "Guest definitions and isolation policy",
              "src/co5_linux/virtualization/")],
            "Toolchain and the artefact each tool produced.",
            widths=[1.15, 1.0, 2.35, 2.05], size=7.4)

    h2(doc, "4.2  Version control and the public repository")
    para(doc,
         "The complete implementation is public. Development was committed in logical "
         "units with substantive messages rather than as a single upload, so the "
         "history itself is evidence of how the work was built.")
    link(doc, REPO, REPO, prefix="Repository:  ")

    image(doc, SHOT / "shot16_github_commits.png",
          "Commit history fetched live from the GitHub REST API. Every SHA resolves "
          "at …/commit/<sha>, so any claim in this report can be traced to the exact "
          "revision that produced it.", width=6.5, is_figure=False)

    image(doc, SHOT / "shot18_github_summary.png",
          "Repository summary and language composition, fetched from the GitHub API.",
          width=6.0, is_figure=False)


    h2(doc, "4.3  Reproducibility")
    para(doc,
         "A result that cannot be regenerated is an assertion. The repository "
         "therefore ships a single driver that rebuilds the entire evidence base — "
         "logs, figures and test results — from source:")
    mono(doc,
         "git clone https://github.com/tharuncoder676/OS-ASSIGNMENT.git\n"
         "cd OS-ASSIGNMENT\n"
         "pip install -r requirements.txt\n"
         "python run_all.py\n\n"
         "  >>> CO3.1  Memory layout, two-level page table, TLB      → 9 logs\n"
         "  >>> CO4.3b Dynamic-arrival scheduling and load sensitivity\n"
         "  >>> Regenerating figures                                  → 10 figures\n"
         "  >>> Running the validation test suite\n"
         "      Ran 65 tests in 0.513s\n"
         "      OK\n"
         "  Tests : PASSED")
    para(doc,
         "Each log carries a provenance header recording the UTC timestamp, the Python "
         "version, the platform and the repository URL, so a regenerated log can be "
         "diffed against the submitted one directly.")
