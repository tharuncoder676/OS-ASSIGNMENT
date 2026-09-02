#!/usr/bin/env python3
"""
CloudMatrix - CO4 : File Allocation Strategies (Contiguous / Linked / Indexed)
=============================================================================

Simulates the three classical allocation methods on a shared block device and
measures, rather than asserts:

  * the block map each method produces for every file
  * whether an allocation succeeds or is refused, and why
  * unused blocks and metadata overhead
  * internal fragmentation (tail waste in the last block of each file)
  * external fragmentation, before and after a create/delete churn cycle
  * sequential and random block-access counts for each method

It then answers the question the brief actually asks: which method for
(a) tiny config files < 4 KB, (b) 10-100 MB web logs, (c) > 50 GB VM disk
images. Extent-based allocation is included as a fourth method because it is
what ext4/XFS genuinely use for case (c), and leaving it out would make the
recommendation historically accurate but practically wrong.

Run:  python src/co4_storage/file_allocation.py
"""

from __future__ import annotations

from dataclasses import dataclass, field

BLOCK_SIZE = 4096                 # bytes, matching the host page size
TOTAL_BLOCKS = 500                # the simulated device (Section D allows this)
POINTER_BYTES = 4                 # a block pointer
PTRS_PER_BLOCK = BLOCK_SIZE // POINTER_BYTES     # 1024

KB, MB, GB = 1024, 1024 ** 2, 1024 ** 3


# The CloudMatrix representative file set (8 files, four workload classes).
FILES = [
    # (name, bytes, access pattern)
    ("named.conf",            2_100,        "random"),
    ("dhcpd.conf",            3_400,        "random"),
    ("syslog-2026-09.log",    40 * 4096,    "sequential"),
    ("nginx-access.log",      60 * 4096,    "sequential"),
    ("tenant-db.dump",        95 * 4096,    "random"),
    ("guest-win11.vmdk",      120 * 4096,   "sequential"),
    ("guest-ubuntu.img",      90 * 4096,    "sequential"),
    ("backup-snapshot.tar",   70 * 4096,    "sequential"),
]


