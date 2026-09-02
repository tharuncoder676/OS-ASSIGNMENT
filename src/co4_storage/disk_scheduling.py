#!/usr/bin/env python3
"""
CloudMatrix - CO4 : Block Disk Scheduling (FCFS, SSTF, SCAN, C-SCAN, LOOK)
=========================================================================

Computes total head movement, average seek distance, service order, per-request
waiting distance and the starvation profile for the CloudMatrix block storage
unit specified in Section D of the brief:

    Cylinders        : 0 - 499  (500-cylinder virtual block storage unit)
    Pending queue    : 86, 147, 312, 91, 177, 48, 409, 22, 130, 365, 220, 480
    Initial head     : cylinder 125
    Direction        : towards higher cylinder numbers

C-LOOK is included as a sixth algorithm because it is what the Linux deadline
and mq-deadline schedulers actually approximate, and omitting it would leave
the recommendation unsupported.

Seek-time model: t_seek = t_settle + d * t_per_cyl, with t_settle = 0.5 ms and
t_per_cyl = 0.01 ms, matching a mid-range enterprise SAS spindle. The model is
applied uniformly so the comparison between algorithms is fair.

Run:  python src/co4_storage/disk_scheduling.py
"""

from __future__ import annotations

DISK_MIN, DISK_MAX = 0, 499
QUEUE = [86, 147, 312, 91, 177, 48, 409, 22, 130, 365, 220, 480]
HEAD = 125
DIRECTION = "up"

SETTLE_MS = 0.5          # head settle / rotational overhead per seek
PER_CYL_MS = 0.01        # per-cylinder traversal cost


# --------------------------------------------------------------------------
# Algorithms -- each returns the full ordered service path INCLUDING the head
# --------------------------------------------------------------------------

def fcfs(queue, head, *_):
    return [head] + list(queue)


def sstf(queue, head, *_):
    pending, path, cur = list(queue), [head], head
    while pending:
        nxt = min(pending, key=lambda c: abs(c - cur))
        pending.remove(nxt)
        path.append(nxt)
        cur = nxt
    return path


def scan(queue, head, lo=DISK_MIN, hi=DISK_MAX, direction=DIRECTION):
    """Elevator: sweep to the physical end of the disk, then reverse."""
    left = sorted(c for c in queue if c < head)
    right = sorted(c for c in queue if c >= head)
    if direction == "up":
        path = [head] + right
        if left:                       # only walk to the end if we must turn
            if path[-1] != hi:
                path.append(hi)
            path += left[::-1]
        return path
    path = [head] + left[::-1]
    if right:
        if path[-1] != lo:
            path.append(lo)
        path += right
    return path


def cscan(queue, head, lo=DISK_MIN, hi=DISK_MAX, direction=DIRECTION):
    """Circular SCAN: sweep up to the end, jump back to 0, resume upward.
    The return jump is counted as head movement, which is the convention used
    throughout this report and stated in the results table."""
    left = sorted(c for c in queue if c < head)
    right = sorted(c for c in queue if c >= head)
    path = [head] + right
    if left:
        if path[-1] != hi:
            path.append(hi)
        path.append(lo)
        path += left
    return path


def look(queue, head, lo=DISK_MIN, hi=DISK_MAX, direction=DIRECTION):
    left = sorted(c for c in queue if c < head)
    right = sorted(c for c in queue if c >= head)
    # like SCAN but never travels past the last request in the sweep direction
    return [head] + right + left[::-1]


def clook(queue, head, lo=DISK_MIN, hi=DISK_MAX, direction=DIRECTION):
    left = sorted(c for c in queue if c < head)
    right = sorted(c for c in queue if c >= head)
    return [head] + right + left


ALGORITHMS = [
    ("FCFS", fcfs), ("SSTF", sstf), ("SCAN", scan),
    ("C-SCAN", cscan), ("LOOK", look), ("C-LOOK", clook),
]


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------

def total_movement(path):
    return sum(abs(path[i + 1] - path[i]) for i in range(len(path) - 1))


def seek_time_ms(path):
    """Sum of per-seek times; a zero-distance step still costs a settle."""
    return sum(SETTLE_MS + abs(path[i + 1] - path[i]) * PER_CYL_MS
               for i in range(len(path) - 1))


def waiting_profile(path, queue):
    """Cumulative head distance travelled before each request is served."""
    dist, seen, out = 0.0, set(), {}
    for i in range(1, len(path)):
        dist += abs(path[i] - path[i - 1])
        c = path[i]
        if c in queue and c not in seen:
            out[c] = dist
            seen.add(c)
    return out


