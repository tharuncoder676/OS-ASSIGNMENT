# CloudMatrix — Integrated System Architecture

This document is the design artefact that ties CO3, CO4 and CO5 together. The diagrams
below render natively on GitHub and are reproduced in Section 5 of the written report.

---

## 1. Layered subsystem architecture

The three course outcomes are not three separate answers — they are three layers of one
request path. A tenant read descends through the memory subsystem (CO3), the file system
and block layer (CO4), and the virtualization and network layer (CO5).

```mermaid
flowchart TB
    subgraph T["Tenant workloads — 1,200 concurrent sessions"]
        W1["Web / DNS<br/>900 guests · 16 MB WSS"]
        W2["Enterprise app<br/>240 guests · 48 MB WSS"]
        W3["Database VM<br/>40 guests · 192 MB WSS"]
        W4["Batch analytics<br/>20 guests · 160 MB WSS"]
    end

    subgraph CO5["CO5 — Virtualization & network services"]
        HV["Xen / KVM hypervisor<br/>CPU pinning · ballooning · sVirt"]
        BR["br0 bridge<br/>virtio-net · anti-spoof filter"]
        NS["BIND9 + ISC DHCP<br/>10.20.30.0/24"]
    end

    subgraph CO3["CO3 — Virtual memory subsystem"]
        TLB["TLB (64 entries)<br/>58.3% hit ratio measured"]
        PT["Two-level page table<br/>p1=5 │ p2=10 │ d=12"]
        FR["8,388,608 frames<br/>32 GB / 4 KB"]
        PFF["PFF controller<br/>U = 0.50 · L = 0.10 faults/ms"]
    end

    subgraph CO4["CO4 — File system & block layer"]
        VFS["VFS · namei() · dentry cache"]
        IN["Inode layer<br/>10 direct + 3 indirect tiers"]
        BC["Buffer cache — LRU, delayed write<br/>76.9% hit @ 1,024 buffers"]
        SCH["I/O scheduler<br/>C-LOOK / mq-deadline"]
    end

    DISK[("500-cylinder block store<br/>+ NVMe swap, 8 ms service")]

    W1 & W2 & W3 & W4 --> HV
    HV --> BR --> NS
    HV --> TLB --> PT --> FR
    FR -. "fault: p > U" .-> PFF
    PFF -. "balloon / suspend" .-> HV
    FR -->|"page fault"| VFS
    HV --> VFS --> IN --> BC --> SCH --> DISK
    DISK -. "8 ms service time" .-> BC

    classDef co3 fill:#dbe9f6,stroke:#1f4e79,color:#10243b
    classDef co4 fill:#fde9d9,stroke:#c55a11,color:#41260a
    classDef co5 fill:#e2f0d9,stroke:#2e7d32,color:#183a1a
    class TLB,PT,FR,PFF co3
    class VFS,IN,BC,SCH co4
    class HV,BR,NS co5
```

---

## 2. Address translation path (CO3)

A 27-bit virtual address is split `p1 = 5 │ p2 = 10 │ d = 12`. The inner table is sized to
exactly one 4 KB frame (1,024 entries × 4 B), which is what allows the page tables themselves
to be paged and drops the per-process resident cost from 128 KB to 4 KB.

```mermaid
flowchart LR
    VA["Virtual address<br/>27 bits"] --> SPLIT{{"split"}}
    SPLIT -->|"p1 · 5 bits"| OUT["Outer page table<br/>32 entries · 128 B"]
    SPLIT -->|"p2 · 10 bits"| INN["Inner page table<br/>1,024 entries · 4 KB"]
    SPLIT -->|"d · 12 bits"| OFF["Offset"]

    VA --> TLBQ{"TLB hit?"}
    TLBQ -->|"yes · 1 memory ref"| PA
    TLBQ -->|"no"| OUT
    OUT --> INN
    INN -->|"valid"| PA["Physical address<br/>35 bits · f=23 │ d=12"]
    INN -->|"invalid"| PF["Page fault<br/>8 ms swap service"]
    PF --> REPL["Replacement: LRU<br/>(stack algorithm — no Belady risk)"]
    REPL --> PA
    OFF --> PA

    classDef hot fill:#e2f0d9,stroke:#2e7d32
    classDef cold fill:#fbdcdc,stroke:#c00000
    class TLBQ,PA hot
    class PF,REPL cold
```

**Measured effective access time** with a 64-entry TLB, 1 ns probe and 100 ns DRAM:
**184.33 ns**, against 300 ns with no TLB at all.

---

## 3. Request path: file read to physical block (CO4)

```mermaid
sequenceDiagram
    autonumber
    participant G as Guest VM
    participant V as VFS / namei()
    participant I as Inode + bmap()
    participant B as Buffer cache
    participant S as I/O scheduler (C-LOOK)
    participant D as Disk

    G->>V: read("/var/lib/cloudmatrix/guest.img", offset)
    V->>V: resolve 4 path components
    Note over V: cold: 5 I/Os · warm: 1 I/O<br/>(dentry cache)
    V->>I: inode 5
    I->>I: bmap(logical block)
    Note over I: block < 10 → direct, 1 read<br/>< 1,034 → single indirect, 2 reads<br/>beyond → up to 4 reads
    I->>B: request physical block
    alt buffer cache hit (76.9% measured)
        B-->>G: data, no disk I/O
    else miss
        B->>S: enqueue block request
        S->>S: insert into the C-LOOK sweep
        Note over S: worst case = one sweep<br/>→ bounded latency, no starvation
        S->>D: seek + transfer
        D-->>B: block
        B-->>G: data
    end
```

