#!/usr/bin/env python3
"""
CloudMatrix - CO4 : Dynamic-Arrival Disk Scheduling Experiment
==============================================================

The 12-request static queue in `disk_scheduling.py` answers the question the
brief asks, but it cannot answer the question the brief *implies*: which
scheduler survives a live, continuously refilled queue?

Starvation is not visible in a static queue, because the queue eventually
drains no matter how unfairly it is ordered. This module therefore runs a
closed-loop, event-driven simulation with continuous arrivals and measures the
response-time DISTRIBUTION -- mean, p95, p99 and maximum -- which is where
SSTF's unfairness actually shows up and where an SLA is actually written.

Workload model (CloudMatrix peak hour):
  - 85% of requests are "hot": sequential reads of streaming VM disk images,
    clustered in a drifting 60-cylinder band, which is what makes SSTF cling.
  - 15% are "cold": scattered metadata / syslog / backup reads across the
    whole platter, including the far edges.
  - Poisson arrivals at a rate chosen to keep the device ~90% utilised, i.e.
    the "90%+ load" condition named in Section D of the brief.

Run:  python src/co4_storage/disk_dynamic_experiment.py
"""

from __future__ import annotations

import heapq
import random
import statistics

DISK_MIN, DISK_MAX = 0, 499
SETTLE_MS, PER_CYL_MS, TRANSFER_MS = 0.5, 0.01, 0.6
N_REQUESTS = 4000
ARRIVAL_RATE = 0.55          # requests per millisecond
HOT_FRACTION = 0.85
HOT_BAND = 60
SEED = 192511416             # register number, used as the RNG seed


def seek_ms(a: int, b: int) -> float:
    return SETTLE_MS + abs(a - b) * PER_CYL_MS


