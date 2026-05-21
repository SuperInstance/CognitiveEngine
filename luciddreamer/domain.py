"""Domain adapters — bridge between vertical-domain logic and the tile system.

Each adapter knows how to:
- verify()   — compare tile output against ground-truth from the domain
- ground_truth() — produce canonical Tile lists for the domain
- on_snap()  — react when a tile crosses the 97.5 % compile threshold
- create_room_chain() — build a SoftRoom → HardRoom pipeline for the domain
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from .tiles import Tile, TileType, Verifier
from .rooms import SoftRoom, HardRoom

logger = logging.getLogger(__name__)

# ── helpers ──────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    """Outcome of comparing a tile against domain ground-truth."""
    tile_id: str
    passed: bool
    detail: str = ""


@dataclass
class RoomChain:
    """A soft → hard room pipeline for a domain."""
    soft: SoftRoom
    hard: HardRoom

# ── abstract base ────────────────────────────────────────────────────

class DomainAdapter(ABC):
    """ABC for vertical-domain adapters."""

    @abstractmethod
    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        """Compare *tiles* against domain ground-truth."""

    @abstractmethod
    def ground_truth(self) -> list[Tile]:
        """Return canonical tiles for this domain."""

    @abstractmethod
    def on_snap(self, tile: Tile) -> None:
        """Called when a tile crosses the 97.5 % compile threshold."""

    @abstractmethod
    def create_room_chain(self, name: str = "domain") -> RoomChain:
        """Build a SoftRoom → HardRoom pipeline for this domain."""

# ── concrete adapters ────────────────────────────────────────────────

class MaritimeAdapter(DomainAdapter):
    """Maritime / fisheries domain adapter."""

    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for tile in tiles:
            # Stub: in production, compare tile output against buyer reconciliation
            passed = tile.confidence >= 0.5
            results.append(VerificationResult(
                tile_id=tile.tile_id,
                passed=passed,
                detail="ok" if passed else "confidence below threshold",
            ))
        return results

    def ground_truth(self) -> list[Tile]:
        return [
            Tile(
                tile_type=TileType.COMMAND,
                input_pattern="haul back",
                output_action="WINCH_HAUL_BACK",
                confidence=1.0,
                verifier=Verifier.CAPTAIN,
                vessel="f/v-example",
            ),
            Tile(
                tile_type=TileType.VISION,
                input_pattern="pollock",
                output_action="SORT_POLLOCK",
                confidence=0.95,
                verifier=Verifier.DECK_CREW,
                vessel="f/v-example",
            ),
        ]

    def on_snap(self, tile: Tile) -> None:
        logger.info("maritime snap: tile=%s confidence=%.2f", tile.tile_id, tile.confidence)

    def create_room_chain(self, name: str = "maritime") -> RoomChain:
        soft = SoftRoom(name=f"{name}-soft")
        hard = HardRoom(name=f"{name}-hard")
        return RoomChain(soft=soft, hard=hard)


class RetailAdapter(DomainAdapter):
    """Retail / shelf-audit domain adapter."""

    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for tile in tiles:
            passed = tile.confidence >= 0.5
            results.append(VerificationResult(
                tile_id=tile.tile_id,
                passed=passed,
                detail="shelf match" if passed else "register mismatch",
            ))
        return results

    def ground_truth(self) -> list[Tile]:
        return [
            Tile(
                tile_type=TileType.COMMAND,
                input_pattern="restock aisle 3",
                output_action="RESTOCK",
                confidence=1.0,
                verifier=Verifier.SIMULATION,
            ),
        ]

    def on_snap(self, tile: Tile) -> None:
        logger.info("retail snap: tile=%s", tile.tile_id)

    def create_room_chain(self, name: str = "retail") -> RoomChain:
        return RoomChain(soft=SoftRoom(name=f"{name}-soft"), hard=HardRoom(name=f"{name}-hard"))


class HealthcareAdapter(DomainAdapter):
    """Healthcare / clinical-outcome domain adapter."""

    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for tile in tiles:
            passed = tile.confidence >= 0.5
            results.append(VerificationResult(
                tile_id=tile.tile_id,
                passed=passed,
                detail="outcome matches" if passed else "prediction mismatch",
            ))
        return results

    def ground_truth(self) -> list[Tile]:
        return [
            Tile(
                tile_type=TileType.COMMAND,
                input_pattern="administer aspirin",
                output_action="MEDICATION",
                confidence=1.0,
                verifier=Verifier.CAPTAIN,
            ),
        ]

    def on_snap(self, tile: Tile) -> None:
        logger.info("healthcare snap: tile=%s", tile.tile_id)

    def create_room_chain(self, name: str = "healthcare") -> RoomChain:
        return RoomChain(soft=SoftRoom(name=f"{name}-soft"), hard=HardRoom(name=f"{name}-hard"))


class WebAdapter(DomainAdapter):
    """Web / conversion-tracking domain adapter."""

    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        results: list[VerificationResult] = []
        for tile in tiles:
            passed = tile.confidence >= 0.5
            results.append(VerificationResult(
                tile_id=tile.tile_id,
                passed=passed,
                detail="conversion match" if passed else "log mismatch",
            ))
        return results

    def ground_truth(self) -> list[Tile]:
        return [
            Tile(
                tile_type=TileType.COMMAND,
                input_pattern="checkout complete",
                output_action="CONVERSION",
                confidence=1.0,
                verifier=Verifier.SIMULATION,
            ),
        ]

    def on_snap(self, tile: Tile) -> None:
        logger.info("web snap: tile=%s", tile.tile_id)

    def create_room_chain(self, name: str = "web") -> RoomChain:
        return RoomChain(soft=SoftRoom(name=f"{name}-soft"), hard=HardRoom(name=f"{name}-hard"))