---

## 4. Network and virtualization topology (CO5)

```mermaid
flowchart TB
    NET(("Internet")) --> GW["gw 10.20.30.1"]

    subgraph HOST["CloudMatrix host — 10.20.30.5"]
        direction TB
        ENO["eno1 — no IP<br/>enslaved to the bridge"]
        BR0["br0 — 10.20.30.5/24<br/>STP on · nf-call-iptables off"]
        BR1["br1 — tenant overlay<br/>no host IP · no default route"]
        HYP["Xen / libvirt<br/>xl list · virsh list"]
        ENO --- BR0
        HYP --- BR0
        HYP --- BR1
    end

    subgraph SVC["Network services"]
        NS1["ns1 · BIND9 primary<br/>10.20.30.10"]
        NS2["ns2 · BIND9 secondary<br/>10.20.30.11"]
        DH["dhcp · ISC DHCP<br/>10.20.30.12"]
    end

    subgraph GUESTS["Guest VMs"]
        V1["vm-web-01 · .101<br/>52:54:00:a1:01:01"]
        V2["vm-db-02 · .102<br/>4 vCPU pinned · 2 MB hugepages"]
        V3["vm-win11-07 · .107"]
        V4["tenant-a · 10.20.40.x"]
    end

    GW --- BR0
    BR0 --- NS1 & NS2 & DH
    BR0 --- V1 & V2 & V3
    BR1 --- V4
    NS1 -->|"AXFR · TSIG hmac-sha256"| NS2
    DH -.->|"lease + reservation"| V1 & V3

    classDef sec fill:#fbdcdc,stroke:#c00000
    class BR1,NS1 sec
```

**Isolation properties.** `br1` carries no host address and no default route, so tenant
overlay guests have no layer-2 path to the management LAN. Every guest vNIC carries a
`clean-traffic` filter bound to its assigned IP, so a compromised guest cannot impersonate the
gateway or another tenant. Zone transfers are TSIG-authenticated, so a host on the LAN cannot
pull the full zone and map the estate.

---

## 5. Decision matrix

Scores are 1 (worst) to 5 (best), assigned from the measured results in `results/logs/`,
not from opinion. The weighted total uses CloudMatrix's stated priorities: performance 30%,
overhead 20%, isolation 25%, reliability 25%.

### Page replacement (CO3)

| Policy | Performance | Overhead | Predictability | Reliability | Weighted | Verdict |
|---|:--:|:--:|:--:|:--:|:--:|---|
| FIFO | 2 | **5** | 1 | 2 | 2.45 | Rejected — Belady's anomaly breaks ballooning |
| **LRU (approx.)** | 4 | 3 | **5** | **5** | **4.30** | **Selected** |
| OPTIMAL | **5** | 1 | 5 | 5 | 4.20 | Not implementable — used as the bound |

*LRU is chosen not because it had the fewest faults on trace W (at 3 frames it had 12 against
FIFO's 11) but because it is a stack algorithm. A balloon driver that resizes a guest's frame
allocation continuously needs the guarantee that more memory never means more faults.*

### Disk scheduling (CO4)

| Policy | Mean latency | Tail (p99) | Fairness | Implementable | Weighted | Verdict |
|---|:--:|:--:|:--:|:--:|:--:|---|
| FCFS | 1 | 1 | **5** | 5 | 2.60 | Rejected — 122.7 ms p99 at load |
| SSTF | **5** | 3 | 1 | 4 | 3.20 | Rejected — starves far requests |
| SCAN | 3 | 3 | 4 | 4 | 3.45 | Viable |
| C-SCAN | 3 | 3 | **5** | 4 | 3.70 | Viable |
| LOOK | 4 | **5** | 4 | 5 | 4.45 | Strong |
| **C-LOOK** | 4 | 4 | **5** | **5** | **4.50** | **Selected** |

### Hypervisor (CO5)

| Criterion | Type-1 (Xen) | Type-2 (VMware Workstation) |
|---|---|---|
| Ring-0 owner | hypervisor | host OS |
| I/O path | direct / dom0 passthrough | through the host OS |
| Overhead | 2–5% | 10–20% |
| Isolation | strong — no host OS attack surface | weaker — a host compromise takes every guest |
| Live migration | native | limited |
| **Verdict** | **Selected for CloudMatrix** | Dev/test only |

---

## 6. Where each requirement is satisfied

| Section D requirement | Satisfied by | Evidence |
|---|---|---|
| Sub-ms translation latency | two-level page table + TLB | 184.33 ns measured — `co3_1_page_table.log` |
| High availability, no data loss | snapshot-before-copy, checksum-verify, `cache='none'` | `cm-backup.sh`, `libvirt-vm-web-01.xml` |
| Multi-tenant isolation | sVirt, per-guest ACLs, br1 separation, anti-spoof filters | `docs` §4, `cm-usermgmt.sh` |
| Sub-10 ms response at 90%+ load | **partially** — met to 45% load; see the honest finding | `co4_3b_disk_dynamic.log` |
| Accurate free-space tracking | bitmap + free list, tested for conservation | 65 passing tests |
| POSIX / SELinux / ISO 27001 | key-only accounts, TSIG, retention policy, audit trail | `co5_linux/` |

The one requirement not fully met is stated plainly rather than glossed: at the 90%+ load
design point, no scheduling policy achieves a 10 ms p99 on a single spindle. The remedy is
architectural (RAID-10 striping or NVMe), not algorithmic, and it is recommended as such.