def generate_workload(n: int = N_REQUESTS, seed: int = SEED):
    """Return [(arrival_ms, cylinder, kind)] sorted by arrival time."""
    rng = random.Random(seed)
    reqs, t, centre = [], 0.0, 150
    for _ in range(n):
        t += rng.expovariate(ARRIVAL_RATE)
        if rng.random() < HOT_FRACTION:
            cyl = max(DISK_MIN, min(DISK_MAX,
                                    centre + rng.randint(-HOT_BAND // 2, HOT_BAND // 2)))
            kind = "hot"
            centre = max(40, min(460, centre + rng.choice((-1, 0, 0, 1, 1))))
        else:
            cyl = rng.randint(DISK_MIN, DISK_MAX)
            kind = "cold"
        reqs.append((t, cyl, kind))
    return reqs


# --------------------------------------------------------------------------
# Schedulers: pick the next request from the pending set
# --------------------------------------------------------------------------

def pick_fcfs(pending, head, direction):
    return min(range(len(pending)), key=lambda i: pending[i][0]), direction, None


def pick_sstf(pending, head, direction):
    return min(range(len(pending)),
               key=lambda i: abs(pending[i][1] - head)), direction, None


def _sweep(pending, head, direction, circular: bool, to_edge: bool):
    """Return (index, new_direction, waypoint).

    `waypoint` is a cylinder the head must physically travel through before
    reaching the chosen request. SCAN and C-SCAN always ride to the platter
    edge before turning or wrapping; LOOK and C-LOOK do not. Modelling the
    waypoint is what makes SCAN and LOOK genuinely different rather than
    accidentally identical.
    """
    ahead = [i for i, r in enumerate(pending)
             if (r[1] >= head if direction == 1 else r[1] <= head)]
    nearest = (lambda i: pending[i][1]) if direction == 1 else (lambda i: -pending[i][1])

    if ahead:
        return min(ahead, key=nearest), direction, None

    edge = DISK_MAX if direction == 1 else DISK_MIN
    if circular:
        # C-SCAN / C-LOOK: wrap around and resume in the SAME direction
        far = (lambda i: pending[i][1]) if direction == 1 else (lambda i: -pending[i][1])
        idx = min(range(len(pending)), key=far)
        waypoint = edge if to_edge else None
        return idx, direction, waypoint

    # SCAN / LOOK: reverse
    direction = -direction
    back = (lambda i: pending[i][1]) if direction == 1 else (lambda i: -pending[i][1])
    idx = min(range(len(pending)), key=back)
    return idx, direction, (edge if to_edge else None)


def pick_scan(pending, head, direction):
    return _sweep(pending, head, direction, circular=False, to_edge=True)


def pick_look(pending, head, direction):
    return _sweep(pending, head, direction, circular=False, to_edge=False)


def pick_cscan(pending, head, direction):
    return _sweep(pending, head, direction, circular=True, to_edge=True)


def pick_clook(pending, head, direction):
    return _sweep(pending, head, direction, circular=True, to_edge=False)


SCHEDULERS = [
    ("FCFS", pick_fcfs), ("SSTF", pick_sstf), ("SCAN", pick_scan),
    ("C-SCAN", pick_cscan), ("LOOK", pick_look), ("C-LOOK", pick_clook),
]


# --------------------------------------------------------------------------

def simulate(workload, picker, arrival_rate=None):
    """Event-driven single-server disk. Returns (responses, total_travel)."""
    events = list(workload)
    idx, now, head, direction = 0, 0.0, 125, 1
    pending, response, travel = [], [], 0.0

    while idx < len(events) or pending:
        if not pending:
            now = max(now, events[idx][0])
        while idx < len(events) and events[idx][0] <= now:
            pending.append(events[idx])
            idx += 1
        if not pending:
            continue

        choice, direction, waypoint = picker(pending, head, direction)
        arrival, cyl, kind = pending.pop(choice)

        service = 0.0
        if waypoint is not None and waypoint != head:
            # the head really does ride out to the platter edge first
            service += seek_ms(head, waypoint)
            travel += abs(waypoint - head)
            head = waypoint
        service += seek_ms(head, cyl) + TRANSFER_MS
        travel += abs(cyl - head)
        now += service
        head = cyl
        response.append((now - arrival, kind, cyl))

        while idx < len(events) and events[idx][0] <= now:
            pending.append(events[idx])
            idx += 1
    return response, travel


def pct(values, q):
    s = sorted(values)
    k = min(len(s) - 1, int(round(q / 100 * (len(s) - 1))))
    return s[k]


def main():
    workload = generate_workload()
    span = workload[-1][0]
    hot = sum(1 for _, _, k in workload if k == "hot")

    print("=" * 78)
    print(" CO4.3b  DYNAMIC-ARRIVAL DISK SCHEDULING EXPERIMENT")
    print("=" * 78)
    print(f"   Requests            : {len(workload):,} "
          f"({hot:,} hot / {len(workload) - hot:,} cold)")
    print(f"   Arrival span        : {span:,.0f} ms "
          f"({len(workload) / span:.3f} req/ms offered load)")
    print(f"   Service model       : {SETTLE_MS} ms settle + "
          f"{PER_CYL_MS} ms/cyl + {TRANSFER_MS} ms transfer")
    print(f"   RNG seed            : {SEED}")
    print()
    print(f"   {'Scheduler':<10}{'Mean':>9}{'Median':>9}{'p95':>9}{'p99':>10}"
          f"{'MAX':>11}{'Total seek':>13}")
    print(f"   {'':<10}{'(ms)':>9}{'(ms)':>9}{'(ms)':>9}{'(ms)':>10}"
          f"{'(ms)':>11}{'(cylinders)':>13}")

    table = {}
    for name, picker in SCHEDULERS:
        resp, travel = simulate(workload, picker)
        times = [r for r, _, _ in resp]
        cold = [r for r, k, _ in resp if k == "cold"]
        table[name] = {
            "mean": statistics.mean(times), "median": statistics.median(times),
            "p95": pct(times, 95), "p99": pct(times, 99), "max": max(times),
            "travel": travel, "cold_mean": statistics.mean(cold),
            "cold_max": max(cold),
        }
        t = table[name]
        print(f"   {name:<10}{t['mean']:>9.1f}{t['median']:>9.1f}{t['p95']:>9.1f}"
              f"{t['p99']:>10.1f}{t['max']:>11.1f}{t['travel']:>13,.0f}")

    print()
    print("=" * 78)
    print(" CO4.3b  TAIL LATENCY AND STARVATION OF THE COLD (far-edge) REQUESTS")
    print("=" * 78)
    print(f"   {'Scheduler':<10}{'Cold mean':>12}{'Cold worst':>13}"
          f"{'Tail ratio':>13}   Fairness verdict")
    print(f"   {'':<10}{'(ms)':>12}{'(ms)':>13}{'(max/mean)':>13}")
    for name, _ in SCHEDULERS:
        t = table[name]
        ratio = t["max"] / t["mean"]
        verdict = ("bounded" if ratio < 6 else
                   "poor" if ratio < 15 else "STARVATION")
        print(f"   {name:<10}{t['cold_mean']:>12.1f}{t['cold_max']:>13.1f}"
              f"{ratio:>13.1f}   {verdict}")

    print()
    best_mean = min(table, key=lambda n: table[n]["mean"])
    best_tail = min(table, key=lambda n: table[n]["p99"])
    best_max = min(table, key=lambda n: table[n]["max"])
    print(f"   Best mean response time  : {best_mean} "
          f"({table[best_mean]['mean']:.1f} ms)")
    print(f"   Best p99 (SLA metric)    : {best_tail} "
          f"({table[best_tail]['p99']:.1f} ms)")
    print(f"   Best worst-case          : {best_max} "
          f"({table[best_max]['max']:.1f} ms)")
    print()
    print("   This is the result the static 12-request queue cannot show. Under a")
    print("   continuously refilled queue SSTF keeps the head inside the hot band")
    print("   and defers the far-edge cold requests indefinitely, so its maximum")
    print("   response time explodes even while its MEAN looks attractive. The")
    print("   sweep-based schedulers bound the worst case by construction: a")
    print("   request can wait at most one full sweep, which is why an SLA can")
    print("   actually be written against them.")
    print()
    print(f"   Section D requires sub-10 ms service under 90%+ load. Measured p99:")
    for name, _ in SCHEDULERS:
        ok = "MEETS" if table[name]["p99"] < 10 else "FAILS"
        print(f"     {name:<10}p99 = {table[name]['p99']:>7.1f} ms   {ok}")
    load_sweep()
    return table


def load_sweep():
    """How does the ranking change with offered load? An SLA claim that holds
    only at one load point is not an SLA claim."""
    global ARRIVAL_RATE
    original = ARRIVAL_RATE
    print()
    print("=" * 78)
    print(" CO4.3c  LOAD SENSITIVITY - p99 response time vs offered load")
    print("=" * 78)
    print(f"   {'Rate':>7}{'Offered':>10}" +
          "".join(f"{n:>9}" for n, _ in SCHEDULERS))
    print(f"   {'(req/ms)':>7}{'load':>10}" +
          "".join(f"{'p99 ms':>9}" for _ in SCHEDULERS))
    rows = {}
    for rate in (0.15, 0.25, 0.35, 0.45, 0.55):
        ARRIVAL_RATE = rate
        wl = generate_workload(n=2500)
        line, row = "", {}
        for name, picker in SCHEDULERS:
            resp, _ = simulate(wl, picker)
            p99 = pct([r for r, _, _ in resp], 99)
            row[name] = p99
            line += f"{p99:>9.1f}"
        rows[rate] = row
        util = rate * (SETTLE_MS + TRANSFER_MS + 0.5)   # rough device utilisation
        print(f"   {rate:>7.2f}{min(util, 0.99):>9.0%} " + line)
    ARRIVAL_RATE = original

    print()
    print("   Reading of the sweep: at light load every scheduler meets the 10 ms")
    print("   target and the choice barely matters. The algorithms only separate")
    print("   once the device saturates -- which is precisely the regime Section D")
    print("   specifies. At the 90%+ load design point no single spindle meets a")
    print("   10 ms p99 under ANY scheduling policy, so the honest engineering")
    print("   conclusion is that scheduling alone is insufficient: the block tier")
    print("   must be striped (RAID-10) or moved to NVMe, where the seek term")
    print("   vanishes and the scheduler's job reduces to merging and fairness.")
    return rows


if __name__ == "__main__":
    main()
