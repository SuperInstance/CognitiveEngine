"""Tests for the domain adapter system (luciddreamer.domain)."""

import pytest

from luciddreamer.domain import (
    DomainAdapter,
    MaritimeAdapter,
    RetailAdapter,
    HealthcareAdapter,
    WebAdapter,
    VerificationResult,
)
from luciddreamer.signal_chain import RoomChain
from luciddreamer.tiles import Tile, TileType, Verifier
from luciddreamer.rooms import SoftRoom, HardRoom


# ── helpers ──────────────────────────────────────────────────────────

def _tile(confidence: float = 0.8, **kw) -> Tile:
    defaults = dict(
        tile_type=TileType.COMMAND,
        input_pattern="test-pattern",
        output_action="TEST",
        confidence=confidence,
    )
    defaults.update(kw)
    return Tile(**defaults)


# =====================================================================
# DomainAdapter ABC
# =====================================================================

class TestDomainAdapterABC:

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            DomainAdapter()

    def test_concrete_adapter_instantiates(self):
        adapter = MaritimeAdapter()
        assert isinstance(adapter, DomainAdapter)

    def test_verify_returns_verification_results(self):
        adapter = MaritimeAdapter()
        results = adapter.verify([_tile()])
        assert isinstance(results, list)
        assert all(isinstance(r, VerificationResult) for r in results)

    def test_ground_truth_returns_tiles(self):
        adapter = MaritimeAdapter()
        tiles = adapter.ground_truth()
        assert isinstance(tiles, list)
        assert all(isinstance(t, Tile) for t in tiles)

    def test_on_snap_called_when_tile_crosses_threshold(self):
        adapter = MaritimeAdapter()
        tile = _tile(confidence=0.98)
        adapter.on_snap(tile)
        # on_snap sets metadata flags, it doesn't log
        assert tile.metadata.get("buyer_report_pending") is True

    def test_create_room_chain_returns_soft_hard(self):
        adapter = MaritimeAdapter()
        chain = adapter.create_room_chain()
        assert isinstance(chain, RoomChain)
        # Default chain: SoftRoom → SignalChainRoom → HardRoom
        assert isinstance(chain.rooms[0], SoftRoom)
        assert isinstance(chain.rooms[-1], HardRoom)


# =====================================================================
# MaritimeAdapter
# =====================================================================

class TestMaritimeAdapter:

    def test_verify_catches_mismatch(self):
        adapter = MaritimeAdapter()
        # Tile with no matching ground truth should fail
        low = _tile(confidence=0.2)
        results = adapter.verify([low])
        assert len(results) == 1
        assert results[0].passed is False
        assert "no ground-truth" in results[0].notes.lower()

    def test_verify_passes_good_tile(self):
        adapter = MaritimeAdapter()
        # Tile matching captain command ground truth
        good = _tile(
            input_pattern="steady as she goes",
            output_action="helm_hold_course",
            tile_type=TileType.COMMAND,
        )
        results = adapter.verify([good])
        assert results[0].passed is True

    def test_ground_truth_realistic_maritime(self):
        adapter = MaritimeAdapter()
        tiles = adapter.ground_truth()
        assert len(tiles) >= 1
        # Types should be maritime-relevant
        types = {t.tile_type for t in tiles}
        assert types & {TileType.COMMAND, TileType.VISION}

    def test_on_snap_sets_metadata(self):
        adapter = MaritimeAdapter()
        tile = _tile(confidence=1.0)
        adapter.on_snap(tile)
        assert tile.metadata.get("buyer_report_pending") is True


# =====================================================================
# RetailAdapter
# =====================================================================

class TestRetailAdapter:

    def test_verify_checks_shelf_vs_register(self):
        adapter = RetailAdapter(
            shelf_audit={"SKU001": 42},
        )
        # Tile matching shelf audit
        good = _tile(
            input_pattern="count sku SKU001",
            output_action="42",
            tile_type=TileType.COMMAND,
        )
        # Tile with no matching ground truth
        bad = _tile(input_pattern="nonexistent", output_action="0")
        results = adapter.verify([good, bad])
        assert results[0].passed is True
        assert results[1].passed is False

    def test_ground_truth_returns_retail_tiles(self):
        adapter = RetailAdapter(shelf_audit={"SKU001": 42})
        tiles = adapter.ground_truth()
        assert len(tiles) >= 1
        assert all(isinstance(t, Tile) for t in tiles)


# =====================================================================
# HealthcareAdapter
# =====================================================================

class TestHealthcareAdapter:

    def test_verify_outcome_vs_prediction(self):
        adapter = HealthcareAdapter(
            outcomes={"flu": {"treatment": "antiviral", "improved": True}},
        )
        good = _tile(
            input_pattern="diagnosis flu",
            output_action="antiviral",
            tile_type=TileType.RESPONSE,
        )
        results = adapter.verify([good])
        assert results[0].passed is True

    def test_ground_truth_clinical_tiles(self):
        adapter = HealthcareAdapter(outcomes={"flu": {"treatment": "antiviral"}})
        tiles = adapter.ground_truth()
        assert len(tiles) >= 1
        assert all(isinstance(t, Tile) for t in tiles)


# =====================================================================
# WebAdapter
# =====================================================================

class TestWebAdapter:

    def test_verify_conversion_vs_prediction(self):
        adapter = WebAdapter(
            conversion_log={"/landing": {"best_variant": "variant_b", "rate": 0.12, "n": 5000}},
        )
        good = _tile(
            input_pattern="optimise /landing",
            output_action="variant_b",
            tile_type=TileType.COMMAND,
        )
        bad = _tile(input_pattern="nonexistent", output_action="control")
        results = adapter.verify([good, bad])
        assert results[0].passed is True
        assert results[1].passed is False

    def test_ground_truth_conversion_tiles(self):
        adapter = WebAdapter(conversion_log={"/landing": {"best_variant": "control", "rate": 0.05, "n": 1000}})
        tiles = adapter.ground_truth()
        assert len(tiles) >= 1
        assert all(isinstance(t, Tile) for t in tiles)
