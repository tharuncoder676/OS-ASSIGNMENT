#!/usr/bin/env python3
"""
CloudMatrix - CO3 : Working-Set Model, Page-Fault Frequency and Thrashing
========================================================================

Four things are established here, all by measurement rather than assertion:

  1. The working-set size WSS(t, Delta) of a locality-structured reference
     stream, computed directly from the sliding-window definition
         W(t, Delta) = { pages referenced in [t - Delta + 1, t] }.

  2. The empirical lifetime curve p(f): faults per reference as a function of
     the frames f granted to a process. This is the curve a page-fault
     frequency (PFF) controller actually steers on.

  3. The thrashing knee, using operational analysis rather than hand-waving.
     Each guest cycles between a CPU burst of mean C = (1/p) * S * t_mem and a
     paging service of mean D = 8 ms. With one CPU and one paging device the
     asymptotic throughput bound is
         X(N) <= min( N / (C + D) , 1 / max(C, D) )
     and CPU utilisation is U(N) = X(N) * C. As N rises, each guest's share
     f = M/N shrinks, p(f) rises, C collapses, and U falls off a cliff. That
     cliff is thrashing.

  4. An admission-control and frame-allocation policy for the real 1,200-session
     CloudMatrix mix, including the ballooning / KSM / suspension budget needed
     to make an over-committed host actually fit.

Modelling assumption (stated explicitly): the synthetic trace is SAMPLED at
page granularity -- one recorded reference stands for S = 4,000 real memory
references. Sub-sampling is standard practice in trace-driven memory studies
and is what makes a 300k-entry trace stand in for a 1.2-billion-reference
execution. All fault RATES below are per sampled reference; wall-clock
quantities divide by S where relevant.

Run:  python src/co3_memory/working_set.py
"""

from __future__ import annotations

import random

MEM_ACCESS_NS = 100.0            # DRAM access latency
PAGE_FAULT_MS = 8.0              # NVMe-backed swap service time on this host
SAMPLING_FACTOR = 4_000          # real references represented by one sample
TOTAL_SIM_FRAMES = 64            # frames in the simulated memory partition

KB, MB, GB = 1024, 1024 ** 2, 1024 ** 3


# --------------------------------------------------------------------------
# 1. Locality-structured reference generator
# --------------------------------------------------------------------------

def locality_trace(length: int = 60_000, locality: int = 8,
                   dwell: int = 4_000, universe: int = 64,
                   seed: int = 4067) -> list[int]:
    """A trace that behaves like a real process: it sits inside a small
    locality for `dwell` references, then the locality drifts."""
    rng = random.Random(seed)
    trace, base = [], 0
    while len(trace) < length:
        window = [(base + i) % universe for i in range(locality)]
        for _ in range(dwell):
            trace.append(rng.choice(window))
            if len(trace) >= length:
                break
        base = (base + rng.randint(2, locality)) % universe
    return trace


# --------------------------------------------------------------------------
# 2. Working-set size
# --------------------------------------------------------------------------

def working_set_sizes(trace: list[int], delta: int, stride: int = 7) -> list[int]:
    """Sliding-window working set, evaluated every `stride` references."""
    return [len(set(trace[max(0, t - delta + 1): t + 1]))
            for t in range(0, len(trace), stride)]


# --------------------------------------------------------------------------
# 3. Empirical fault rate p(f) under LRU  (O(1) per reference)
# --------------------------------------------------------------------------

def lru_fault_rate(trace: list[int], frames: int) -> float:
    mem: dict[int, None] = {}
    faults = 0
    for page in trace:
        if page in mem:
            del mem[page]
        else:
            faults += 1
            if len(mem) >= frames:
                mem.pop(next(iter(mem)))
        mem[page] = None
    return faults / len(trace)


def cpu_burst_ms(p: float) -> float:
    """Mean CPU time between two page faults, in milliseconds."""
    if p <= 0:
        return float("inf")
    real_refs_between_faults = (1.0 / p) * SAMPLING_FACTOR
    return real_refs_between_faults * MEM_ACCESS_NS / 1e6


def utilisation(n: int, p: float) -> tuple[float, float, float]:
    """Operational-analysis bound: returns (throughput, U_cpu, U_disk)."""
    c, d = cpu_burst_ms(p), PAGE_FAULT_MS
    x = min(n / (c + d), 1.0 / max(c, d))     # jobs completed per ms
    return x, min(1.0, x * c), min(1.0, x * d)


