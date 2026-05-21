"""Tests for the LucidDreamer maritime intelligence system."""

from luciddreamer.tiles import (
    Tile, TileType, Confidence, Verifier, TileStore,
    CommandTile, VisionTile, ChartTile,
)
from luciddreamer.compiler import RigidFinder, CompiledCommand
from luciddreamer.bathymetry import BathymetricMap, DepthSounding
from luciddreamer.router import Router, RouteDecision
from luciddreamer.training import (
    TrainingDataGenerator, LoRACheckpoint, CheckpointManager, CheckpointDiff,
)
from luciddreamer.simulators import (
    AutopilotSimulator, FishSortSimulator, ChartSimulator,
    CaptainReviewSimulator, FullTripSimulator,
)
import pytest


# ---------------------------------------------------------------------------
# Tile system tests
# ---------------------------------------------------------------------------

class TestTile:
    def test_tile_id_deterministic(self):
        t1 = Tile(tile_type=TileType.COMMAND, input_pattern="turn port 10", output_action="TURN_PORT(10)")
        t2 = Tile(tile_type=TileType.COMMAND, input_pattern="turn port 10", output_action="TURN_PORT(10)")
        assert t1.tile_id == t2.tile_id

    def test_confidence_class_compiled(self):
        t = Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=1.0)
        assert t.confidence_class == Confidence.COMPILED

    def test_confidence_class_verified(self):
        t = Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=0.92)
        assert t.confidence_class == Confidence.VERIFIED

    def test_confidence_class_tentative(self):
        t = Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=0.75)
        assert t.confidence_class == Confidence.TENTATIVE

    def test_confidence_class_ambiguous(self):
        t = Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=0.55)
        assert t.confidence_class == Confidence.AMBIGUOUS

    def test_confidence_class_unknown(self):
        t = Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=0.3)
        assert t.confidence_class == Confidence.UNKNOWN

    def test_record_use_increases_confidence(self):
        t = Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=0.5)
        t.record_use(True)
        assert t.confidence > 0.5
        assert t.times_used == 1

    def test_record_correction_decreases_confidence(self):
        t = Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=0.8)
        t.record_use(False)
        assert t.confidence < 0.8
        assert t.times_corrected == 1

    def test_serialization_roundtrip(self):
        t = Tile(tile_type=TileType.COMMAND, input_pattern="steady", output_action="HOLD", confidence=0.95, source="captain")
        d = t.to_dict()
        t2 = Tile.from_dict(d)
        assert t2.input_pattern == t.input_pattern
        assert t2.output_action == t.output_action
        assert t2.confidence == t.confidence


class TestTileStore:
    def test_add_and_get(self):
        store = TileStore()
        t = Tile(tile_type=TileType.COMMAND, input_pattern="port 10", output_action="TURN_PORT(10)")
        tid = store.add(t)
        assert store.get(tid) is not None

    def test_find_by_type(self):
        store = TileStore()
        store.add(Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y"))
        store.add(Tile(tile_type=TileType.VISION, input_pattern="z", output_action="w"))
        assert len(store.find_by_type(TileType.COMMAND)) == 1
        assert len(store.find_by_type(TileType.VISION)) == 1

    def test_find_compiled(self):
        store = TileStore()
        store.add(Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=1.0))
        store.add(Tile(tile_type=TileType.COMMAND, input_pattern="z", output_action="w", confidence=0.5))
        assert len(store.find_compiled()) == 1

    def test_json_roundtrip(self):
        store = TileStore()
        store.add(Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=0.9))
        json_data = store.export_json()
        store2 = TileStore()
        count = store2.import_json(json_data)
        assert count == 1
        assert len(store2) == 1


# ---------------------------------------------------------------------------
# Compiler tests
# ---------------------------------------------------------------------------

class TestCompiler:
    def _make_verified_tile(self, pattern, action, regex="", uses=25, correct=25):
        t = CommandTile(
            input_pattern=pattern,
            output_action=action,
            regex_pattern=regex,
            confidence=1.0,
            source="captain",
            times_used=uses,
            times_correct=correct,
        )
        return t

    def test_compile_verified_tile(self):
        store = TileStore()
        t = self._make_verified_tile("turn port 10", "TURN_PORT(10)", r"^turn port (?P<deg>\d+)$")
        store.add(t)
        finder = RigidFinder(store)
        compiled = finder.compile_all()
        assert len(compiled) == 1

    def test_match_compiled_command(self):
        store = TileStore()
        t = self._make_verified_tile("turn port 10", "TURN_PORT(10)", r"^turn port (?P<deg>\d+)$")
        store.add(t)
        finder = RigidFinder(store)
        finder.compile_all()
        result = finder.match("turn port 10")
        assert result is not None
        assert result["action"] == "TURN_PORT(10)"

    def test_no_match_returns_none(self):
        store = TileStore()
        finder = RigidFinder(store)
        assert finder.match("turn port 10") is None

    def test_low_confidence_not_compiled(self):
        store = TileStore()
        t = CommandTile(input_pattern="x", output_action="y", confidence=0.5, times_used=3)
        store.add(t)
        finder = RigidFinder(store)
        assert len(finder.compile_all()) == 0

    def test_too_few_uses_not_compiled(self):
        store = TileStore()
        t = CommandTile(input_pattern="x", output_action="y", confidence=1.0, times_used=1)
        store.add(t)
        finder = RigidFinder(store)
        assert len(finder.compile_all()) == 0


