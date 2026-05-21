"""Tests for SoftRoom and HardRoom."""

import pytest

from luciddreamer.rooms import SoftRoom, HardRoom
from luciddreamer.signal_chain import SignalChainRoom, EpsilonAccumulator
from luciddreamer.tiles import Tile, TileType, TileStore
from luciddreamer.router import RouteDecision


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_tile(pattern: str = "test", action: str = "do_thing",
              confidence: float = 0.5, tile_type: TileType = TileType.COMMAND) -> Tile:
    return Tile(tile_type, pattern, action, confidence=confidence)


# ===================================================================
# SoftRoom tests
# ===================================================================

class TestSoftRoomConstruction:
    def test_dial_locked_at_1(self):
        room = SoftRoom()
        assert room.dial == 1.0

    def test_inherits_signal_chain_room(self):
        assert issubclass(SoftRoom, SignalChainRoom)

    def test_set_dial_is_noop(self):
        room = SoftRoom()
        room.set_dial(0.0)
        assert room.dial == 1.0


class TestSoftRoomAdmit:
    def test_admits_low_confidence(self):
        room = SoftRoom()
        tile = make_tile(confidence=0.1)
        admitted = room.admit(tile)
        assert admitted is tile

    def test_admits_high_confidence(self):
        room = SoftRoom()
        tile = make_tile(confidence=0.95)
        admitted = room.admit(tile)
        assert admitted is tile

    def test_admits_zero_confidence(self):
        room = SoftRoom()
        tile = make_tile(confidence=0.0)
        admitted = room.admit(tile)
        assert admitted is tile


class TestSoftRoomEpsilonAccumulation:
    def test_accumulator_tracks_confidence(self):
        room = SoftRoom(epsilon=0.01)
        tile = make_tile(confidence=0.5)
        room.admit(tile)
        # The accumulator should have been updated
        assert room._accumulator.last == 0.5

    def test_auto_compile_at_threshold(self):
        room = SoftRoom(compile_threshold=0.975, epsilon=0.001)
        tile = make_tile(confidence=0.98)
        admitted = room.admit(tile)
        # 0.98 >= 0.975 compile threshold → auto-compiled to confidence 1.0
        assert admitted.confidence == 1.0

    def test_no_auto_compile_below_threshold(self):
        room = SoftRoom(compile_threshold=0.975, epsilon=0.001)
        tile = make_tile(confidence=0.5)
        admitted = room.admit(tile)
        assert admitted.confidence == 0.5


class TestSoftRoomCascade:
    def test_cascade_pushes_to_children(self):
        parent = SoftRoom(name="parent")
        child = SoftRoom(name="child")
        parent.add_child(child)

        tile = make_tile(pattern="hello", confidence=0.0)
        parent.admit(tile)
        # Manually set it to snap status to test propagation
        tile.confidence = 1.0
        parent.propagate_snaps()

        # Child should have the snap
        child_tiles = list(child.store)
        assert len(child_tiles) >= 1
        assert any(t.input_pattern == "hello" for t in child_tiles)


class TestSoftRoomQuery:
    def test_query_returns_tiles(self):
        room = SoftRoom()
        tile = make_tile(pattern="lookup", confidence=0.3)
        room.admit(tile)
        # find_at_dial with dial=1.0 accepts all confidences
        results = room.find_at_dial("lookup")
        assert any(t.input_pattern == "lookup" for t in results)


# ===================================================================
# HardRoom tests
# ===================================================================

class TestHardRoomConstruction:
    def test_dial_locked_at_0(self):
        room = HardRoom()
        assert room.dial == 0.0

    def test_inherits_signal_chain_room(self):
        assert issubclass(HardRoom, SignalChainRoom)

    def test_set_dial_is_noop(self):
        room = HardRoom()
        room.set_dial(1.0)
        assert room.dial == 0.0


class TestHardRoomAdmit:
    def test_admits_snap_confidence_1(self):
        room = HardRoom()
        tile = make_tile(confidence=1.0)
        admitted = room.admit(tile)
        assert admitted is tile

    def test_rejects_low_confidence(self):
        room = HardRoom()
        tile = make_tile(confidence=0.5)
        admitted = room.admit(tile)
        assert admitted is None

    def test_rejects_zero_confidence(self):
        room = HardRoom()
        tile = make_tile(confidence=0.0)
        admitted = room.admit(tile)
        assert admitted is None

    def test_rejects_near_one_confidence(self):
        room = HardRoom()
        tile = make_tile(confidence=0.99)
        admitted = room.admit(tile)
        assert admitted is None


class TestHardRoomNoFallback:
    def test_rejected_route_returns_fallback_rejected(self):
        room = HardRoom()
        decision, payload = room.route("unknown command")
        assert decision == RouteDecision.FALLBACK
        assert payload["action"] == "REJECTED"


class TestHardRoomQuery:
    def test_query_returns_only_compiled(self):
        room = HardRoom()
        # Add a snap
        snap = make_tile(pattern="known", confidence=1.0)
        room.admit(snap)
        # Try to add a non-snap — should be rejected
        infer = make_tile(pattern="guess", confidence=0.4)
        room.admit(infer)

        snaps = room.snaps
        assert len(snaps) == 1
        assert snaps[0].input_pattern == "known"


# ===================================================================
# SoftRoom → HardRoom chain tests
# ===================================================================

class TestSoftToHardChain:
    def test_soft_accumulates_cascades_to_hard(self):
        soft = SoftRoom(name="soft")
        hard = HardRoom(name="hard")
        soft.add_child(hard)

        # Put a snap in soft
        snap = make_tile(pattern="verified", confidence=1.0)
        soft.admit(snap)
        soft.propagate_snaps()

        # Hard should now have the snap
        assert any(t.input_pattern == "verified" for t in hard.store)

    def test_only_snapped_tiles_survive_cascade(self):
        soft = SoftRoom(name="soft")
        hard = HardRoom(name="hard")
        soft.add_child(hard)

        # Low-confidence tile — not a snap
        infer = make_tile(pattern="flaky", confidence=0.3)
        soft.admit(infer)
        soft.propagate_snaps()

        # Hard should NOT have this tile (it's not in soft.snaps)
        assert not any(t.input_pattern == "flaky" for t in hard.snaps)

    def test_full_flow_inference_accumulate_snap_cascade(self):
        """End-to-end: inference → accumulate → snap → cascade → hard room."""
        soft = SoftRoom(name="soft", compile_threshold=0.975, epsilon=0.001)
        hard = HardRoom(name="hard")
        soft.add_child(hard)

        # Simulate a tile that auto-compiles
        tile = make_tile(pattern="auto_snap", confidence=0.98)
        admitted = soft.admit(tile)
        assert admitted.confidence == 1.0  # auto-compiled

        # Propagate to hard
        soft.propagate_snaps()

        # Hard should have it
        hard_snaps = hard.snaps
        assert len(hard_snaps) == 1
        assert hard_snaps[0].input_pattern == "auto_snap"
        assert hard_snaps[0].confidence == 1.0