def blocks_needed(size_bytes: int) -> int:
    return max(1, -(-size_bytes // BLOCK_SIZE))     # ceiling division


# --------------------------------------------------------------------------
# The device
# --------------------------------------------------------------------------

@dataclass
class Disk:
    total: int = TOTAL_BLOCKS
    free: list = field(default_factory=lambda: [True] * TOTAL_BLOCKS)

    def free_count(self) -> int:
        return sum(self.free)

    def free_list(self) -> list[int]:
        return [i for i, f in enumerate(self.free) if f]

    def runs(self) -> list[tuple[int, int]]:
        """Contiguous free extents as (start, length)."""
        out, i = [], 0
        while i < self.total:
            if self.free[i]:
                s = i
                while i < self.total and self.free[i]:
                    i += 1
                out.append((s, i - s))
            else:
                i += 1
        return out

    def occupy(self, blocks) -> None:
        for b in blocks:
            self.free[b] = False

    def release(self, blocks) -> None:
        for b in blocks:
            self.free[b] = True

    def largest_run(self) -> int:
        r = self.runs()
        return max((ln for _, ln in r), default=0)

    def external_fragmentation(self) -> float:
        """1 - (largest free run / total free). 0 = perfectly contiguous."""
        fc = self.free_count()
        return 0.0 if fc == 0 else 1 - self.largest_run() / fc

    def bitmap(self, width: int = 100) -> str:
        rows = []
        for base in range(0, self.total, width):
            row = "".join("." if f else "#"
                          for f in self.free[base:base + width])
            rows.append(f"   {base:>4}| {row}")
        return "\n".join(rows)


# --------------------------------------------------------------------------
# Allocation methods
# --------------------------------------------------------------------------

def alloc_contiguous(disk: Disk, name: str, n: int) -> dict:
    for start, length in disk.runs():
        if length >= n:
            blocks = list(range(start, start + n))
            disk.occupy(blocks)
            return {"ok": True, "data": blocks, "meta": [], "start": start,
                    "note": f"start={start}, length={n}"}
    return {"ok": False, "data": [], "meta": [], "start": None,
            "note": f"REFUSED: needs {n} contiguous, largest run is "
                    f"{disk.largest_run()}"}


def alloc_linked(disk: Disk, name: str, n: int) -> dict:
    free = disk.free_list()
    if len(free) < n:
        return {"ok": False, "data": [], "meta": [], "start": None,
                "note": f"REFUSED: needs {n} blocks, only {len(free)} free"}
    blocks = free[:n]
    disk.occupy(blocks)
    return {"ok": True, "data": blocks, "meta": [], "start": blocks[0],
            "note": f"head={blocks[0]}, tail={blocks[-1]}, "
                    f"{n} next-pointers ({n * POINTER_BYTES} B stolen from data)"}


def alloc_indexed(disk: Disk, name: str, n: int) -> dict:
    index_blocks = max(1, -(-n // PTRS_PER_BLOCK))
    need = n + index_blocks
    free = disk.free_list()
    if len(free) < need:
        return {"ok": False, "data": [], "meta": [], "start": None,
                "note": f"REFUSED: needs {n} data + {index_blocks} index = "
                        f"{need}, only {len(free)} free"}
    meta = free[:index_blocks]
    data = free[index_blocks:need]
    disk.occupy(meta + data)
    return {"ok": True, "data": data, "meta": meta, "start": meta[0],
            "note": f"index block(s)={meta}, {n} data blocks"}


def alloc_extent(disk: Disk, name: str, n: int, max_extents: int = 4) -> dict:
    """Best-effort extent allocation: take the largest runs first, up to
    `max_extents` extents, which is how ext4 records a large file in its
    inode without any indirect block at all."""
    runs = sorted(disk.runs(), key=lambda r: -r[1])
    chosen, remaining = [], n
    for start, length in runs:
        if remaining <= 0 or len(chosen) >= max_extents:
            break
        take = min(length, remaining)
        chosen.append((start, take))
        remaining -= take
    if remaining > 0:
        return {"ok": False, "data": [], "meta": [], "start": None,
                "note": f"REFUSED: {n} blocks do not fit in {max_extents} extents"}
    data = [b for s, ln in chosen for b in range(s, s + ln)]
    disk.occupy(data)
    return {"ok": True, "data": data, "meta": [], "start": chosen[0][0],
            "extents": chosen,
            "note": f"{len(chosen)} extent(s): " +
                    ", ".join(f"[{s}..{s + ln - 1}]" for s, ln in chosen)}


METHODS = [
    ("Contiguous", alloc_contiguous),
    ("Linked", alloc_linked),
    ("Indexed", alloc_indexed),
    ("Extent (ext4-style)", alloc_extent),
]


# --------------------------------------------------------------------------
# Access-cost model
# --------------------------------------------------------------------------

def access_costs(method: str, n: int, k: int = 4) -> tuple[int, int]:
    """Return (sequential_ios, random_ios) to read a whole file sequentially
    and to read every k-th block in random order."""
    random_targets = max(1, n // k)
    if method == "Contiguous":
        return n, random_targets                       # direct: start + offset
    if method == "Linked":
        # sequential: follow the chain once. random: re-walk from the head,
        # average (i+1) hops for the i-th target.
        rnd = sum(k * i + 1 for i in range(random_targets))
        return n, rnd
    if method == "Indexed":
        idx = max(1, -(-n // PTRS_PER_BLOCK))
        return idx + n, idx + random_targets           # one index read, then direct
    if method.startswith("Extent"):
        # the extent map lives in the inode itself: no extra block read at all
        return n, random_targets
    raise ValueError(method)


# --------------------------------------------------------------------------

def run_allocation_round(method_name: str, allocator) -> tuple[Disk, dict]:
    disk = Disk()
    table = {}
    for name, size, pattern in FILES:
        n = blocks_needed(size)
        res = allocator(disk, name, n)
        res["need"] = n
        res["size"] = size
        res["pattern"] = pattern
        res["internal_waste"] = n * BLOCK_SIZE - size
        table[name] = res
    return disk, table


def compress(blocks: list[int]) -> str:
    """Render a block list as ranges: [0..5, 12, 20..22]."""
    if not blocks:
        return "-"
    out, s, p = [], blocks[0], blocks[0]
    for b in blocks[1:]:
        if b == p + 1:
            p = b
            continue
        out.append(f"{s}" if s == p else f"{s}-{p}")
        s = p = b
    out.append(f"{s}" if s == p else f"{s}-{p}")
    joined = ", ".join(out)
    return joined if len(joined) <= 46 else joined[:43] + "..."


def main():
    print("=" * 78)
    print(" CO4.1  FILE ALLOCATION - CloudMatrix representative file set")
    print("=" * 78)
    print(f"   Device       : {TOTAL_BLOCKS} blocks x {BLOCK_SIZE // KB} KB "
          f"= {TOTAL_BLOCKS * BLOCK_SIZE / MB:.2f} MB")
    print(f"   Pointers/block: {PTRS_PER_BLOCK}")
    print()
    print(f"   {'File':<24}{'Size (B)':>12}{'Blocks':>8}{'Tail waste (B)':>16}"
          f"   Access")
    total_need = 0
    for name, size, pattern in FILES:
        n = blocks_needed(size)
        total_need += n
        print(f"   {name:<24}{size:>12,}{n:>8}{n * BLOCK_SIZE - size:>16,}"
              f"   {pattern}")
    print(f"   {'TOTAL':<24}{sum(s for _, s, _ in FILES):>12,}{total_need:>8}"
          f"{sum(blocks_needed(s) * BLOCK_SIZE - s for _, s, _ in FILES):>16,}")

    summaries, disks, tables = {}, {}, {}
    for mname, allocator in METHODS:
        disk, table = run_allocation_round(mname, allocator)
        disks[mname], tables[mname] = disk, table
        print()
        print(f"  --- {mname} allocation " + "-" * (58 - len(mname)))
        print(f"   {'File':<24}{'Blk':>5}{'Status':>10}   Block map / metadata")
        for name, _, _ in FILES:
            r = table[name]
            status = "OK" if r["ok"] else "REFUSED"
            if r["ok"]:
                detail = compress(r["data"])
                if r["meta"]:
                    detail = f"idx {compress(r['meta'])} -> " + detail
            else:
                detail = r["note"]
            print(f"   {name:<24}{r['need']:>5}{status:>10}   {detail}")
        used = TOTAL_BLOCKS - disk.free_count()
        meta = sum(len(r["meta"]) for r in table.values())
        data = sum(len(r["data"]) for r in table.values())
        placed = sum(1 for r in table.values() if r["ok"])
        internal = sum(r["internal_waste"] for r in table.values() if r["ok"])
        if mname == "Linked":
            meta_bytes = data * POINTER_BYTES
        else:
            meta_bytes = meta * BLOCK_SIZE
        summaries[mname] = {
            "placed": placed, "used": used, "free": disk.free_count(),
            "data": data, "meta": meta, "meta_bytes": meta_bytes,
            "internal": internal,
            "util": used / TOTAL_BLOCKS * 100,
            "extfrag": disk.external_fragmentation(),
        }
        print(f"   Files placed {placed}/{len(FILES)}   data blocks {data}"
              f"   metadata blocks {meta}   used {used}   free {disk.free_count()}")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO4.1  ALLOCATION SUMMARY")
    print("=" * 78)
    print(f"   {'Method':<22}{'Placed':>8}{'Used':>7}{'Free':>7}{'Util %':>9}"
          f"{'Meta (B)':>11}{'Internal (B)':>14}")
    for mname, _ in METHODS:
        s = summaries[mname]
        print(f"   {mname:<22}{s['placed']:>8}{s['used']:>7}{s['free']:>7}"
              f"{s['util']:>9.1f}{s['meta_bytes']:>11,}{s['internal']:>14,}")
    print()
    print("   Internal fragmentation is identical for every method (it is a")
    print("   property of the block size, not the allocator). Metadata overhead")
    print("   is where the methods genuinely differ.")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO4.2  ACCESS COST - block I/Os for sequential vs random reads")
    print("=" * 78)
    probes = [("nginx-access.log", "sequential"), ("tenant-db.dump", "random")]
    for fname, pattern in probes:
        n = blocks_needed(dict((f[0], f[1]) for f in FILES)[fname])
        print()
        print(f"   {fname}  ({n} blocks, {pattern}-access workload)")
        print(f"   {'Method':<22}{'Sequential I/Os':>18}{'Random I/Os':>14}"
              f"{'Random penalty':>17}")
        base = None
        for mname, _ in METHODS:
            seq, rnd = access_costs(mname, n)
            if base is None:
                base = rnd
            print(f"   {mname:<22}{seq:>18,}{rnd:>14,}{rnd / base:>16.1f}x")
    print()
    print("   Linked allocation is the outlier by two orders of magnitude on")
    print("   random access, because reaching block i costs i pointer hops and")
    print("   there is no way to shortcut the chain. For tenant-db.dump this is")
    print("   the difference between 23 I/Os and 1,035 -- a 45x penalty.")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO4.2  EXTERNAL FRAGMENTATION UNDER CREATE/DELETE CHURN")
    print("=" * 78)
    disk = disks["Contiguous"]
    table = tables["Contiguous"]
    print("   Free-space map after the initial contiguous allocation")
    print("   ('#' = allocated, '.' = free)")
    print(disk.bitmap())
    print(f"   Free {disk.free_count()} blocks, largest run "
          f"{disk.largest_run()}, external fragmentation "
          f"{disk.external_fragmentation():.3f}")

    deletions = ["syslog-2026-09.log", "tenant-db.dump", "guest-ubuntu.img"]
    for d in deletions:
        disk.release(table[d]["data"] + table[d]["meta"])
    print()
    print(f"   After deleting {', '.join(deletions)}:")
    print(disk.bitmap())
    print(f"   Free {disk.free_count()} blocks, largest run "
          f"{disk.largest_run()}, external fragmentation "
          f"{disk.external_fragmentation():.3f}")
    print(f"   Free extents: {disk.runs()}")

    newfile_blocks = 150
    print()
    print(f"   Now create rebuild-2026.vmdk requiring {newfile_blocks} blocks:")
    for mname, allocator in METHODS:
        probe = Disk()
        probe.free = list(disks["Contiguous"].free) if mname == "Contiguous" else None
        # rebuild each method's post-deletion state faithfully
        d2, t2 = run_allocation_round(mname, allocator)
        for f in deletions:
            d2.release(t2[f]["data"] + t2[f]["meta"])
        res = allocator(d2, "rebuild-2026.vmdk", newfile_blocks)
        verdict = "ALLOCATED" if res["ok"] else "FAILED"
        print(f"     {mname:<22}{verdict:<11}{res['note']}")
    print()
    print(f"   The disk holds {disk.free_count()} free blocks -- comfortably more")
    print(f"   than the {newfile_blocks} requested -- yet contiguous allocation")
    print("   refuses the request because no single run is large enough. That is")
    print("   external fragmentation stated as a measurement rather than a")
    print("   definition, and it is the failure mode that rules contiguous")
    print("   allocation out for a platform with constant VM churn.")

    # ------------------------------------------------------------------
    print()
    print("=" * 78)
    print(" CO4.1  RECOMMENDATION BY FILE CLASS")
    print("=" * 78)
    classes = [
        ("(a) Config files  < 4 KB", "named.conf, dhcpd.conf, resolv.conf",
         "Inline / direct blocks in the inode",
         "One block, one I/O. Indexing costs a whole extra 4 KB block for a "
         "2 KB file -- 200% overhead. Modern ext4 inlines such files in the "
         "inode's 60-byte i_block area, so the read costs zero data I/Os."),
        ("(b) Web logs 10-100 MB", "nginx-access.log, syslog",
         "Indexed (single + double indirect)",
         "Append-heavy and read sequentially, but occasionally grepped at "
         "random offsets. Indexed gives O(1) random reach for ~0.1% metadata "
         "overhead, and the file grows without needing contiguous space."),
        ("(c) VM images  > 50 GB", "guest-win11.vmdk, guest-ubuntu.img",
         "Extent-based (ext4/XFS extents)",
         "A 50 GB file is 13,107,200 blocks; a classical index would need "
         "12,814 metadata blocks. Four extents describe the same file in 48 "
         "bytes inside the inode, and keep the physical layout sequential for "
         "streaming reads."),
    ]
    for title, examples, rec, why in classes:
        print()
        print(f"   {title}")
        print(f"     examples       : {examples}")
        print(f"     RECOMMENDATION : {rec}")
        print(f"     justification  : {why}")

    return summaries


if __name__ == "__main__":
    main()