# ---------------------------------------------------------------------------
# Router tests
# ---------------------------------------------------------------------------

class TestRouter:
    def test_compiled_route(self):
        store = TileStore()
        t = CommandTile(
            input_pattern="steady", output_action="HOLD", confidence=1.0,
            regex_pattern="^steady$", times_used=30, times_correct=30,
        )
        store.add(t)
        finder = RigidFinder(store)
        finder.compile_all()
        router = Router(store, finder)
        dec, res = router.route("steady")
        assert dec == RouteDecision.COMPILED

    def test_fallback_route(self):
        store = TileStore()
        finder = RigidFinder(store)
        router = Router(store, finder, fallback_fn=lambda x: {"action": "CLOUD:" + x})
        dec, res = router.route("something completely new")
        assert dec == RouteDecision.FALLBACK
        assert "CLOUD:" in res["action"]

    def test_pending_review(self):
        store = TileStore()
        finder = RigidFinder(store)
        router = Router(store, finder, fallback_fn=lambda x: {"action": "Y"})
        router.route("new command")
        assert router.pending_count == 1
        router.confirm_pending(0, correct=True)
        assert router.pending_count == 0
        assert len(store) == 1


# ---------------------------------------------------------------------------
# Bathymetry tests
# ---------------------------------------------------------------------------

class TestBathymetry:
    def test_coverage_calculation(self):
        bathy = BathymetricMap()
        bathy.update("turn", compiled=8, total=10)
        assert bathy.soundings["turn"].coverage == 0.8

    def test_overall_coverage(self):
        bathy = BathymetricMap()
        bathy.update("turn", compiled=8, total=10)
        bathy.update("speed", compiled=3, total=10)
        assert abs(bathy.overall_coverage - 0.55) < 0.01

    def test_render(self):
        bathy = BathymetricMap()
        bathy.update("turn", compiled=5, total=10)
        output = bathy.render()
        assert "█" in output
        assert "░" in output


# ---------------------------------------------------------------------------
# Training tests
# ---------------------------------------------------------------------------

class TestTraining:
    def test_generate_from_tiles(self):
        store = TileStore()
        store.add(Tile(tile_type=TileType.COMMAND, input_pattern="steady", output_action="HOLD", confidence=0.95))
        gen = TrainingDataGenerator(store)
        data = gen.generate(include_variations=False, include_negatives=False)
        assert len(data) >= 1

    def test_checkpoint_manager(self):
        mgr = CheckpointManager()
        cp1 = LoRACheckpoint(version="v1.0", overall_accuracy=0.80)
        mgr.add(cp1)
        cp2 = LoRACheckpoint(version="v1.1", overall_accuracy=0.85, parent_version="v1.0")
        diff = mgr.add(cp2)
        assert diff.is_improvement
        assert mgr.get_active().version == "v1.1"

    def test_rollback(self):
        mgr = CheckpointManager()
        mgr.add(LoRACheckpoint(version="v1.0", overall_accuracy=0.85))
        mgr.add(LoRACheckpoint(version="v1.1", overall_accuracy=0.80))
        mgr.rollback("v1.0")
        assert mgr.get_active().version == "v1.0"

    def test_diff_diagnosis_regression(self):
        diff = CheckpointDiff(
            old=LoRACheckpoint(version="v1.0", overall_accuracy=0.90),
            new=LoRACheckpoint(version="v1.1", overall_accuracy=0.82),
        )
        assert diff.is_regression
        assert "REGRESSION" in diff.diagnose()


# ---------------------------------------------------------------------------
# Simulator tests
# ---------------------------------------------------------------------------

class TestSimulators:
    def test_autopilot_generates_commands(self):
        sim = AutopilotSimulator()
        cmds = sim.generate_commands(20)
        assert len(cmds) == 20
        assert all("text" in c and "expected_action" in c for c in cmds)

    def test_autopilot_categories(self):
        sim = AutopilotSimulator()
        cmds = sim.generate_commands(50)
        categories = {c["category"] for c in cmds}
        assert "exact" in categories or "abstraction" in categories

    def test_fish_sort_generates_events(self):
        sim = FishSortSimulator()
        events = sim.generate_events(20)
        assert len(events) == 20
        assert all("classified_species" in e for e in events)

    def test_fish_species_realistic(self):
        sim = FishSortSimulator()
        events = sim.generate_events(50)
        species = {e["classified_species"] for e in events}
        # Should include Pacific salmon species
        assert any(s in species for s in ["Chinook", "Sockeye", "Pink", "Chum", "Halibut"])

    def test_chart_simulator(self):
        sim = ChartSimulator()
        queries = sim.generate_queries(10)
        assert len(queries) == 10

    def test_captain_review(self):
        sim = CaptainReviewSimulator()
        store = TileStore()
        store.add(Tile(tile_type=TileType.COMMAND, input_pattern="x", output_action="y", confidence=0.6))
        result = sim.review_session(store)
        assert result is not None

    def test_full_trip(self):
        sim = FullTripSimulator()
        report = sim.run()
        assert "total_tiles" in report
        assert "phases" in report

    def test_full_trip_has_phases(self):
        sim = FullTripSimulator()
        report = sim.run()
        phases = report.get("phases", [])
        assert len(phases) > 0
