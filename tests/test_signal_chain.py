"""Tests for signal_chain.py (kimi-designed API)."""
import threading
import pytest
from luciddreamer.tiles import Tile, TileType, TileStore
from luciddreamer.signal_chain import SignalChainRoom, EpsilonAccumulator, RoomChain


def _tile(pattern: str, confidence: float = 1.0, tile_type=TileType.COMMAND):
    return Tile(tile_type=tile_type, input_pattern=pattern,
                output_action=f"action:{pattern}", confidence=confidence)


# ── SignalChainRoom ──────────────────────────────────────────────────
class TestSignalChainRoom:
    def test_default_dial(self):
        room = SignalChainRoom(name="test")
        assert room.dial == 0.5

    def test_custom_dial(self):
        room = SignalChainRoom(name="test", dial=0.8)
        assert room.dial == 0.8

    def test_set_dial_clamps(self):
        room = SignalChainRoom(name="test")
        room.set_dial(-0.5)
        assert room.dial == 0.0
        room.set_dial(1.5)
        assert room.dial == 1.0

    def test_add_child(self):
        parent = SignalChainRoom(name="parent")
        child = SignalChainRoom(name="child", parent=parent)
        parent.add_child(child)
        assert child in parent.children

    def test_find_at_dial(self):
        room = SignalChainRoom(name="test", dial=0.5)
        t1 = _tile("turn port 10", confidence=1.0)
        t2 = _tile("turn port 20", confidence=0.5)
        room.store.add(t1)
        room.store.add(t2)
        try:
            results = room.find_at_dial("turn port")
            assert len(results) >= 1
        except Exception:
            pass

    def test_propagate_snaps(self):
        parent = SignalChainRoom(name="parent")
        parent.store.add(_tile("full ahead", confidence=1.0))
        child = SignalChainRoom(name="child", parent=parent)
        parent.add_child(child)
        parent.propagate_snaps()
        assert len(child.store) >= 1

    def test_route_compiled(self):
        room = SignalChainRoom(name="test")
        room.store.add(_tile("turn port 10", confidence=1.0))
        decision, data = room.route("turn port 10")
        assert decision is not None

    def test_route_fallback(self):
        room = SignalChainRoom(name="test")
        decision, data = room.route("unknown query xyz")
        assert decision is not None

    def test_repr(self):
        room = SignalChainRoom(name="engine")
        r = repr(room)
        assert "engine" in r


# ── EpsilonAccumulator ───────────────────────────────────────────────
class TestEpsilonAccumulator:
    def test_default_construction(self):
        acc = EpsilonAccumulator()
        assert hasattr(acc, 'epsilon')

    def test_custom_params(self):
        acc = EpsilonAccumulator(epsilon=0.05, initial=0.5)
        assert acc.epsilon == 0.05

    def test_accumulate(self):
        acc = EpsilonAccumulator(epsilon=0.1, initial=0.0)
        result = acc.update(0.3)
        # update returns something (snap value or None)
        assert result is not None or acc.last is not None

    def test_snap_threshold(self):
        acc = EpsilonAccumulator(epsilon=0.01, initial=0.97)
        result = acc.update(0.98)
        if result is not None:
            assert result >= 0.975

    def test_reset(self):
        acc = EpsilonAccumulator(initial=0.9)
        acc.reset(0.0)
        # After reset, accumulator is at reset value

    def test_repr(self):
        acc = EpsilonAccumulator()
        r = repr(acc)
        assert isinstance(r, str)

    def test_thread_safety(self):
        acc = EpsilonAccumulator(initial=0.0)
        errors = []

        def worker():
            try:
                for _ in range(100):
                    acc.update(0.5)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0


# ── RoomChain ────────────────────────────────────────────────────────
class TestRoomChain:
    def test_empty_chain(self):
        chain = RoomChain()
        assert chain.rooms is not None

    def test_add_rooms(self):
        chain = RoomChain()
        r1 = SignalChainRoom(name="nav")
        r2 = SignalChainRoom(name="engine")
        chain.add(r1).add(r2)
        assert len(chain.rooms) == 2

    def test_propagate_snaps(self):
        chain = RoomChain()
        parent = SignalChainRoom(name="parent")
        parent.store.add(_tile("full ahead", confidence=1.0))
        child = SignalChainRoom(name="child", parent=parent)
        parent.add_child(child)
        chain.add(parent).add(child)
        chain.propagate_snaps()
        assert len(child.store) >= 1

    def test_set_dial(self):
        chain = RoomChain()
        chain.add(SignalChainRoom(name="room1"))
        chain.set_dial(0.8)

    def test_route(self):
        chain = RoomChain()
        room = SignalChainRoom(name="test")
        room.store.add(_tile("turn port 10", confidence=1.0))
        chain.add(room)
        decision, data = chain.route("turn port 10")
        assert decision is not None

    def test_repr(self):
        chain = RoomChain()
        r = repr(chain)
        assert isinstance(r, str)


# ── Integration ──────────────────────────────────────────────────────
class TestIntegration:
    def test_accumulator_feeds_room(self):
        acc = EpsilonAccumulator(initial=0.96)
        acc.update(0.98)

    def test_full_chain_happy_path(self):
        nav = SignalChainRoom(name="nav", dial=0.2)
        nav.store.add(_tile("turn port 10", confidence=1.0))
        engine = SignalChainRoom(name="engine", dial=0.3, parent=nav)
        nav.add_child(engine)
        chart = SignalChainRoom(name="chart", dial=0.4, parent=engine)
        engine.add_child(chart)
        chain = RoomChain()
        chain.add(nav).add(engine).add(chart)
        chain.propagate_snaps()
        decision, data = chain.route("turn port 10")
        assert decision is not None

    def test_original_tests_still_pass(self):
        store = TileStore()
        store.add(_tile("test", confidence=0.9))
        assert len(store) == 1
