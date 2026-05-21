"""Comprehensive tests for the EpsilonAccumulator module."""

import threading
import time

import pytest

from luciddreamer.epsilon_accumulator import (
    AccumulationRecord,
    AccumulationResult,
    EpsilonAccumulator,
)
from luciddreamer.tiles import CommandTile, Tile, TileType


# ── helpers ──────────────────────────────────────────────────────────────


def _tile(**overrides):
    """Create a Tile for test data with sensible defaults."""
    defaults = dict(
        tile_type=TileType.COMMAND,
        input_pattern="test-pattern",
        output_action="test-action",
    )
    defaults.update(overrides)
    return Tile(**defaults)


# ── 1. Construction ─────────────────────────────────────────────────────


class TestConstruction:
    def test_default_params(self):
        acc = EpsilonAccumulator()
        assert acc.snap_threshold == 0.975
        assert acc.decay == 0.995
        assert acc.tile_count == 0
        assert acc.snapped_count == 0

    def test_custom_params(self):
        acc = EpsilonAccumulator(snap_threshold=0.8, decay=0.9)
        assert acc.snap_threshold == 0.8
        assert acc.decay == 0.9

    def test_threshold_at_one(self):
        acc = EpsilonAccumulator(snap_threshold=1.0)
        assert acc.snap_threshold == 1.0

    def test_rejects_threshold_zero(self):
        with pytest.raises(ValueError, match="snap_threshold"):
            EpsilonAccumulator(snap_threshold=0.0)

    def test_rejects_threshold_negative(self):
        with pytest.raises(ValueError, match="snap_threshold"):
            EpsilonAccumulator(snap_threshold=-0.5)

    def test_rejects_threshold_above_one(self):
        with pytest.raises(ValueError, match="snap_threshold"):
            EpsilonAccumulator(snap_threshold=1.1)

    def test_rejects_decay_zero(self):
        with pytest.raises(ValueError, match="decay"):
            EpsilonAccumulator(decay=0.0)

    def test_rejects_decay_negative(self):
        with pytest.raises(ValueError, match="decay"):
            EpsilonAccumulator(decay=-0.1)

    def test_rejects_decay_above_one(self):
        with pytest.raises(ValueError, match="decay"):
            EpsilonAccumulator(decay=1.5)

    def test_repr(self):
        acc = EpsilonAccumulator(snap_threshold=0.9, decay=0.99)
        r = repr(acc)
        assert "EpsilonAccumulator" in r
        assert "tiles=0" in r


# ── 2. Accumulate — small deltas compound ───────────────────────────────


