#!/usr/bin/env python3
"""
CloudMatrix - CO3 : Page Replacement Trace, Belady's Anomaly and PFF Control
===========================================================================

Implements FIFO, LRU and OPT (Belady's optimal) replacement, prints the full
step-by-step frame table that the report reproduces, compares 3-frame against
4-frame allocations, and tests explicitly for Belady's anomaly.

The reference string is the CloudMatrix guest-VM trace W (18 references over
7 distinct pages).  It is deliberately constructed so that the FIFO anomaly is
exposed rather than hidden -- a negative result is still a result.

Run:  python src/co3_memory/page_replacement.py
"""

from __future__ import annotations

from dataclasses import dataclass

# The CloudMatrix guest-VM page reference trace (18 references, 7 pages).
#   pages 2..5 = enterprise application text/data pages
#   page  1    = shared libc page brought in late by dynamic linking
#   pages 6,7  = the batch-analytics scan phase that starts at reference 13
REFERENCE_STRING = [2, 3, 4, 5, 2, 3, 1, 2, 3, 4, 5, 1, 6, 7, 6, 7, 6, 7]


@dataclass
class Result:
    name: str
    frames: int
    faults: int
    hits: int
    steps: list

    @property
    def fault_rate(self) -> float:
        return self.faults / (self.faults + self.hits)

    @property
    def hit_ratio(self) -> float:
        return self.hits / (self.faults + self.hits)


def _snapshot(mem: list, frames: int) -> str:
    cells = [str(mem[i]) if i < len(mem) else "-" for i in range(frames)]
    return " ".join(f"{c:>2}" for c in cells)


# --------------------------------------------------------------------------
# Algorithms
# --------------------------------------------------------------------------

def fifo(ref: list[int], frames: int) -> Result:
    mem: list[int] = []
    faults = hits = 0
    steps = []
    for i, page in enumerate(ref):
        if page in mem:
            hits += 1
            victim, event = None, "HIT"
        else:
            faults += 1
            if len(mem) >= frames:
                victim = mem.pop(0)          # oldest arrival leaves
                event = f"FAULT (evict {victim})"
            else:
                victim, event = None, "FAULT (free frame)"
            mem.append(page)
        steps.append((i + 1, page, _snapshot(mem, frames), event))
    return Result("FIFO", frames, faults, hits, steps)


def lru(ref: list[int], frames: int) -> Result:
    mem: list[int] = []                       # mem[0] = least recently used
    faults = hits = 0
    steps = []
    for i, page in enumerate(ref):
        if page in mem:
            hits += 1
            mem.remove(page)
            mem.append(page)
            event = "HIT"
        else:
            faults += 1
            if len(mem) >= frames:
                victim = mem.pop(0)
                event = f"FAULT (evict {victim})"
            else:
                event = "FAULT (free frame)"
            mem.append(page)
        steps.append((i + 1, page, _snapshot(sorted(mem), frames), event))
    return Result("LRU", frames, faults, hits, steps)


def optimal(ref: list[int], frames: int) -> Result:
    mem: list[int] = []
    faults = hits = 0
    steps = []
    for i, page in enumerate(ref):
        if page in mem:
            hits += 1
            event = "HIT"
        else:
            faults += 1
            if len(mem) >= frames:
                # evict the resident page whose next use is furthest away
                furthest, victim = -1, mem[0]
                for candidate in mem:
                    try:
                        nxt = ref.index(candidate, i + 1)
                    except ValueError:
                        nxt = float("inf")
                    if nxt > furthest:
                        furthest, victim = nxt, candidate
                mem.remove(victim)
                event = f"FAULT (evict {victim})"
            else:
                event = "FAULT (free frame)"
            mem.append(page)
        steps.append((i + 1, page, _snapshot(sorted(mem), frames), event))
    return Result("OPTIMAL", frames, faults, hits, steps)


ALGORITHMS = {"FIFO": fifo, "LRU": lru, "OPTIMAL": optimal}


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def print_trace(res: Result) -> None:
    print()
    print(f"  --- {res.name} with {res.frames} frames "
          f"------------------------------------------".ljust(74, "-"))
    print(f"   {'#':>3}  {'Ref':>3}   {'Frames':<{3 * res.frames}}   Event")
    for n, page, snap, event in res.steps:
        print(f"   {n:>3}  {page:>3}   {snap:<{3 * res.frames}}   {event}")
    print(f"   Page faults = {res.faults} / {len(res.steps)}"
          f"   fault rate = {res.fault_rate * 100:.2f}%"
          f"   hit ratio = {res.hit_ratio * 100:.2f}%")


def run(ref: list[int] = None, verbose: bool = True) -> dict:
    ref = ref or REFERENCE_STRING
    print("=" * 78)
    print(" CO3.3  PAGE REPLACEMENT TRACE - CloudMatrix guest-VM workload")
    print("=" * 78)
    print(f"   Reference string W ({len(ref)} references, "
          f"{len(set(ref))} distinct pages):")
    print("   " + ", ".join(str(p) for p in ref))

    table = {}
    for frames in (3, 4):
        for name, fn in ALGORITHMS.items():
            res = fn(ref, frames)
            table[(name, frames)] = res
            if verbose:
                print_trace(res)

    print()
    print("=" * 78)
    print(" CO3.3  SUMMARY - page faults by algorithm and frame allocation")
    print("=" * 78)
    print(f"   {'Algorithm':<12}{'3 frames':>12}{'4 frames':>12}"
          f"{'Change':>12}{'Fault rate (4f)':>18}")
    for name in ALGORITHMS:
        f3, f4 = table[(name, 3)].faults, table[(name, 4)].faults
        delta = f4 - f3
        arrow = "improves" if delta < 0 else ("ANOMALY +" if delta > 0 else "no change")
        print(f"   {name:<12}{f3:>12}{f4:>12}{arrow + ' ' + str(abs(delta)) if delta else arrow:>12}"
              f"{table[(name, 4)].fault_rate * 100:>17.2f}%")

    print()
    print("=" * 78)
    print(" CO3.3  BELADY'S ANOMALY TEST")
    print("=" * 78)
    anomaly = False
    for name in ALGORITHMS:
        f3, f4 = table[(name, 3)].faults, table[(name, 4)].faults
        if f4 > f3:
            anomaly = True
            print(f"   {name}: {f3} faults with 3 frames -> {f4} faults with 4 frames.")
            print(f"   ANOMALY CONFIRMED. Adding a frame made {name} strictly worse")
            print(f"   on this trace ({f4 - f3} extra fault(s), "
                  f"{(f4 - f3) / f3 * 100:.1f}% regression).")
        else:
            print(f"   {name}: {f3} -> {f4} faults. No anomaly "
                  f"({'stack algorithm, provably immune' if name in ('LRU', 'OPTIMAL') else 'not exhibited'}).")
    if anomaly:
        print()
        print("   Engineering consequence for CloudMatrix: because FIFO is not a stack")
        print("   algorithm, the inclusion property mu(m) subset-of mu(m+1) does not hold,")
        print("   so a memory-ballooning controller that hands a guest extra frames has")
        print("   NO monotonic guarantee of fewer faults under FIFO. LRU and OPT are")
        print("   stack algorithms and cannot regress, which is decisive for a platform")
        print("   whose frames are continuously resized by the balloon driver.")
    return table


if __name__ == "__main__":
    run()
