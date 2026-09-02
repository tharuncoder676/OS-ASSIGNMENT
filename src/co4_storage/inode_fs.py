#!/usr/bin/env python3
"""
CloudMatrix - CO4 : UNIX Inode Dynamics, Kernel System Calls, Buffer Cache
=========================================================================

Implements a working miniature UNIX file system so that the kernel algorithms
the brief asks about can be TRACED rather than described:

    ialloc()  - assign a free inode from the super-block cache
    ifree()   - return an inode to the free list
    alloc()   - assign a free disk block
    free()    - return a disk block to the free list
    namei()   - resolve a pathname to an inode, component by component
    bmap()    - map a file byte offset to a physical block, walking the
                direct / single / double / triple indirect pointers

It also derives the classical inode reach limits, computes the metadata cost
of a 50 GB VM image, and measures buffer-cache hit ratio under an LRU cache
for a realistic CloudMatrix block trace.

Structure follows the System V / Bach model (10 direct, 1 single-indirect,
1 double-indirect, 1 triple-indirect), which is what the syllabus specifies.

Run:  python src/co4_storage/inode_fs.py
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

BLOCK_SIZE = 4096
POINTER_SIZE = 4
PTRS = BLOCK_SIZE // POINTER_SIZE       # 1024 pointers per indirect block
N_DIRECT = 10

KB, MB, GB, TB = 1024, 1024 ** 2, 1024 ** 3, 1024 ** 4


# ==========================================================================
# 1. Inode reach arithmetic
# ==========================================================================

def inode_reach() -> dict:
    direct = N_DIRECT
    single = PTRS
    double = PTRS ** 2
    triple = PTRS ** 3
    total = direct + single + double + triple
    return {
        "direct_blocks": direct, "direct_bytes": direct * BLOCK_SIZE,
        "single_blocks": single, "single_bytes": single * BLOCK_SIZE,
        "double_blocks": double, "double_bytes": double * BLOCK_SIZE,
        "triple_blocks": triple, "triple_bytes": triple * BLOCK_SIZE,
        "total_blocks": total, "max_file_bytes": total * BLOCK_SIZE,
    }


def bmap_cost(logical_block: int) -> tuple[str, int]:
    """Return (tier, disk reads) to fetch `logical_block` with a cold cache."""
    if logical_block < N_DIRECT:
        return "direct", 1
    logical_block -= N_DIRECT
    if logical_block < PTRS:
        return "single indirect", 2
    logical_block -= PTRS
    if logical_block < PTRS ** 2:
        return "double indirect", 3
    logical_block -= PTRS ** 2
    if logical_block < PTRS ** 3:
        return "triple indirect", 4
    return "beyond inode reach", -1


def metadata_blocks_for(file_bytes: int) -> dict:
    """How many indirect blocks does a file of this size actually consume?"""
    n = -(-file_bytes // BLOCK_SIZE)
    meta, remaining = 0, n
    remaining -= min(remaining, N_DIRECT)

    single = min(remaining, PTRS)
    if single > 0:
        meta += 1
        remaining -= single

    double = min(remaining, PTRS ** 2)
    if double > 0:
        inner = -(-double // PTRS)
        meta += 1 + inner
        remaining -= double

    triple = min(remaining, PTRS ** 3)
    if triple > 0:
        inner = -(-triple // PTRS)          # bottom-level indirect blocks
        middle = -(-inner // PTRS)          # second-level indirect blocks
        meta += 1 + middle + inner
        remaining -= triple

    return {"data_blocks": n, "meta_blocks": meta,
            "overhead_pct": meta / n * 100 if n else 0,
            "unmappable": remaining}


# ==========================================================================
# 2. A working miniature UNIX file system
# ==========================================================================

@dataclass
class Inode:
    ino: int
    ftype: str = "regular"            # regular | directory
    links: int = 0
    size: int = 0
    uid: int = 0
    mode: int = 0o644
    direct: list = field(default_factory=lambda: [None] * N_DIRECT)
    single: int | None = None
    double: int | None = None
    triple: int | None = None
    indirect_data: list = field(default_factory=list)  # data reached via indirection
    entries: dict = field(default_factory=dict)        # directories only
    free: bool = True


class MiniUnixFS:
    """Enough of a System V file system to trace the kernel algorithms."""

    def __init__(self, n_inodes: int = 64, n_blocks: int = 512, log=None):
        self.inodes = [Inode(i) for i in range(n_inodes)]
        self.block_free = [True] * n_blocks
        self.n_blocks = n_blocks
        # The super-block caches a small window of free inode numbers; when it
        # empties the kernel must rescan the inode list. This is the detail
        # that makes ialloc() interesting rather than trivial.
        self.free_inode_cache: list[int] = []
        self.remembered_inode = 0
        self.log = log if log is not None else []
        self.superblock_scans = 0

        root = self.inodes[1]
        root.free, root.ftype, root.links, root.mode = False, "directory", 2, 0o755
        root.entries = {".": 1, "..": 1}
        self.root_ino = 1

    # -- logging -------------------------------------------------------
    def _t(self, call: str, detail: str) -> None:
        self.log.append((call, detail))

    # -- block allocator ----------------------------------------------
    def alloc(self) -> int | None:
        """Kernel alloc(): remove a block from the free list."""
        for b, f in enumerate(self.block_free):
            if f:
                self.block_free[b] = False
                self._t("alloc()", f"free list -> block {b} removed, "
                                   f"{sum(self.block_free)} free remain")
                return b
        self._t("alloc()", "ENOSPC - free list empty")
        return None

    def free(self, b: int) -> None:
        """Kernel free(): return a block to the free list."""
        self.block_free[b] = True
        self._t("free()", f"block {b} returned to free list, "
                          f"{sum(self.block_free)} free")

    # -- inode allocator ----------------------------------------------
    def _refill_inode_cache(self, window: int = 4) -> None:
        self.superblock_scans += 1
        found = []
        for i in range(self.remembered_inode, len(self.inodes)):
            if self.inodes[i].free and i != 0:
                found.append(i)
                if len(found) == window:
                    break
        self.free_inode_cache = found
        self.remembered_inode = (found[-1] + 1) if found else 0
        self._t("ialloc()", f"super-block free-inode cache empty -> scan #"
                            f"{self.superblock_scans} refilled with {found}")

    def ialloc(self, ftype: str = "regular", uid: int = 0,
               mode: int = 0o644) -> Inode | None:
        """Kernel ialloc(): assign a free inode."""
        if not self.free_inode_cache:
            self._refill_inode_cache()
        if not self.free_inode_cache:
            self._t("ialloc()", "ENOSPC - no free inodes")
            return None
        ino = self.free_inode_cache.pop(0)
        ip = self.inodes[ino]
        ip.free, ip.ftype, ip.uid, ip.mode = False, ftype, uid, mode
        ip.links, ip.size = 0, 0
        ip.direct = [None] * N_DIRECT
        ip.single = ip.double = ip.triple = None
        ip.indirect_data = []
        ip.entries = {}
        self._t("ialloc()", f"inode {ino} taken from cache, type={ftype}, "
                            f"uid={uid}, mode={oct(mode)}; "
                            f"cache now {self.free_inode_cache}")
        return ip

    def ifree(self, ino: int) -> None:
        """Kernel ifree(): release an inode."""
        ip = self.inodes[ino]
        for b in [b for b in ip.direct if b is not None]:
            self.free(b)
        for b in ip.indirect_data:
            self.free(b)
        for b in (ip.single, ip.double, ip.triple):
            if b is not None:
                self.free(b)
        ip.free, ip.links, ip.size = True, 0, 0
        ip.direct = [None] * N_DIRECT
        ip.single = ip.double = ip.triple = None
        ip.indirect_data = []
        if len(self.free_inode_cache) < 4:
            self.free_inode_cache.append(ino)
            note = f"returned to super-block cache {self.free_inode_cache}"
        else:
            self.remembered_inode = min(self.remembered_inode, ino)
            note = (f"cache full; remembered_inode set to "
                    f"{self.remembered_inode} for the next scan")
        self._t("ifree()", f"inode {ino} released, {note}")

    # -- pathname resolution ------------------------------------------
    def namei(self, path: str) -> Inode | None:
        """Kernel namei(): convert a pathname to an inode."""
        parts = [p for p in path.strip("/").split("/") if p]
        cur = self.inodes[self.root_ino]
        self._t("namei()", f"resolving '{path}' - start at root inode "
                           f"{self.root_ino}")
        for part in parts:
            if cur.ftype != "directory":
                self._t("namei()", f"ENOTDIR at '{part}'")
                return None
            if part not in cur.entries:
                self._t("namei()", f"component '{part}' NOT FOUND in inode "
                                   f"{cur.ino} -> ENOENT")
                return None
            nxt = cur.entries[part]
            self._t("namei()", f"component '{part}' found in directory inode "
                               f"{cur.ino} -> inode {nxt}")
            cur = self.inodes[nxt]
        self._t("namei()", f"resolved '{path}' -> inode {cur.ino}")
        return cur

    # -- higher-level operations --------------------------------------
    def mkdir(self, parent: Inode, name: str, uid: int = 0) -> Inode:
        ip = self.ialloc("directory", uid, 0o755)
        ip.entries = {".": ip.ino, "..": parent.ino}
        ip.links = 2
        parent.entries[name] = ip.ino
        parent.links += 1
        self._t("mkdir", f"'{name}' -> inode {ip.ino} linked into inode "
                         f"{parent.ino}")
        return ip

    def create(self, parent: Inode, name: str, size_blocks: int,
               uid: int = 0, mode: int = 0o644) -> Inode | None:
        ip = self.ialloc("regular", uid, mode)
        if ip is None:
            return None
        for i in range(size_blocks):
            if i == N_DIRECT:
                # crossing the direct limit costs one extra METADATA block
                ip.single = self.alloc()
                self._t("create", f"logical block {i} exceeds the {N_DIRECT} "
                                  f"direct pointers -> block {ip.single} "
                                  f"allocated as the SINGLE INDIRECT block")
            if i == N_DIRECT + PTRS:
                ip.double = self.alloc()
                self._t("create", f"single indirect exhausted at logical block "
                                  f"{i} -> block {ip.double} allocated as the "
                                  f"DOUBLE INDIRECT block")
            b = self.alloc()
            if b is None:
                self._t("create", f"ENOSPC while growing '{name}'")
                break
            if i < N_DIRECT:
                ip.direct[i] = b
            else:
                ip.indirect_data.append(b)
        ip.links = 1
        ip.size = size_blocks * BLOCK_SIZE
        parent.entries[name] = ip.ino
        self._t("create", f"'{name}' -> inode {ip.ino}, {size_blocks} blocks, "
                          f"size {ip.size:,} B, linked into inode {parent.ino}")
        return ip

    def unlink(self, parent: Inode, name: str) -> None:
        ino = parent.entries.pop(name)
        ip = self.inodes[ino]
        ip.links -= 1
        self._t("unlink", f"'{name}' removed from directory inode "
                          f"{parent.ino}; inode {ino} link count -> {ip.links}")
        if ip.links == 0:
            self._t("unlink", f"link count reached 0 -> calling ifree({ino})")
            self.ifree(ino)


# ==========================================================================
# 3. Buffer cache
# ==========================================================================

class BufferCache:
    """LRU buffer cache with delayed write, as in the classical UNIX design."""

    def __init__(self, size: int):
        self.size = size
        self.buf: dict[int, bool] = {}      # block -> dirty flag
        self.hits = self.misses = 0
        self.writes_to_disk = 0

    def read(self, block: int) -> None:
        if block in self.buf:
            self.hits += 1
            self.buf[block] = self.buf.pop(block)      # refresh recency
        else:
            self.misses += 1
            self._admit(block, dirty=False)

    def write(self, block: int) -> None:
        if block in self.buf:
            self.hits += 1
            self.buf.pop(block)
            self.buf[block] = True                     # delayed write
        else:
            self.misses += 1
            self._admit(block, dirty=True)

    def _admit(self, block: int, dirty: bool) -> None:
        if len(self.buf) >= self.size:
            victim, was_dirty = next(iter(self.buf.items()))
            self.buf.pop(victim)
            if was_dirty:
                self.writes_to_disk += 1               # flush on eviction
        self.buf[block] = dirty

    def sync(self) -> int:
        n = sum(1 for d in self.buf.values() if d)
        self.writes_to_disk += n
        self.buf = {b: False for b in self.buf}
        return n

    @property
    def hit_ratio(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


def block_trace(n: int = 20000, seed: int = 4067) -> list[tuple[str, int]]:
    """A CloudMatrix-shaped block trace: hot metadata, warm log appends,
    cold streaming reads of VM images that blow past any cache."""
    rng = random.Random(seed)
    trace = []
    for _ in range(n):
        r = rng.random()
        if r < 0.40:                       # superblock / inode / bitmap: tiny hot set
            trace.append(("r", rng.randint(0, 31)))
        elif r < 0.62:                     # directory blocks: small warm set
            trace.append(("r", rng.randint(32, 159)))
        elif r < 0.80:                     # log appends: sequential writes
            trace.append(("w", rng.randint(160, 400)))
        else:                              # VM image streaming: huge cold set
            trace.append(("r", rng.randint(1000, 60000)))
    return trace


# ==========================================================================

def main():
    # ---------------- inode reach ----------------
    r = inode_reach()
    print("=" * 78)
    print(" CO4.2  UNIX INODE STRUCTURE AND ADDRESSING REACH")
    print("=" * 78)
    print(f"   Block size {BLOCK_SIZE} B, pointer {POINTER_SIZE} B "
          f"-> {PTRS} pointers per indirect block")
    print()
    print(f"   {'Pointer tier':<22}{'Blocks reachable':>20}{'Bytes':>18}"
          f"{'Reads to fetch':>16}")
    rows = [
        (f"{N_DIRECT} direct", r["direct_blocks"], r["direct_bytes"], 1),
        ("1 single indirect", r["single_blocks"], r["single_bytes"], 2),
        ("1 double indirect", r["double_blocks"], r["double_bytes"], 3),
        ("1 triple indirect", r["triple_blocks"], r["triple_bytes"], 4),
    ]
    for label, blocks, byts, reads in rows:
        if byts >= TB:
            human = f"{byts / TB:.3f} TB"
        elif byts >= GB:
            human = f"{byts / GB:.3f} GB"
        elif byts >= MB:
            human = f"{byts / MB:.3f} MB"
        else:
            human = f"{byts / KB:.0f} KB"
        print(f"   {label:<22}{blocks:>20,}{human:>18}{reads:>16}")
    print(f"   {'MAXIMUM FILE SIZE':<22}{r['total_blocks']:>20,}"
          f"{r['max_file_bytes'] / TB:>15.3f} TB")
    print()
    print("   The asymmetry is the whole point of the design: 99.99% of files in")
    print("   a real system fit inside the 10 direct pointers and cost exactly")
    print("   one disk read, while the rare huge file is still addressable, at a")
    print("   worst case of 4 reads per block.")

    # ---------------- bmap examples ----------------
    print()
    print("=" * 78)
    print(" CO4.2  bmap() - which pointer tier serves a given logical block?")
    print("=" * 78)
    print(f"   {'Logical block':>15}{'File offset':>18}{'Tier':>22}{'Disk reads':>13}")
    for lb in (0, 9, 10, 1033, 1034, 1_049_610, 1_049_700, 13_107_199):
        tier, reads = bmap_cost(lb)
        off = lb * BLOCK_SIZE
        human = (f"{off / GB:.2f} GB" if off >= GB else
                 f"{off / MB:.2f} MB" if off >= MB else f"{off / KB:.0f} KB")
        print(f"   {lb:>15,}{human:>18}{tier:>22}{reads:>13}")

    # ---------------- 50 GB VM image ----------------
    print()
    print("=" * 78)
    print(" CO4.2  METADATA COST OF A 50 GB VM DISK IMAGE (guest-win11.vmdk)")
    print("=" * 78)
    for label, size in (("named.conf (2 KB)", 2_100),
                        ("nginx-access.log (80 MB)", 80 * MB),
                        ("guest-ubuntu.img (8 GB)", 8 * GB),
                        ("guest-win11.vmdk (50 GB)", 50 * GB)):
        m = metadata_blocks_for(size)
        print(f"   {label:<28}data {m['data_blocks']:>12,} blocks   "
              f"indirect {m['meta_blocks']:>8,} blocks   "
              f"overhead {m['overhead_pct']:>6.3f}%")
    print()
    print("   A 50 GB image needs 12,814 indirect blocks -- 50 MB of pure pointer")
    print("   metadata that must itself be cached, and up to 4 disk reads to")
    print("   reach one data block on a cold cache. This is precisely why ext4")
    print("   replaced the indirect chain with extents for large files: a single")
    print("   12-byte extent descriptor covers up to 128 MB contiguously.")

    # ---------------- system-call trace ----------------
    print()
    print("=" * 78)
    print(" CO4.2  KERNEL SYSTEM-CALL TRACE - guest VM create / delete cycle")
    print("=" * 78)
    fs = MiniUnixFS()
    root = fs.inodes[fs.root_ino]

    print()
    print("   PHASE 1 - build /var/lib/cloudmatrix and create the guest image")
    print("   " + "-" * 68)
    var = fs.mkdir(root, "var")
    lib = fs.mkdir(var, "lib")
    cm = fs.mkdir(lib, "cloudmatrix", uid=1001)
    fs.create(cm, "guest-tenant7.img", 14, uid=1001, mode=0o600)
    fs.create(cm, "guest-tenant7.cfg", 1, uid=1001, mode=0o644)
    for call, detail in fs.log:
        print(f"     {call:<12} {detail}")

    print()
    print("   PHASE 2 - namei() resolution of the guest image path")
    print("   " + "-" * 68)
    fs.log.clear()
    ip = fs.namei("/var/lib/cloudmatrix/guest-tenant7.img")
    for call, detail in fs.log:
        print(f"     {call:<12} {detail}")
    print(f"     RESULT       inode {ip.ino}, size {ip.size:,} B, "
          f"uid {ip.uid}, mode {oct(ip.mode)}, links {ip.links}")
    print(f"     direct[]   = {ip.direct}")
    print(f"     single     = {ip.single}   (block 11 onwards needs it)")
    print(f"     namei() cost: 4 directory reads + 1 inode read = 5 I/Os cold,")
    print(f"     1 I/O warm -- which is exactly what the dentry/inode cache is for.")

    print()
    print("   PHASE 3 - tenant offboarding: unlink the guest, watch ifree/free")
    print("   " + "-" * 68)
    fs.log.clear()
    before = sum(fs.block_free)
    fs.unlink(cm, "guest-tenant7.img")
    for call, detail in fs.log:
        print(f"     {call:<12} {detail}")
    print(f"     Free blocks {before} -> {sum(fs.block_free)} "
          f"({sum(fs.block_free) - before} reclaimed)")

    print()
    print("   PHASE 4 - a failed lookup, proving namei() reports ENOENT safely")
    print("   " + "-" * 68)
    fs.log.clear()
    missing = fs.namei("/var/lib/cloudmatrix/guest-tenant7.img")
    for call, detail in fs.log:
        print(f"     {call:<12} {detail}")
    print(f"     RESULT       {missing} - the block map is gone and the inode")
    print("                  is back on the free list; no stale pointer survives.")

    # ---------------- buffer cache ----------------
    print()
    print("=" * 78)
    print(" CO4.2  BUFFER CACHE HIT RATIO (LRU, delayed write)")
    print("=" * 78)
    trace = block_trace()
    reads = sum(1 for op, _ in trace if op == "r")
    print(f"   Trace: {len(trace):,} operations "
          f"({reads:,} reads / {len(trace) - reads:,} writes)")
    print(f"   Working sets: metadata 32 blocks, directories 128 blocks,")
    print(f"                 log 241 blocks, VM streaming 59,000 blocks")
    print()
    print(f"   {'Cache size':>12}{'Cache MB':>11}{'Hits':>10}{'Misses':>10}"
          f"{'Hit ratio':>12}{'Disk writes':>14}")
    for size in (16, 32, 64, 128, 256, 512, 1024, 2048):
        c = BufferCache(size)
        for op, blk in trace:
            (c.read if op == "r" else c.write)(blk)
        c.sync()
        print(f"   {size:>12}{size * BLOCK_SIZE / MB:>11.2f}{c.hits:>10,}"
              f"{c.misses:>10,}{c.hit_ratio:>11.2%}{c.writes_to_disk:>14,}")
    print()
    print("   Reading of the curve: 80% of operations touch a hot set of only")
    print("   401 blocks (metadata + directories + the log tail), and 20% stream")
    print("   the 59,000-block VM image region, which no realistic cache can hold.")
    print("   The achievable ceiling is therefore about 80%, and 1,024 buffers")
    print("   (4 MB) already reach 76.9% -- 96% of everything available. Doubling")
    print("   the cache again buys 1.4 more percentage points for another 4 MB.")
    print("   The right fix is not a bigger cache but O_DIRECT on VM image I/O,")
    print("   so streaming traffic stops evicting the metadata that caches well.")
    print()
    print("   Note the write column: delayed write means a block modified many")
    print("   times reaches the platter once, but any block still dirty at a")
    print("   crash is lost. That is the reliability/performance trade-off that")
    print("   fsync() and the journal exist to arbitrate.")


if __name__ == "__main__":
    main()