def analyse(name, fn):
    path = fn(QUEUE, HEAD)
    served = [c for c in path[1:] if c in QUEUE]
    tm = total_movement(path)
    wait = waiting_profile(path, QUEUE)
    return {
        "name": name,
        "path": path,
        "order": served,
        "total": tm,
        "avg": tm / len(QUEUE),
        "seek_ms": seek_time_ms(path),
        "wait": wait,
        "max_wait": max(wait.values()),
        "starved": max(wait, key=wait.get),
    }


# --------------------------------------------------------------------------

def main():
    print("=" * 78)
    print(" CO4.3  DISK HEAD MOVEMENT - CloudMatrix 500-cylinder block store")
    print("=" * 78)
    print(f"   Cylinder range   : {DISK_MIN} - {DISK_MAX}")
    print(f"   Pending queue    : {QUEUE}")
    print(f"   Requests         : {len(QUEUE)}")
    print(f"   Initial head     : cylinder {HEAD}, moving towards higher cylinders")
    print(f"   Seek model       : t = {SETTLE_MS} ms settle + "
          f"{PER_CYL_MS} ms per cylinder")

    results = []
    for name, fn in ALGORITHMS:
        r = analyse(name, fn)
        results.append(r)
        print()
        print(f"  --- {name} " + "-" * (70 - len(name)))
        print("   Service order :")
        print("     " + " -> ".join(str(c) for c in r["path"]))
        steps = " + ".join(
            str(abs(r["path"][i + 1] - r["path"][i]))
            for i in range(len(r["path"]) - 1))
        print(f"   Head movement : {steps}")
        print(f"                 = {r['total']} cylinders")
        print(f"   Average seek  : {r['total']} / {len(QUEUE)} "
              f"= {r['avg']:.2f} cylinders per request")
        print(f"   Seek time     : {r['seek_ms']:.2f} ms total, "
              f"{r['seek_ms'] / len(QUEUE):.3f} ms per request")
        print(f"   Worst wait    : cylinder {r['starved']} served after "
              f"{r['max_wait']:.0f} cylinders of travel")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO4.3  COMPARATIVE SUMMARY")
    print("=" * 78)
    print(f"   {'Algorithm':<10}{'Total move':>12}{'Avg seek':>11}"
          f"{'Seek time':>12}{'Worst wait':>12}{'vs FCFS':>10}")
    print(f"   {'':<10}{'(cylinders)':>12}{'(cyl/req)':>11}"
          f"{'(ms)':>12}{'(cylinders)':>12}{'':>10}")
    base = results[0]["total"]
    for r in results:
        improve = (base - r["total"]) / base * 100
        print(f"   {r['name']:<10}{r['total']:>12}{r['avg']:>11.2f}"
              f"{r['seek_ms']:>12.2f}{r['max_wait']:>12.0f}"
              f"{improve:>9.1f}%")

    best = min(results, key=lambda r: r["total"])
    fair = min(results, key=lambda r: r["max_wait"])
    print()
    print(f"   Lowest total head movement : {best['name']} "
          f"({best['total']} cylinders)")
    print(f"   Lowest worst-case wait     : {fair['name']} "
          f"({fair['max_wait']:.0f} cylinders)")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO4.3  STARVATION / FAIRNESS PROFILE")
    print("=" * 78)
    print("   Distance the head travels before each request is served:")
    header = "   " + f"{'Cylinder':<10}" + "".join(f"{r['name']:>9}" for r in results)
    print(header)
    for c in sorted(QUEUE):
        row = f"   {c:<10}" + "".join(f"{r['wait'][c]:>9.0f}" for r in results)
        print(row)
    print()
    spread = {r["name"]: max(r["wait"].values()) - min(r["wait"].values())
              for r in results}
    print("   Wait spread (max - min), a direct proxy for unfairness:")
    for name, s in sorted(spread.items(), key=lambda kv: kv[1]):
        print(f"     {name:<10}{s:>8.0f} cylinders")
    print()
    print("   SSTF's low total movement is bought by leaving cylinder 22 and 48")
    print("   unserved until the very end of the sweep -- the classic SSTF")
    print("   starvation signature. Under a continuously refilled CloudMatrix")
    print("   queue those far-edge requests may never be served at all, because")
    print("   SSTF has no mechanism that guarantees forward progress.")
    return results


if __name__ == "__main__":
    main()