class TestAccumulation:
    def test_first_delta(self):
        acc = EpsilonAccumulator(decay=1.0)
        result = acc.accumulate("tile-1", 0.1)
        assert result.previous_confidence == 0.0
        assert abs(result.new_confidence - 0.1) < 1e-9
        assert result.delta_applied == 0.1

    def test_compound_deltas(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.2)
        r = acc.accumulate("t", 0.3)
        assert abs(r.new_confidence - 0.5) < 1e-9

    def test_independent_tiles(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("a", 0.4)
        acc.accumulate("b", 0.7)
        assert abs(acc.get_confidence("a") - 0.4) < 1e-9
        assert abs(acc.get_confidence("b") - 0.7) < 1e-9

    def test_capped_at_one(self):
        acc = EpsilonAccumulator(decay=1.0)
        r = acc.accumulate("t", 5.0)
        assert r.new_confidence == 1.0

    def test_unknown_tile_returns_zero(self):
        acc = EpsilonAccumulator()
        assert acc.get_confidence("nonexistent") == 0.0

    def test_with_real_tile_id(self):
        tile = _tile()
        acc = EpsilonAccumulator(decay=1.0)
        r = acc.accumulate(tile.tile_id, 0.5)
        assert abs(r.new_confidence - 0.5) < 1e-9

    def test_with_command_tile_id(self):
        cmd = CommandTile(input_pattern="helm port 10", output_action="helm_port_10")
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate(cmd.tile_id, 0.6)
        assert abs(acc.get_confidence(cmd.tile_id) - 0.6) < 1e-9


# ── 3. Snap detection ───────────────────────────────────────────────────


class TestSnapDetection:
    def test_snap_exactly_at_threshold(self):
        acc = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
        acc.accumulate("t", 0.3)
        assert not acc.accumulate("t", 0.1).snapped  # 0.4 < 0.5
        r = acc.accumulate("t", 0.2)  # 0.6 >= 0.5
        assert r.snapped

    def test_snap_crossing_threshold(self):
        acc = EpsilonAccumulator(snap_threshold=0.975, decay=1.0)
        acc.accumulate("t", 0.9)
        r = acc.accumulate("t", 0.1)  # 1.0, but capped → 1.0 >= 0.975
        assert r.snapped
        assert r.new_confidence >= 0.975

    def test_snap_not_triggered_below_threshold(self):
        acc = EpsilonAccumulator(snap_threshold=0.975, decay=1.0)
        r = acc.accumulate("t", 0.97)
        assert not r.snapped
        r2 = acc.accumulate("t", 0.004)  # 0.974 < 0.975
        assert not r2.snapped

    def test_snap_increments_snapped_count(self):
        acc = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
        acc.accumulate("a", 0.6)
        assert acc.snapped_count == 1
        acc.accumulate("b", 0.7)
        assert acc.snapped_count == 2


# ── 4. No double-snap ───────────────────────────────────────────────────


class TestNoDoubleSnap:
    def test_no_resnap_after_threshold(self):
        acc = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
        acc.accumulate("t", 0.6)  # snaps
        r = acc.accumulate("t", 0.1)  # already above
        assert not r.snapped

    def test_no_resnap_at_exactly_one(self):
        acc = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
        acc.accumulate("t", 1.0)  # snaps
        r = acc.accumulate("t", 0.0)  # stays at 1.0
        assert not r.snapped

    def test_multiple_accumulates_after_snap_none_resnap(self):
        acc = EpsilonAccumulator(snap_threshold=0.3, decay=1.0)
        acc.accumulate("t", 0.5)  # snap
        for _ in range(10):
            assert not acc.accumulate("t", 0.01).snapped


# ── 5. Decay ────────────────────────────────────────────────────────────


class TestDecay:
    def test_decay_reduces_existing_confidence(self):
        acc = EpsilonAccumulator(decay=0.9)
        acc.accumulate("t", 1.0)
        r = acc.accumulate("t", 0.0)
        # previous=1.0, decayed=0.9, +0.0 = 0.9
        assert abs(r.new_confidence - 0.9) < 1e-9

    def test_compound_decay(self):
        acc = EpsilonAccumulator(decay=0.5)
        acc.accumulate("t", 1.0)  # 1.0
        acc.accumulate("t", 0.0)  # 0.5
        r = acc.accumulate("t", 0.0)  # 0.25
        assert abs(r.new_confidence - 0.25) < 1e-9

    def test_decay_with_positive_delta(self):
        acc = EpsilonAccumulator(decay=0.8)
        acc.accumulate("t", 0.5)  # 0.5
        r = acc.accumulate("t", 0.3)  # 0.5*0.8 + 0.3 = 0.7
        assert abs(r.new_confidence - 0.7) < 1e-9

    def test_no_decay_when_decay_is_one(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.5)
        r = acc.accumulate("t", 0.3)
        assert abs(r.new_confidence - 0.8) < 1e-9


# ── 6. Reset ────────────────────────────────────────────────────────────


class TestReset:
    def test_reset_clears_confidence(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.9)
        acc.reset("t")
        assert acc.get_confidence("t") == 0.0

    def test_reset_nonexistent_is_noop(self):
        acc = EpsilonAccumulator()
        acc.reset("ghost")  # should not raise

    def test_reset_removed_from_tile_count(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.5)
        assert acc.tile_count == 1
        acc.reset("t")
        assert acc.tile_count == 0

    def test_reset_allows_re_snap(self):
        acc = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
        acc.accumulate("t", 0.6)
        assert acc.snapped_count == 1
        acc.reset("t")
        assert acc.snapped_count == 0
        r = acc.accumulate("t", 0.6)
        assert r.snapped  # re-snaps after reset

    def test_reset_does_not_affect_other_tiles(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("a", 0.5)
        acc.accumulate("b", 0.7)
        acc.reset("a")
        assert acc.get_confidence("a") == 0.0
        assert abs(acc.get_confidence("b") - 0.7) < 1e-9


# ── 7. History ──────────────────────────────────────────────────────────


class TestHistory:
    def test_empty_history(self):
        acc = EpsilonAccumulator()
        assert acc.history() == []
        assert acc.history("t") == []

    def test_records_accumulation(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.1)
        acc.accumulate("t", 0.2)
        h = acc.history("t")
        assert len(h) == 2
        assert isinstance(h[0], AccumulationRecord)
        assert h[0].tile_id == "t"
        assert abs(h[0].delta - 0.1) < 1e-9
        assert abs(h[0].current - 0.1) < 1e-9

    def test_history_filter_by_tile(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("a", 0.1)
        acc.accumulate("b", 0.2)
        acc.accumulate("a", 0.3)
        assert len(acc.history("a")) == 2
        assert len(acc.history("b")) == 1

    def test_full_history(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("a", 0.1)
        acc.accumulate("b", 0.2)
        acc.accumulate("a", 0.3)
        assert len(acc.history()) == 3

    def test_record_has_timestamp(self):
        acc = EpsilonAccumulator(decay=1.0)
        before = time.time()
        acc.accumulate("t", 0.1)
        after = time.time()
        h = acc.history("t")
        assert before <= h[0].timestamp <= after

    def test_record_snap_flag(self):
        acc = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
        acc.accumulate("t", 0.3)
        acc.accumulate("t", 0.3)  # 0.6 → snap
        h = acc.history("t")
        assert not h[0].snapped
        assert h[1].snapped

    def test_record_repr(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.5)
        r = acc.history("t")[0]
        s = repr(r)
        assert "AccumulationRecord" in s
        assert "t" in s


# ── 8. Thread safety ────────────────────────────────────────────────────


class TestThreadSafety:
    def test_concurrent_accumulation(self):
        acc = EpsilonAccumulator(snap_threshold=1.0, decay=1.0)
        n_threads = 8
        n_ops = 1000
        barrier = threading.Barrier(n_threads)

        def worker():
            barrier.wait()
            for _ in range(n_ops):
                acc.accumulate("shared", 0.001)

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected = min(n_threads * n_ops * 0.001, 1.0)
        assert abs(acc.get_confidence("shared") - expected) < 0.01

    def test_concurrent_different_tiles(self):
        acc = EpsilonAccumulator(decay=1.0)
        n_threads = 8
        barrier = threading.Barrier(n_threads)

        def worker(idx):
            barrier.wait()
            for _ in range(200):
                acc.accumulate(f"tile-{idx}", 0.01)

        threads = [
            threading.Thread(target=worker, args=(i,)) for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        snap = acc.snapshot()
        for i in range(n_threads):
            assert abs(snap[f"tile-{i}"] - 2.0) < 0.01 or snap[f"tile-{i}"] == 1.0

    def test_concurrent_reset_and_accumulate(self):
        acc = EpsilonAccumulator(decay=1.0)
        errors = []

        def accumuler():
            try:
                for _ in range(500):
                    acc.accumulate("t", 0.01)
            except Exception as e:
                errors.append(e)

        def resetter():
            try:
                for _ in range(100):
                    acc.reset("t")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=accumuler)
        t2 = threading.Thread(target=resetter)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert errors == []


# ── 9. Edge cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    def test_threshold_at_one(self):
        """With threshold 1.0, only confidence exactly 1.0 triggers snap."""
        acc = EpsilonAccumulator(snap_threshold=1.0, decay=1.0)
        r = acc.accumulate("t", 0.99)
        assert not r.snapped
        r2 = acc.accumulate("t", 0.01)  # exactly 1.0
        assert r2.snapped
        assert r2.new_confidence == 1.0

    def test_threshold_near_zero(self):
        """Very small threshold snaps almost immediately."""
        acc = EpsilonAccumulator(snap_threshold=0.001, decay=1.0)
        r = acc.accumulate("t", 0.01)
        assert r.snapped

    def test_empty_tile_id_rejected(self):
        acc = EpsilonAccumulator()
        with pytest.raises(ValueError, match="tile_id"):
            acc.accumulate("", 0.5)

    def test_negative_delta_clamps_to_zero(self):
        acc = EpsilonAccumulator(decay=1.0)
        r = acc.accumulate("t", -0.5)
        assert r.new_confidence == 0.0

    def test_negative_delta_from_positive(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.5)
        r = acc.accumulate("t", -0.3)  # 0.5 - 0.3 = 0.2
        assert abs(r.new_confidence - 0.2) < 1e-9

    def test_negative_delta_clamps_negative_to_zero(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.1)
        r = acc.accumulate("t", -0.5)  # 0.1 - 0.5 = -0.4 → clamped to 0
        assert r.new_confidence == 0.0

    def test_zero_delta(self):
        acc = EpsilonAccumulator(decay=1.0)
        r = acc.accumulate("t", 0.0)
        assert r.new_confidence == 0.0
        assert not r.snapped


# ── 10. Snapshot ────────────────────────────────────────────────────────


class TestSnapshot:
    def test_empty_snapshot(self):
        acc = EpsilonAccumulator()
        assert acc.snapshot() == {}

    def test_snapshot_returns_copy(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.5)
        snap = acc.snapshot()
        snap["t"] = 0.0  # mutate copy
        assert acc.get_confidence("t") == 0.5  # original unchanged

    def test_snapshot_after_multiple_accumulates(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("a", 0.3)
        acc.accumulate("b", 0.6)
        acc.accumulate("a", 0.2)
        snap = acc.snapshot()
        assert abs(snap["a"] - 0.5) < 1e-9
        assert abs(snap["b"] - 0.6) < 1e-9

    def test_snapshot_after_reset(self):
        acc = EpsilonAccumulator(decay=1.0)
        acc.accumulate("t", 0.8)
        acc.reset("t")
        assert "t" not in acc.snapshot()


# ── 11. Integration: accumulate until snap, verify compiled ──────────────


class TestIntegration:
    def test_accumulate_until_snap(self):
        """Full lifecycle: small deltas → snap → verified as compiled."""
        acc = EpsilonAccumulator(snap_threshold=0.975, decay=0.995)
        tile = _tile(input_pattern="helm starboard 15", output_action="helm_stbd_15")

        # Feed deltas large enough to overcome 0.995 decay and cross 0.975
        deltas = [0.25, 0.25, 0.25, 0.25]
        snapped = False
        for d in deltas:
            r = acc.accumulate(tile.tile_id, d)
            if r.snapped:
                snapped = True

        assert snapped, "Should have snapped during accumulation"
        assert acc.get_confidence(tile.tile_id) >= 0.975

        # Verify in history
        hist = acc.history(tile.tile_id)
        snap_records = [h for h in hist if h.snapped]
        assert len(snap_records) == 1, "Exactly one snap event"

        # Post-snap: no re-snap
        r = acc.accumulate(tile.tile_id, 0.005)
        assert not r.snapped

    def test_multiple_tiles_snap_independently(self):
        acc = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
        tiles = [
            _tile(input_pattern=f"cmd-{i}", output_action=f"act-{i}")
            for i in range(5)
        ]

        for i, t in enumerate(tiles):
            acc.accumulate(t.tile_id, 0.3)
            acc.accumulate(t.tile_id, 0.3)  # 0.6 → snap

        assert acc.snapped_count == 5
        assert acc.tile_count == 5

    def test_accumulation_result_repr(self):
        acc = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
        r = acc.accumulate("t", 0.6)
        s = repr(r)
        assert "AccumulationResult" in s
        assert "★ SNAP" in s

    def test_accumulation_result_no_snap_repr(self):
        acc = EpsilonAccumulator(decay=1.0)
        r = acc.accumulate("t", 0.1)
        s = repr(r)
        assert "★ SNAP" not in s

    def test_decay_prevents_snap_without_reinforcement(self):
        """With decay < 1.0, confidence erodes without ongoing deltas."""
        acc = EpsilonAccumulator(snap_threshold=0.8, decay=0.5)
        acc.accumulate("t", 1.0)  # 1.0

        # Without reinforcement, decay eats away
        for _ in range(5):
            acc.accumulate("t", 0.0)

        # 1.0 * 0.5^5 = 0.03125 — well below threshold
        assert acc.get_confidence("t") < 0.1
        assert acc.snapped_count == 0  # never hit 0.8 from below
