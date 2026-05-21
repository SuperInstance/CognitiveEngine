"""Tests for the domain adapter system (luciddreamer.domain)."""

import logging

import pytest

from luciddreamer.domain import (
    DomainAdapter,
    MaritimeAdapter,
    RetailAdapter,
    HealthcareAdapter,
    WebAdapter,
    VerificationResult,
    RoomChain,
)
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

    def test_on_snap_called_when_tile_crosses_threshold(self, caplog):
        adapter = MaritimeAdapter()
        tile = _tile(confidence=0.98)
        with caplog.at_level(logging.INFO, logger="luciddreamer.domain"):
            adapter.on_snap(tile)
        assert any("snap" in r.message.lower() for r in caplog.records)

    def test_create_room_chain_returns_soft_hard(self):
        adapter = MaritimeAdapter()
        chain = adapter.create_room_chain()
        assert isinstance(chain, RoomChain)
        assert isinstance(chain.soft, SoftRoom)
        assert isinstance(chain.hard, HardRoom)


# =====================================================================
# MaritimeAdapter
# =====================================================================

class TestMaritimeAdapter:

    def test_verify_catches_mismatch(self):
        adapter = MaritimeAdapter()
        # Low-confidence tile should fail verification
        low = _tile(confidence=0.2)
        results = adapter.verify([low])
        assert len(results) == 1
        assert results[0].passed is False
        assert "threshold" in results[0].detail.lower() or "below" in results[0].detail.lower()

    def test_verify_passes_good_tile(self):
        adapter = MaritimeAdapter()
        good = _tile(confidence=0.9)
        results = adapter.verify([good])
        assert results[0].passed is True

    def test_ground_truth_realistic_maritime(self):
        adapter = MaritimeAdapter()
        tiles = adapter.ground_truth()
        assert len(tiles) >= 1
        # Should contain vessel-tagged tiles
        assert any(t.vessel for t in tiles)
        # Types should be maritime-relevant
        types = {t.tile_type for t in tiles}
        assert types & {TileType.COMMAND, TileType.VISION}

    def test_on_snap_logs(self, caplog):
        adapter = MaritimeAdapter()
        tile = _tile(confidence=1.0)
        with caplog.at_level(logging.INFO, logger="luciddreamer.domain"):
            adapter.on_snap(tile)
        assert "maritime snap" in caplog.text


# =====================================================================
# RetailAdapter
# =====================================================================

class TestRetailAdapter:

    def test_verify_checks_shelf_vs_register(self):
        adapter = RetailAdapter()
        good = _tile(confidence=0.9)
        bad = _tile(confidence=0.1)
        results = adapter.verify([good, bad])
        assert results[0].passed is True
        assert results[1].passed is False

    def test_ground_truth_returns_retail_tiles(self):
        adapter = RetailAdapter()
        tiles = adapter.ground_truth()
        assert len(tiles) >= 1
        assert all(isinstance(t, Tile) for t in tiles)


# =====================================================================
# HealthcareAdapter
# =====================================================================

class TestHealthcareAdapter:

    def test_verify_outcome_vs_prediction(self):
        adapter = HealthcareAdapter()
        good = _tile(confidence=0.8)
        results = adapter.verify([good])
        assert results[0].passed is True

    def test_ground_truth_clinical_tiles(self):
        adapter = HealthcareAdapter()
        tiles = adapter.ground_truth()
        assert len(tiles) >= 1
        assert all(isinstance(t, Tile) for t in tiles)


# =====================================================================
# WebAdapter
# =====================================================================

class TestWebAdapter:

    def test_verify_conversion_vs_prediction(self):
        adapter = WebAdapter()
        good = _tile(confidence=0.7)
        bad = _tile(confidence=0.1)
        results = adapter.verify([good, bad])
        assert results[0].passed is True
        assert results[1].passed is False

    def test_ground_truth_conversion_tiles(self):
        adapter = WebAdapter()
        tiles = adapter.ground_truth()
        assert len(tiles) >= 1
        assert all(isinstance(t, Tile) for t in tiles)
