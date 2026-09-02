#!/usr/bin/env python3
"""
CloudMatrix - validation test suite
===================================

Every number quoted in the report is checked here against an independent
source: a hand-computed value, a textbook invariant, or a property that must
hold for any correct implementation. A simulator that produces confident
nonsense is worse than no simulator, so the results are only defensible if
the code that produced them is tested.

Run:  python -m unittest discover -s tests -v
  or: python tests/test_simulators.py
"""

from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from co3_memory.page_table import MemoryGeometry, TwoLevelMMU, KB, MB, GB
from co3_memory import page_replacement as pr
from co3_memory import dynamic_allocation as da
from co3_memory import working_set as ws
from co4_storage import disk_scheduling as ds
from co4_storage import file_allocation as fa
from co4_storage import inode_fs as ifs


# ==========================================================================
class TestMemoryGeometry(unittest.TestCase):
    """CO3.1 - the page-table arithmetic must match the hand calculation."""

    def setUp(self):
        self.geo = MemoryGeometry()

    def test_physical_frames(self):
        # 32 GB / 4 KB = 2^35 / 2^12 = 2^23
        self.assertEqual(self.geo.frames, 8_388_608)
        self.assertEqual(self.geo.frames, 2 ** 23)

    def test_virtual_pages(self):
        # 128 MB / 4 KB = 2^27 / 2^12 = 2^15
        self.assertEqual(self.geo.pages, 32_768)
        self.assertEqual(self.geo.pages, 2 ** 15)

    def test_address_widths(self):
        self.assertEqual(self.geo.virtual_bits, 27)
        self.assertEqual(self.geo.physical_bits, 35)
        self.assertEqual(self.geo.offset_bits, 12)
        self.assertEqual(self.geo.frame_bits, 23)

    def test_two_level_split_sums_to_page_number(self):
        self.assertEqual(self.geo.outer_bits + self.geo.inner_bits,
                         self.geo.page_number_bits)
        self.assertEqual((self.geo.outer_bits, self.geo.inner_bits), (5, 10))

    def test_inner_table_occupies_exactly_one_frame(self):
        self.assertEqual(self.geo.entries_per_page * self.geo.pte_size,
                         self.geo.page_size)

    def test_sparse_table_is_cheaper_than_flat(self):
        sparse = self.geo.outer_table_bytes + self.geo.page_size
        self.assertLess(sparse, self.geo.flat_table_bytes)
        self.assertEqual(self.geo.flat_table_bytes // sparse, 31)


class TestTranslation(unittest.TestCase):
    """CO3.1 - translation must be a correct, invertible mapping."""

    def setUp(self):
        self.mmu = TwoLevelMMU(MemoryGeometry())

    def test_split_reassembles(self):
        for va in (0x0, 0x1, 0xFFF, 0x1000, 0x0400ABC, 0x7FFFFFF):
            p1, p2, d = self.mmu.split(va)
            page = (p1 << 10) | p2
            self.assertEqual((page << 12) | d, va)

    def test_offset_is_preserved_by_translation(self):
        for va in (0x0000ABC, 0x0401FFF, 0x07FF001):
            pa = self.mmu.translate(va)
            self.assertEqual(pa & 0xFFF, va & 0xFFF,
                             "the page offset must pass through untouched")

    def test_same_page_maps_to_same_frame(self):
        a = self.mmu.translate(0x0400000)
        b = self.mmu.translate(0x0400FFF)
        self.assertEqual(a >> 12, b >> 12)

    def test_distinct_pages_get_distinct_frames(self):
        frames = {self.mmu.translate(p << 12) >> 12 for p in range(64)}
        self.assertEqual(len(frames), 64)

    def test_tlb_never_exceeds_capacity(self):
        for p in range(500):
            self.mmu.translate(p << 12)
        self.assertLessEqual(len(self.mmu.tlb), self.mmu.tlb_entries)

    def test_eat_between_hit_and_miss_cost(self):
        for p in (0, 1, 2, 0, 1):
            self.mmu.translate(p << 12)
        eat = self.mmu.effective_access_time()
        self.assertGreater(eat, 101.0)     # better than an all-miss walk
        self.assertLess(eat, 301.0)


# ==========================================================================
class TestPageReplacement(unittest.TestCase):
    """CO3.3 - replacement counts and the anomaly."""

    def test_hand_computed_fault_counts(self):
        """These six numbers are the ones the report tabulates."""
        expected = {("FIFO", 3): 11, ("FIFO", 4): 12,
                    ("LRU", 3): 12, ("LRU", 4): 10,
                    ("OPTIMAL", 3): 9, ("OPTIMAL", 4): 8}
        for (name, frames), want in expected.items():
            got = pr.ALGORITHMS[name](pr.REFERENCE_STRING, frames).faults
            self.assertEqual(got, want, f"{name} with {frames} frames")

    def test_belady_anomaly_is_present_for_fifo(self):
        f3 = pr.fifo(pr.REFERENCE_STRING, 3).faults
        f4 = pr.fifo(pr.REFERENCE_STRING, 4).faults
        self.assertGreater(f4, f3, "the trace is chosen to exhibit the anomaly")

    def test_stack_algorithms_never_regress(self):
        """LRU and OPT satisfy the inclusion property, so more frames can
        never mean more faults. This is the property FIFO lacks."""
        for algo in (pr.lru, pr.optimal):
            for m in range(1, 7):
                a = algo(pr.REFERENCE_STRING, m).faults
                b = algo(pr.REFERENCE_STRING, m + 1).faults
                self.assertLessEqual(b, a, f"{algo.__name__} regressed at m={m}")

    def test_optimal_is_a_lower_bound(self):
        """No online algorithm can beat OPT. If one does, OPT is wrong."""
        for frames in (2, 3, 4, 5, 6):
            opt = pr.optimal(pr.REFERENCE_STRING, frames).faults
            for algo in (pr.fifo, pr.lru):
                self.assertGreaterEqual(algo(pr.REFERENCE_STRING, frames).faults,
                                        opt)

    def test_faults_never_below_distinct_pages(self):
        """Compulsory faults: every distinct page must be brought in once."""
        distinct = len(set(pr.REFERENCE_STRING))
        for frames in (3, 4, 8, 20):
            for algo in pr.ALGORITHMS.values():
                self.assertGreaterEqual(
                    algo(pr.REFERENCE_STRING, frames).faults, distinct)

    def test_hits_and_faults_sum_to_trace_length(self):
        for frames in (3, 4):
            for algo in pr.ALGORITHMS.values():
                r = algo(pr.REFERENCE_STRING, frames)
                self.assertEqual(r.faults + r.hits, len(pr.REFERENCE_STRING))

    def test_enough_frames_means_only_compulsory_faults(self):
        distinct = len(set(pr.REFERENCE_STRING))
        for algo in pr.ALGORITHMS.values():
            self.assertEqual(algo(pr.REFERENCE_STRING, distinct).faults, distinct)


# ==========================================================================
class TestDynamicAllocation(unittest.TestCase):
    """CO3.2 - placement policies must conserve memory."""

    def test_memory_is_conserved(self):
        for strategy in ("first", "best", "worst"):
            placements, holes, stats = da.place(strategy, da.HOLES_MB, da.REQUESTS)
            allocated = sum(s for _, s, i, _ in placements if i is not None)
            self.assertEqual(allocated + sum(holes), sum(da.HOLES_MB))

    def test_no_hole_goes_negative(self):
        for strategy in ("first", "best", "worst"):
            _, holes, _ = da.place(strategy, da.HOLES_MB, da.REQUESTS)
            self.assertTrue(all(h >= 0 for h in holes))

    def test_placement_always_fits_the_chosen_hole(self):
        for strategy in ("first", "best", "worst"):
            placements, _, _ = da.place(strategy, da.HOLES_MB, da.REQUESTS)
            for _, size, idx, leftover in placements:
                if idx is not None:
                    self.assertGreaterEqual(leftover, 0)

    def test_best_fit_picks_the_tightest_hole(self):
        holes = [100, 500, 250, 900]
        placements, _, _ = da.place("best", holes, [("x", 200)])
        self.assertEqual(placements[0][2], 2)      # the 250 MB hole

    def test_worst_fit_picks_the_largest_hole(self):
        holes = [100, 500, 250, 900]
        placements, _, _ = da.place("worst", holes, [("x", 200)])
        self.assertEqual(placements[0][2], 3)      # the 900 MB hole

    def test_first_fit_picks_the_lowest_address(self):
        holes = [100, 500, 250, 900]
        placements, _, _ = da.place("first", holes, [("x", 200)])
        self.assertEqual(placements[0][2], 1)      # the first that fits

    def test_worst_fit_rejects_the_large_request(self):
        """The reported finding: Worst-Fit is the only policy that fails."""
        _, _, s = da.place("worst", da.HOLES_MB, da.REQUESTS)
        self.assertEqual(s["failures"], 1)
        for strategy in ("first", "best"):
            _, _, s2 = da.place(strategy, da.HOLES_MB, da.REQUESTS)
            self.assertEqual(s2["failures"], 0)


# ==========================================================================
class TestDiskScheduling(unittest.TestCase):
    """CO4.3 - head movement, verified against the hand calculation."""

    HAND_COMPUTED = {"FCFS": 2197, "SSTF": 813, "SCAN": 851,
                     "C-SCAN": 964, "LOOK": 813, "C-LOOK": 882}

    def test_totals_match_hand_calculation(self):
        for name, fn in ds.ALGORITHMS:
            path = fn(ds.QUEUE, ds.HEAD)
            self.assertEqual(ds.total_movement(path), self.HAND_COMPUTED[name],
                             f"{name} head movement")

    def test_every_request_is_served_exactly_once(self):
        for name, fn in ds.ALGORITHMS:
            path = fn(ds.QUEUE, ds.HEAD)
            served = [c for c in path[1:] if c in ds.QUEUE]
            self.assertEqual(sorted(served), sorted(ds.QUEUE),
                             f"{name} did not serve every request exactly once")

    def test_path_starts_at_the_head(self):
        for name, fn in ds.ALGORITHMS:
            self.assertEqual(fn(ds.QUEUE, ds.HEAD)[0], ds.HEAD)

    def test_path_stays_within_the_platter(self):
        for name, fn in ds.ALGORITHMS:
            for c in fn(ds.QUEUE, ds.HEAD):
                self.assertGreaterEqual(c, ds.DISK_MIN)
                self.assertLessEqual(c, ds.DISK_MAX)

    def test_fcfs_preserves_arrival_order(self):
        path = ds.fcfs(ds.QUEUE, ds.HEAD)
        self.assertEqual(path[1:], ds.QUEUE)

    def test_sstf_is_a_lower_bound_among_greedy_choices(self):
        """SSTF must never move further than FCFS on this queue."""
        self.assertLess(ds.total_movement(ds.sstf(ds.QUEUE, ds.HEAD)),
                        ds.total_movement(ds.fcfs(ds.QUEUE, ds.HEAD)))

    def test_look_never_exceeds_scan(self):
        """LOOK is SCAN without the trip to the platter edge, so it can never
        travel further."""
        self.assertLessEqual(ds.total_movement(ds.look(ds.QUEUE, ds.HEAD)),
                             ds.total_movement(ds.scan(ds.QUEUE, ds.HEAD)))
        self.assertLessEqual(ds.total_movement(ds.clook(ds.QUEUE, ds.HEAD)),
                             ds.total_movement(ds.cscan(ds.QUEUE, ds.HEAD)))

    def test_scan_reaches_the_platter_edge(self):
        self.assertIn(ds.DISK_MAX, ds.scan(ds.QUEUE, ds.HEAD))

    def test_average_seek_is_total_over_count(self):
        for name, fn in ds.ALGORITHMS:
            r = ds.analyse(name, fn)
            self.assertAlmostEqual(r["avg"], r["total"] / len(ds.QUEUE))

    def test_empty_and_single_request_queues(self):
        """Edge cases the report does not show but the code must survive."""
        for name, fn in ds.ALGORITHMS:
            self.assertEqual(ds.total_movement(fn([], 100)), 0)
            self.assertEqual(ds.total_movement(fn([150], 100)), 50)


# ==========================================================================
class TestFileAllocation(unittest.TestCase):
    """CO4.1 - allocation must never corrupt, overlap or lose blocks."""

    def test_no_two_files_share_a_block(self):
        for name, allocator in fa.METHODS:
            disk, table = fa.run_allocation_round(name, allocator)
            seen = set()
            for r in table.values():
                for b in r["data"] + r["meta"]:
                    self.assertNotIn(b, seen,
                                     f"{name}: block {b} allocated twice")
                    seen.add(b)

    def test_allocated_blocks_are_marked_used(self):
        for name, allocator in fa.METHODS:
            disk, table = fa.run_allocation_round(name, allocator)
            for r in table.values():
                for b in r["data"] + r["meta"]:
                    self.assertFalse(disk.free[b],
                                     f"{name}: block {b} still marked free")

    def test_block_accounting_balances(self):
        for name, allocator in fa.METHODS:
            disk, table = fa.run_allocation_round(name, allocator)
            used = sum(len(r["data"]) + len(r["meta"]) for r in table.values())
            self.assertEqual(used + disk.free_count(), fa.TOTAL_BLOCKS)

    def test_contiguous_blocks_really_are_contiguous(self):
        disk, table = fa.run_allocation_round("Contiguous", fa.alloc_contiguous)
        for r in table.values():
            if r["ok"] and len(r["data"]) > 1:
                self.assertEqual(r["data"],
                                 list(range(r["data"][0],
                                            r["data"][0] + len(r["data"]))))

    def test_indexed_allocation_reserves_an_index_block(self):
        disk, table = fa.run_allocation_round("Indexed", fa.alloc_indexed)
        for r in table.values():
            if r["ok"]:
                self.assertGreaterEqual(len(r["meta"]), 1)
                self.assertNotIn(r["meta"][0], r["data"])

    def test_allocation_is_refused_when_it_cannot_be_honoured(self):
        """Section D reliability requirement: the system must correctly report
        failure rather than silently over-allocating."""
        disk = fa.Disk()
        r = fa.alloc_contiguous(disk, "huge", fa.TOTAL_BLOCKS + 1)
        self.assertFalse(r["ok"])
        self.assertEqual(disk.free_count(), fa.TOTAL_BLOCKS,
                         "a failed allocation must not consume any block")

    def test_external_fragmentation_defeats_contiguous_only(self):
        """The headline result: after deletions, contiguous fails while the
        non-contiguous methods succeed with the same free space."""
        outcomes = {}
        for name, allocator in fa.METHODS:
            disk, table = fa.run_allocation_round(name, allocator)
            for f in ("syslog-2026-09.log", "tenant-db.dump", "guest-ubuntu.img"):
                disk.release(table[f]["data"] + table[f]["meta"])
            free_before = disk.free_count()
            outcomes[name] = (allocator(disk, "rebuild.vmdk", 150)["ok"],
                              free_before)
        self.assertFalse(outcomes["Contiguous"][0])
        self.assertTrue(outcomes["Linked"][0])
        self.assertTrue(outcomes["Indexed"][0])
        self.assertGreater(outcomes["Contiguous"][1], 150,
                           "the failure must be fragmentation, not capacity")

    def test_deallocation_returns_every_block(self):
        disk = fa.Disk()
        r = fa.alloc_indexed(disk, "f", 40)
        self.assertEqual(disk.free_count(), fa.TOTAL_BLOCKS - 41)
        disk.release(r["data"] + r["meta"])
        self.assertEqual(disk.free_count(), fa.TOTAL_BLOCKS)

    def test_linked_random_access_is_quadratic(self):
        """The reported 45x penalty is a property of chain traversal."""
        seq, rnd = fa.access_costs("Linked", 95)
        self.assertEqual(seq, 95)
        self.assertEqual(rnd, 1035)
        self.assertGreater(rnd, fa.access_costs("Indexed", 95)[1] * 40)

    def test_direct_access_methods_cost_one_io_per_block(self):
        for method in ("Contiguous", "Extent (ext4-style)"):
            seq, rnd = fa.access_costs(method, 95)
            self.assertEqual(seq, 95)
            self.assertEqual(rnd, 23)


# ==========================================================================
class TestInodeFS(unittest.TestCase):
    """CO4.2 - inode reach, bmap tiers and the kernel call sequence."""

    def test_maximum_file_size(self):
        r = ifs.inode_reach()
        self.assertEqual(r["single_bytes"], 4 * ifs.MB)
        self.assertEqual(r["double_bytes"], 4 * ifs.GB)
        self.assertEqual(r["triple_bytes"], 4 * ifs.TB)
        self.assertEqual(r["total_blocks"], 1_074_791_434)

    def test_bmap_tier_boundaries(self):
        self.assertEqual(ifs.bmap_cost(0), ("direct", 1))
        self.assertEqual(ifs.bmap_cost(9), ("direct", 1))
        self.assertEqual(ifs.bmap_cost(10), ("single indirect", 2))
        self.assertEqual(ifs.bmap_cost(1033), ("single indirect", 2))
        self.assertEqual(ifs.bmap_cost(1034), ("double indirect", 3))
        self.assertEqual(ifs.bmap_cost(10 + 1024 + 1024 ** 2),
                         ("triple indirect", 4))

    def test_50gb_metadata_cost(self):
        m = ifs.metadata_blocks_for(50 * ifs.GB)
        self.assertEqual(m["data_blocks"], 13_107_200)
        self.assertEqual(m["meta_blocks"], 12_814)
        self.assertEqual(m["unmappable"], 0)

    def test_small_file_needs_no_indirect_block(self):
        self.assertEqual(ifs.metadata_blocks_for(2_100)["meta_blocks"], 0)
        self.assertEqual(ifs.metadata_blocks_for(40 * ifs.KB)["meta_blocks"], 0)
        self.assertEqual(ifs.metadata_blocks_for(41 * ifs.KB)["meta_blocks"], 1)

    def test_namei_resolves_and_reports_enoent(self):
        fs = ifs.MiniUnixFS()
        root = fs.inodes[fs.root_ino]
        var = fs.mkdir(root, "var")
        lib = fs.mkdir(var, "lib")
        fs.create(lib, "guest.img", 3)
        self.assertIsNotNone(fs.namei("/var/lib/guest.img"))
        self.assertIsNone(fs.namei("/var/lib/absent.img"))
        self.assertIsNone(fs.namei("/nosuchdir/guest.img"))

    def test_unlink_reclaims_every_block(self):
        fs = ifs.MiniUnixFS()
        root = fs.inodes[fs.root_ino]
        before = sum(fs.block_free)
        fs.create(root, "big.img", 14)
        self.assertLess(sum(fs.block_free), before)
        fs.unlink(root, "big.img")
        self.assertEqual(sum(fs.block_free), before,
                         "ifree() must return every data and indirect block")

    def test_ifree_returns_the_inode_to_the_free_pool(self):
        fs = ifs.MiniUnixFS()
        root = fs.inodes[fs.root_ino]
        ip = fs.create(root, "f", 2)
        ino = ip.ino
        self.assertFalse(fs.inodes[ino].free)
        fs.unlink(root, "f")
        self.assertTrue(fs.inodes[ino].free)

    def test_ialloc_never_hands_out_the_same_inode_twice(self):
        fs = ifs.MiniUnixFS()
        root = fs.inodes[fs.root_ino]
        seen = set()
        for i in range(30):
            ip = fs.create(root, f"f{i}", 1)
            self.assertNotIn(ip.ino, seen)
            seen.add(ip.ino)

    def test_alloc_never_hands_out_the_same_block_twice(self):
        fs = ifs.MiniUnixFS()
        blocks = [fs.alloc() for _ in range(60)]
        self.assertEqual(len(set(blocks)), 60)

    def test_buffer_cache_hit_ratio_is_monotonic_in_size(self):
        trace = ifs.block_trace(n=4000)
        prev = -1.0
        for size in (16, 32, 64, 128, 256, 512):
            c = ifs.BufferCache(size)
            for op, blk in trace:
                (c.read if op == "r" else c.write)(blk)
            self.assertGreaterEqual(c.hit_ratio, prev,
                                    "LRU is a stack algorithm; a bigger cache "
                                    "cannot have a lower hit ratio")
            prev = c.hit_ratio

    def test_buffer_cache_never_exceeds_capacity(self):
        c = ifs.BufferCache(32)
        for op, blk in ifs.block_trace(n=3000):
            (c.read if op == "r" else c.write)(blk)
            self.assertLessEqual(len(c.buf), 32)

    def test_sync_flushes_every_dirty_buffer(self):
        c = ifs.BufferCache(64)
        for b in range(20):
            c.write(b)
        self.assertEqual(c.sync(), 20)
        self.assertTrue(all(d is False for d in c.buf.values()))


# ==========================================================================
class TestWorkingSet(unittest.TestCase):
    """CO3.4 - working-set and thrashing model invariants."""

    @classmethod
    def setUpClass(cls):
        cls.trace = ws.locality_trace(length=8000)

    def test_working_set_size_grows_with_the_window(self):
        prev = 0
        for delta in (10, 25, 50, 100, 250):
            sizes = ws.working_set_sizes(self.trace, delta)
            mean = sum(sizes) / len(sizes)
            self.assertGreaterEqual(mean, prev)
            prev = mean

    def test_working_set_never_exceeds_the_window(self):
        for delta in (10, 50, 200):
            self.assertLessEqual(max(ws.working_set_sizes(self.trace, delta)),
                                 delta)

    def test_fault_rate_falls_as_frames_are_added(self):
        prev = 1.0
        for f in (2, 4, 8, 16, 32):
            p = ws.lru_fault_rate(self.trace, f)
            self.assertLessEqual(p, prev)
            prev = p

    def test_fault_rate_is_a_probability(self):
        for f in (1, 4, 16, 64):
            p = ws.lru_fault_rate(self.trace, f)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_utilisation_is_bounded(self):
        for n in (1, 4, 8, 16, 32):
            _, ucpu, udisk = ws.utilisation(n, ws.lru_fault_rate(self.trace, 64 // n or 1))
            self.assertGreaterEqual(ucpu, 0.0)
            self.assertLessEqual(ucpu, 1.0)
            self.assertLessEqual(udisk, 1.0)

    def test_thrashing_occurs_past_the_knee(self):
        """Utilisation at N=16 must be materially worse than at the knee."""
        u_knee = ws.utilisation(8, ws.lru_fault_rate(self.trace, 8))[1]
        u_over = ws.utilisation(16, ws.lru_fault_rate(self.trace, 4))[1]
        self.assertGreater(u_knee, u_over * 2)


# ==========================================================================
class TestReportedFiguresAreReproducible(unittest.TestCase):
    """Every module must run end to end without raising, because the report
    quotes their console output verbatim."""

    def test_all_modules_execute(self):
        from co3_memory import page_table
        from co4_storage import disk_dynamic_experiment as dyn
        for module in (page_table.demo, pr.run, da.report, ws.main,
                       ds.main, fa.main, ifs.main, dyn.main):
            with redirect_stdout(io.StringIO()) as buf:
                module()
            self.assertGreater(len(buf.getvalue()), 500,
                               f"{module.__module__} produced almost no output")


if __name__ == "__main__":
    unittest.main(verbosity=2)