# --------------------------------------------------------------------------

def main() -> dict:
    trace = locality_trace()

    print("=" * 78)
    print(" CO3.4  WORKING-SET MODEL - measured on a locality-structured trace")
    print("=" * 78)
    print(f"   Trace length        : {len(trace):,} sampled references over "
          f"{len(set(trace))} distinct pages")
    print(f"   True locality size  : 8 pages, drifting every 4,000 references")
    print()
    print(f"   {'Window Delta':>14}{'mean WSS':>12}{'peak WSS':>12}{'min WSS':>10}"
          f"   Interpretation")
    ws_summary = {}
    for delta in (10, 25, 50, 100, 250, 500, 1000):
        sizes = working_set_sizes(trace, delta)
        mean, peak, low = sum(sizes) / len(sizes), max(sizes), min(sizes)
        ws_summary[delta] = (mean, peak, low)
        if delta <= 25:
            note = "too short - undercounts the locality"
        elif delta <= 250:
            note = "tracks the true locality"
        else:
            note = "too long - absorbs stale localities"
        print(f"   {delta:>14}{mean:>12.2f}{peak:>12}{low:>10}   {note}")
    print()
    print("   Delta = 50-250 is the usable operating band: WSS settles on the")
    print("   generator's true locality of 8 pages. Too small a window starves the")
    print("   process; too large a window keeps dead pages resident and wastes")
    print("   frames that another guest needs. D = sum(WSS_i) computed with a")
    print("   window in this band is the demand figure the allocator must respect.")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO3.4  LIFETIME CURVE p(f) - measured fault rate vs frames granted")
    print("=" * 78)
    print(f"   {'Frames f':>9}{'faults/ref p':>14}{'CPU burst C (ms)':>19}"
          f"{'C vs D=8ms':>13}   Regime")
    curve = {}
    for f in (2, 3, 4, 5, 6, 7, 8, 10, 12, 16, 24, 32, 48, 64):
        p = lru_fault_rate(trace, f)
        c = cpu_burst_ms(p)
        curve[f] = p
        regime = "CPU-bound (healthy)" if c > PAGE_FAULT_MS else "PAGING-BOUND"
        print(f"   {f:>9}{p:>14.6f}{c:>19.3f}"
              f"{('C > D' if c > PAGE_FAULT_MS else 'C < D'):>13}   {regime}")
    print()
    print("   The knee is at f = 8 frames, exactly the locality size. Below it the")
    print("   process faults faster than the swap device can serve, and the paging")
    print("   device -- not the CPU -- becomes the system bottleneck.")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO3.4  THRASHING - CPU utilisation as multiprogramming degree N rises")
    print("=" * 78)
    print(f"   Partition = {TOTAL_SIM_FRAMES} frames, equal-share allocation f = M/N")
    print(f"   Paging service D = {PAGE_FAULT_MS} ms, one CPU, one paging device")
    print()
    print(f"   {'N':>4}{'f=M/N':>7}{'p':>11}{'C (ms)':>10}{'X (jobs/ms)':>13}"
          f"{'U_cpu':>9}{'U_disk':>9}   State")
    util, best_n, best_u = {}, 0, 0.0
    for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16, 21, 32):
        f = max(1, TOTAL_SIM_FRAMES // n)
        p = lru_fault_rate(trace, f)
        c = cpu_burst_ms(p)
        x, ucpu, udisk = utilisation(n, p)
        util[n] = (f, p, c, x, ucpu, udisk)
        if ucpu >= best_u - 1e-9:      # knee = LAST N still at peak
            best_u, best_n = max(best_u, ucpu), n
        state = ("healthy" if ucpu > 0.85 else
                 "degrading" if ucpu > 0.40 else "THRASHING")
        print(f"   {n:>4}{f:>7}{p:>11.6f}{c:>10.3f}{x:>13.4f}"
              f"{ucpu:>9.3f}{udisk:>9.3f}   {state}")
    print()
    print(f"   Utilisation holds at U = {best_u:.3f} up to N = {best_n} guests"
          f" (f = {TOTAL_SIM_FRAMES // best_n} frames each), then collapses.")
    print("   Past that point every additional guest LOWERS aggregate throughput:")
    print("   U_disk pins at 1.000 while U_cpu collapses, which is the operational")
    print("   signature of thrashing -- the machine is fully busy, but busy paging.")
    print("   Admission control must therefore cap N at the knee, and the PFF")
    print("   controller must enforce the cap dynamically as working sets grow.")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO3.4  FRAME ALLOCATION FOR THE 1,200-SESSION CloudMatrix MIX")
    print("=" * 78)
    frames_total = 32 * GB // (4 * KB)
    reserve = int(frames_total * 0.10)          # kernel, hypervisor, page cache
    available = frames_total - reserve
    tiers = [
        ("Web / DNS microservice", 900, 16),
        ("Interactive enterprise app", 240, 48),
        ("Database guest VM", 40, 192),
        ("Batch analytics worker", 20, 160),
    ]
    print(f"   Total frames (32 GB / 4 KB)   : {frames_total:,}")
    print(f"   Hypervisor + page cache (10%) : {reserve:,}")
    print(f"   Available to guests  m        : {available:,}  "
          f"({available * 4 * KB / GB:.2f} GB)")
    print()
    print(f"   {'Tier':<30}{'Guests':>8}{'WSS (MB)':>10}{'frames':>10}"
          f"{'tier demand':>14}{'GB':>8}")
    demand = 0
    tier_frames = {}
    for name, count, wss_mb in tiers:
        wf = wss_mb * MB // (4 * KB)
        tier_frames[name] = wf * count
        demand += wf * count
        print(f"   {name:<30}{count:>8}{wss_mb:>10}{wf:>10,}"
              f"{wf * count:>14,}{wf * count * 4 * KB / GB:>8.2f}")
    print(f"   {'TOTAL DEMAND  D = sum WSS_i':<30}"
          f"{sum(c for _, c, _ in tiers):>8}{'':>10}{'':>10}"
          f"{demand:>14,}{demand * 4 * KB / GB:>8.2f}")
    print()
    ratio = demand / available
    print(f"   D / m = {demand:,} / {available:,} = {ratio:.3f}"
          f"   -> {(ratio - 1) * 100:+.1f}% over-committed")
    print("   D > m, so the naive allocation thrashes. Three reclaim mechanisms")
    print("   close the gap, in the order the controller should apply them:")
    print()
    ksm = int(tier_frames["Web / DNS microservice"] * 0.35)
    balloon = int(tier_frames["Interactive enterprise app"] * 0.10)
    suspend = tier_frames["Batch analytics worker"]
    print(f"   1. KSM page sharing across 900 near-identical web guests (35%)"
          f"   -{ksm:>10,} frames  ({ksm * 4 * KB / GB:.2f} GB)")
    print(f"   2. Balloon reclaim of cold pages in the enterprise tier (10%)"
          f"   -{balloon:>10,} frames  ({balloon * 4 * KB / GB:.2f} GB)")
    print(f"   3. Suspend the batch analytics tier when PFF > upper threshold"
          f"  -{suspend:>10,} frames  ({suspend * 4 * KB / GB:.2f} GB)")
    residual = demand - ksm - balloon - suspend
    print()
    print(f"   Residual demand D' = {residual:,} frames "
          f"({residual * 4 * KB / GB:.2f} GB)")
    print(f"   D' / m = {residual / available:.3f}"
          f"   -> {(1 - residual / available) * 100:.1f}% headroom  "
          f"{'FITS' if residual < available else 'STILL OVER-COMMITTED'}")
    print()
    print("   Resulting per-guest allocation rule (proportional + WS floor):")
    print("     frames_i = max( WSS_i(Delta) , (size_i / sum size) * m )")
    print("     subject to  sum frames_i <= m, batch tier suspendable")
    print()
    print("   PFF control band (Denning; Wulf's page-fault-frequency scheme):")
    print("     PFF_i > U = 0.50 faults/ms  ->  grant guest i more frames")
    print("     PFF_i < L = 0.10 faults/ms  ->  balloon frames back from guest i")
    print("     PFF_i > U and no free frame ->  SUSPEND lowest-priority guest")
    print("   Batch analytics is the designated victim class: it carries no")
    print("   interactive SLA, so suspending it protects the sub-10 ms response")
    print("   time that Section D requires of the web/DNS and enterprise tiers.")

    return {"working_set": ws_summary, "curve": curve, "util": util,
            "demand": demand, "available": available, "residual": residual,
            "best_n": best_n}


if __name__ == "__main__":
    main()
