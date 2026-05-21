"""Epsilon accumulator — small confidence deltas compound into structure over time.

Oracle1's key insight from The Soft Room: "The epsilon doesn't go to zero.
It accumulates." Each low-confidence signal adds sediment. Given enough time,
sediment becomes rock.

The snap moment (from The Snap): when accumulated confidence crosses the
compile threshold (97.5%, from compiler.py / dream.rs data), inference
becomes hard-locked fact. The line comes tight.

Thread-safe. Pure accumulation with optional decay — no model calls, no tokens.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

__all__ = [
    "AccumulationRecord",
    "AccumulationResult",
    "EpsilonAccumulator",
]


@dataclass(frozen=True)
class AccumulationRecord:
    """Immutable log of a single accumulation event."""

    tile_id: str
    delta: float
    previous: float
    current: float
    snapped: bool
    timestamp: float

    def __repr__(self) -> str:
        snap_flag = " ★ SNAP" if self.snapped else ""
        return (
            f"AccumulationRecord({self.tile_id!r} "
            f"{self.previous:.4f} + {self.delta:+.4f} → {self.current:.4f}{snap_flag})"
        )


@dataclass(frozen=True)
class AccumulationResult:
    """Result of a single accumulate() call."""

    tile_id: str
    previous_confidence: float
    new_confidence: float
    snapped: bool
    delta_applied: float

    def __repr__(self) -> str:
        snap_flag = " ★ SNAP" if self.snapped else ""
        return (
            f"AccumulationResult({self.tile_id!r} "
            f"{self.previous_confidence:.4f} → {self.new_confidence:.4f}{snap_flag})"
        )


class EpsilonAccumulator:
    """Accumulates small confidence deltas until tiles snap (cross threshold).

    From The Soft Room: 'The epsilon doesn't go to zero. It accumulates.'
    From The Snap: the moment inference crosses confidence 1.0 and becomes
    hard-locked fact.

    Args:
        snap_threshold: Confidence level at which a tile "snaps" (default 0.975,
            matching the compile threshold from compiler.py).
        decay: Per-accumulate multiplicative decay applied to existing confidence
            before adding the new delta. 1.0 = no decay. Values < 1.0 mean old
            evidence fades slightly, requiring ongoing reinforcement. Default 0.995.
    """

    def __init__(self, snap_threshold: float = 0.975, decay: float = 0.995) -> None:
        if not 0.0 < snap_threshold <= 1.0:
            raise ValueError(f"snap_threshold must be in (0, 1], got {snap_threshold}")
        if not 0.0 < decay <= 1.0:
            raise ValueError(f"decay must be in (0, 1], got {decay}")
        self._snap_threshold = snap_threshold
        self._decay = decay
        self._accumulations: dict[str, float] = {}  # tile_id -> accumulated confidence
        self._history: list[AccumulationRecord] = []
        self._lock = threading.Lock()

    # ── core ─────────────────────────────────────────────────────────────

    def accumulate(self, tile_id: str, delta: float) -> AccumulationResult:
        """Add a confidence delta. Returns result with snapped=True if crossed threshold.

        Args:
            tile_id: Identifier for the tile being accumulated.
            delta: Confidence delta to add. Can be positive or negative.

        Returns:
            AccumulationResult describing the state transition.
        """
        if not tile_id:
            raise ValueError("tile_id must be non-empty")

        with self._lock:
            previous = self._accumulations.get(tile_id, 0.0)

            # Apply decay to existing confidence, then add delta
            decayed = previous * self._decay
            new = max(0.0, decayed + delta)

            # Cap at 1.0
            new = min(new, 1.0)

            already_snapped = previous >= self._snap_threshold
            now_snapped = new >= self._snap_threshold
            snapped = now_snapped and not already_snapped

            self._accumulations[tile_id] = new

            record = AccumulationRecord(
                tile_id=tile_id,
                delta=delta,
                previous=previous,
                current=new,
                snapped=snapped,
                timestamp=time.time(),
            )
            self._history.append(record)

            return AccumulationResult(
                tile_id=tile_id,
                previous_confidence=previous,
                new_confidence=new,
                snapped=snapped,
                delta_applied=delta,
            )

    def get_confidence(self, tile_id: str) -> float:
        """Current accumulated confidence for a tile. Returns 0.0 if unknown."""
        with self._lock:
            return self._accumulations.get(tile_id, 0.0)

    def history(self, tile_id: str | None = None) -> list[AccumulationRecord]:
        """Get accumulation history, optionally filtered by tile_id."""
        with self._lock:
            if tile_id is None:
                return list(self._history)
            return [r for r in self._history if r.tile_id == tile_id]

    def reset(self, tile_id: str) -> None:
        """Reset a tile's accumulation to zero (for rollback)."""
        with self._lock:
            self._accumulations.pop(tile_id, None)

    def snapshot(self) -> dict[str, float]:
        """Get all current accumulations as {tile_id: confidence}."""
        with self._lock:
            return dict(self._accumulations)

    # ── info ─────────────────────────────────────────────────────────────

    @property
    def snap_threshold(self) -> float:
        return self._snap_threshold

    @property
    def decay(self) -> float:
        return self._decay

    @property
    def tile_count(self) -> int:
        """Number of tiles currently being tracked."""
        with self._lock:
            return len(self._accumulations)

    @property
    def snapped_count(self) -> int:
        """Number of tiles currently above snap threshold."""
        with self._lock:
            return sum(
                1 for c in self._accumulations.values() if c >= self._snap_threshold
            )

    def __repr__(self) -> str:
        return (
            f"EpsilonAccumulator("
            f"tiles={self.tile_count}, "
            f"snapped={self.snapped_count}, "
            f"threshold={self._snap_threshold}, "
            f"decay={self._decay})"
        )


# ── inline tests ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    failures = 0

    def check(name: str, condition: bool) -> None:
        global failures
        if condition:
            print(f"  ✓ {name}")
        else:
            print(f"  ✗ {name}")
            failures += 1

    print("EpsilonAccumulator — unit tests\n")

    # --- construction ---
    print("[construction]")
    acc = EpsilonAccumulator(snap_threshold=0.975, decay=0.995)
    check("empty tile_count", acc.tile_count == 0)
    check("empty snapshot", acc.snapshot() == {})
    check("repr", "EpsilonAccumulator" in repr(acc))

    # --- basic accumulation ---
    print("\n[basic accumulation]")
    r = acc.accumulate("tile-a", 0.3)
    check("first delta gives 0.3", abs(r.new_confidence - 0.3) < 1e-9)
    check("not snapped at 0.3", not r.snapped)

    r2 = acc.accumulate("tile-a", 0.4)
    # previous was 0.3, decayed: 0.3 * 0.995 = 0.2985, + 0.4 = 0.6985
    check("second delta accumulates", abs(r2.new_confidence - 0.6985) < 1e-9)
    check("not snapped at ~0.7", not r2.snapped)

    # --- snap ---
    print("\n[snap]")
    r3 = acc.accumulate("tile-a", 0.3)
    # previous ~0.6985, decayed: 0.6985 * 0.995 = 0.6950075, + 0.3 = 0.9950075 → capped 0.995...
    # but we cap at 1.0, and 0.9950075 > 0.975, so it snaps
    check("confidence exceeds threshold", r3.new_confidence >= 0.975)
    check("SNAPPED", r3.snapped)

    # --- no double-snap ---
    print("\n[no double-snap]")
    r4 = acc.accumulate("tile-a", 0.01)
    check("already snapped, no re-snap", not r4.snapped)

    # --- separate tiles ---
    print("\n[independent tiles]")
    acc.accumulate("tile-b", 0.5)
    check("tile-b has own confidence", abs(acc.get_confidence("tile-b") - 0.5) < 1e-9)
    check("tile-a unaffected", acc.get_confidence("tile-a") >= 0.975)
    check("unknown tile returns 0.0", acc.get_confidence("unknown") == 0.0)

    # --- reset ---
    print("\n[reset]")
    acc.reset("tile-a")
    check("tile-a reset to 0", acc.get_confidence("tile-a") == 0.0)
    check("tile-b unaffected", abs(acc.get_confidence("tile-b") - 0.5) < 1e-9)

    # --- history ---
    print("\n[history]")
    acc2 = EpsilonAccumulator(snap_threshold=0.8, decay=1.0)
    acc2.accumulate("x", 0.3)
    acc2.accumulate("x", 0.3)
    acc2.accumulate("y", 0.5)
    x_hist = acc2.history("x")
    check("x has 2 records", len(x_hist) == 2)
    all_hist = acc2.history()
    check("total 3 records", len(all_hist) == 3)
    check("first x record has delta 0.3", abs(x_hist[0].delta - 0.3) < 1e-9)

    # --- thread safety ---
    print("\n[thread safety]")
    acc3 = EpsilonAccumulator(snap_threshold=1.0, decay=1.0)
    n_threads = 8
    n_ops = 1000
    barrier = threading.Barrier(n_threads)

    def worker():
        barrier.wait()
        for i in range(n_ops):
            acc3.accumulate("shared", 0.001)

    threads = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected = min(n_threads * n_ops * 0.001, 1.0)
    check(
        f"thread-safe accumulation (expected ~{expected:.3f})",
        abs(acc3.get_confidence("shared") - expected) < 0.01,
    )

    # --- edge cases ---
    print("\n[edge cases]")
    acc4 = EpsilonAccumulator(snap_threshold=0.5, decay=1.0)
    r_neg = acc4.accumulate("neg", -0.2)
    check("negative delta clamped to 0", r_neg.new_confidence == 0.0)
    r_cap = acc4.accumulate("cap", 1.5)
    check("confidence capped at 1.0", r_cap.new_confidence == 1.0)

    # --- validation ---
    print("\n[validation]")
    try:
        EpsilonAccumulator(snap_threshold=0.0)
        check("rejects threshold 0", False)
    except ValueError:
        check("rejects threshold 0", True)
    try:
        acc.accumulate("", 0.5)
        check("rejects empty tile_id", False)
    except ValueError:
        check("rejects empty tile_id", True)

    # --- result
    print(f"\n{'='*40}")
    if failures == 0:
        print("All tests passed ✓")
    else:
        print(f"{failures} test(s) FAILED ✗")
        sys.exit(1)
