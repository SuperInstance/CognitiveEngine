"""Domain adapter layer — plug any domain into the tile system.

The LucidDreamer architecture is domain-independent by design.  Tiles know
nothing about boats, shelves, patients, or web pages.  This module provides
the bridge: a ``DomainAdapter`` base class and concrete implementations for
four exemplar domains.

Every domain has three anchors:

1. **Ground truth source** — what counts as verified.
2. **Tile lifecycle** — how tiles are created, verified, compiled.
3. **Compiled vs. fresh competition** — compiled tiles compete with live
   inferences so that proven knowledge always wins.

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from .rooms import SoftRoom, HardRoom
from .signal_chain import SignalChainRoom, RoomChain
from .tiles import Tile, TileType, Verifier

__all__ = [
    "VerificationResult",
    "DomainAdapter",
    "MaritimeAdapter",
    "RetailAdapter",
    "HealthcareAdapter",
    "WebAdapter",
]


# ---------------------------------------------------------------------------
# Verification result
# ---------------------------------------------------------------------------

@dataclass
class VerificationResult:
    """Outcome of verifying a tile against domain ground truth.

    Attributes
    ----------
    tile_id:
        The SHA-256 id of the tile that was checked.
    passed:
        ``True`` when the tile agrees with ground truth.
    correction:
        The correct *output_action* if ``passed`` is ``False``.
    verifier:
        Who or what performed the verification.
    confidence_delta:
        Adjustment to apply to the tile's confidence (e.g. +0.15 for
        buyer match, -0.10 for mismatch).
    notes:
        Human-readable explanation of the result.
    """

    tile_id: str
    passed: bool
    correction: Optional[str] = None
    verifier: Verifier = Verifier.MODEL
    confidence_delta: float = 0.0
    notes: str = ""

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return (
            f"VerificationResult({self.tile_id[:8]}…, {status}, "
            f"delta={self.confidence_delta:+.2f})"
        )


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------

class DomainAdapter(ABC):
    """Base class for plugging any domain into the tile system.

    Concrete subclasses must implement the three abstract hooks that
    define domain-specific ground truth, verification, and snap handling.
    """

    # ------------------------------------------------------------------
    # Abstract hooks
    # ------------------------------------------------------------------

    @abstractmethod
    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        """Verify *tiles* against domain ground truth.

        Returns a :class:`VerificationResult` for every tile, marking
        mismatches and supplying corrections so the tile store can learn.
        """

    @abstractmethod
    def ground_truth(self) -> list[Tile]:
        """Load domain-specific ground truth as a list of fully-verified tiles.

        These tiles are treated as the gold standard against which live
        inferences are judged.  Confidence should be ``1.0`` and the
        verifier should reflect the authoritative source (e.g.
        ``Verifier.BUYER`` or ``Verifier.CAPTAIN``).
        """

    @abstractmethod
    def on_snap(self, tile: Tile) -> None:
        """Hook called when a tile *snaps* (crosses the 97.5 % compile threshold).

        Subclasses can use this to trigger domain-specific side effects:
        regenerate a buyer report, update an EHR record, publish a new
        conversion funnel, etc.
        """

    # ------------------------------------------------------------------
    # Default room-chain builder
    # ------------------------------------------------------------------

    def create_room_chain(self) -> RoomChain:
        """Build a domain-specific room chain.

        The default chain is **SoftRoom → SignalChainRoom → HardRoom**,
        mirroring the promotion ladder from inference to compilation.

        SoftRoom  (dial 1.0)
            Receives everything; low-confidence inferences accumulate.
        SignalChainRoom  (dial 0.5)
            The proving ground — tiles here are verified against ground
            truth before they are allowed to propagate.
        HardRoom  (dial 0.0)
            Only fully-compiled snaps live here.  Zero inference, zero
            approximation.
        """
        soft = SoftRoom(name="soft")
        mid = SignalChainRoom(name="verify", dial=0.5)
        hard = HardRoom(name="hard")
        return RoomChain([soft, mid, hard])

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# ---------------------------------------------------------------------------
# Maritime domain
# ---------------------------------------------------------------------------

class MaritimeAdapter(DomainAdapter):
    """Fishing / maritime domain.

    Ground truth comes from two authoritative sources:

    1. **Buyer reconciliation** — the dockside buyer's count and grade
       sheet is the final word on what was caught and how much it was
       worth.
    2. **Captain review** — the master of the vessel approves (or
       corrects) autopilot commands, chart queries, and sorting
       decisions.
    """

    def __init__(self, buyer_log: Optional[dict] = None) -> None:
        self.buyer_log = buyer_log or {}

    # -- ground truth --------------------------------------------------

    def ground_truth(self) -> list[Tile]:
        """Return buyer-reconciled catch records as gold-standard tiles."""
        truth: list[Tile] = []
        for species, data in self.buyer_log.items():
            truth.append(
                Tile(
                    tile_type=TileType.VISION,
                    input_pattern=f"sort {species}",
                    output_action=f"hold_{data.get('hold', 1)}",
                    confidence=1.0,
                    verifier=Verifier.BUYER,
                    metadata={
                        "species": species,
                        "weight_kg": data.get("weight", 0.0),
                        "grade": data.get("grade", "A"),
                        "price_per_lb": data.get("price", 0.0),
                    },
                )
            )
        # Captain-verified helm commands are also ground truth
        truth.append(
            Tile(
                tile_type=TileType.COMMAND,
                input_pattern="steady as she goes",
                output_action="helm_hold_course",
                confidence=1.0,
                verifier=Verifier.CAPTAIN,
            )
        )
        return truth

    # -- verify --------------------------------------------------------

    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        """Compare tiles against buyer log and captain commands.

        A fish-sorting tile that matches the buyer's species→hold
        mapping gets a strong positive delta.  A mismatch is flagged
        with the buyer's hold as the correction.
        """
        truth = {t.input_pattern: t for t in self.ground_truth()}
        results: list[VerificationResult] = []

        for tile in tiles:
            gold = truth.get(tile.input_pattern)
            if gold is None:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=False,
                        confidence_delta=-0.05,
                        notes="No ground-truth record for this input pattern.",
                    )
                )
                continue

            if tile.output_action == gold.output_action:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=True,
                        verifier=gold.verifier,
                        confidence_delta=+0.15,
                        notes=f"Matched {gold.verifier.value} ground truth.",
                    )
                )
            else:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=False,
                        correction=gold.output_action,
                        verifier=gold.verifier,
                        confidence_delta=-0.10,
                        notes=(
                            f"Expected '{gold.output_action}' "
                            f"per {gold.verifier.value} record."
                        ),
                    )
                )
        return results

    # -- snap hook -----------------------------------------------------

    def on_snap(self, tile: Tile) -> None:
        """When a maritime tile snaps, mark it for buyer-report regeneration."""
        tile.metadata["buyer_report_pending"] = True
        tile.metadata["snap_timestamp"] = tile.metadata.get("created_at", 0.0)


# ---------------------------------------------------------------------------
# Retail domain
# ---------------------------------------------------------------------------

class RetailAdapter(DomainAdapter):
    """Retail / inventory domain.

    Ground truth is the intersection of:

    1. **Shelf audit** — a human or robot physically counts what is on
       the shelf and records SKU + quantity.
    2. **Register reconciliation** — point-of-sale data proves what was
       actually sold and at what price.
    """

    def __init__(
        self,
        shelf_audit: Optional[dict] = None,
        register_receipts: Optional[list[dict]] = None,
    ) -> None:
        self.shelf_audit = shelf_audit or {}
        self.register_receipts = register_receipts or []

    # -- ground truth --------------------------------------------------

    def ground_truth(self) -> list[Tile]:
        """Return shelf-audit + register-reconciled SKU tiles."""
        truth: list[Tile] = []
        for sku, count in self.shelf_audit.items():
            truth.append(
                Tile(
                    tile_type=TileType.COMMAND,
                    input_pattern=f"count sku {sku}",
                    output_action=str(count),
                    confidence=1.0,
                    verifier=Verifier.DECK_CREW,  # nearest analogue: floor staff
                    metadata={"source": "shelf_audit", "sku": sku},
                )
            )
        # Register reconciliation: price charged is truth
        for receipt in self.register_receipts:
            sku = receipt.get("sku")
            if sku is None:
                continue
            truth.append(
                Tile(
                    tile_type=TileType.RESPONSE,
                    input_pattern=f"price sku {sku}",
                    output_action=str(receipt.get("price", 0.0)),
                    confidence=1.0,
                    verifier=Verifier.BUYER,  # nearest analogue: customer/payment
                    metadata={"source": "register", "sku": sku},
                )
            )
        return truth

    # -- verify --------------------------------------------------------

    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        """Check tile predictions against shelf count and register data.

        A restock command that matches the physical audit is promoted.
        A price lookup that disagrees with the register is corrected
        immediately (pricing errors are high-stakes in retail).
        """
        truth = {t.input_pattern: t for t in self.ground_truth()}
        results: list[VerificationResult] = []

        for tile in tiles:
            gold = truth.get(tile.input_pattern)
            if gold is None:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=False,
                        confidence_delta=-0.03,
                        notes="SKU not found in shelf audit or register.",
                    )
                )
                continue

            if tile.output_action == gold.output_action:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=True,
                        verifier=gold.verifier,
                        confidence_delta=+0.12,
                        notes="Matches physical audit / register record.",
                    )
                )
            else:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=False,
                        correction=gold.output_action,
                        verifier=gold.verifier,
                        confidence_delta=-0.10,
                        notes=(
                            f"Physical audit says {gold.output_action}; "
                            f"tile said {tile.output_action}."
                        ),
                    )
                )
        return results

    # -- snap hook -----------------------------------------------------

    def on_snap(self, tile: Tile) -> None:
        """When a retail tile snaps, queue a replenishment order if stock is low."""
        tile.metadata["auto_replenish"] = True
        tile.metadata["replenish_threshold"] = tile.metadata.get("min_stock", 5)


# ---------------------------------------------------------------------------
# Healthcare domain
# ---------------------------------------------------------------------------

class HealthcareAdapter(DomainAdapter):
    """Clinical / healthcare domain.

    Ground truth is derived from:

    1. **Outcome verification** — did the patient improve after the
       recommended intervention?  Labs, imaging, and vital signs tell
       the story.
    2. **Peer review** — a second clinician independently reviews the
       case and either concurs or offers a correction.
    """

    def __init__(
        self,
        outcomes: Optional[dict] = None,
        peer_reviews: Optional[dict] = None,
    ) -> None:
        self.outcomes = outcomes or {}
        self.peer_reviews = peer_reviews or {}

    # -- ground truth --------------------------------------------------

    def ground_truth(self) -> list[Tile]:
        """Return outcome-verified and peer-reviewed clinical tiles."""
        truth: list[Tile] = []
        for dx, outcome in self.outcomes.items():
            truth.append(
                Tile(
                    tile_type=TileType.RESPONSE,
                    input_pattern=f"diagnosis {dx}",
                    output_action=outcome.get("treatment", "observe"),
                    confidence=1.0,
                    verifier=Verifier.CAPTAIN,  # nearest analogue: attending
                    metadata={
                        "source": "outcome",
                        "improved": outcome.get("improved", False),
                        "follow_up_days": outcome.get("follow_up", 30),
                    },
                )
            )
        for dx, review in self.peer_reviews.items():
            truth.append(
                Tile(
                    tile_type=TileType.CORRECTION,
                    input_pattern=f"diagnosis {dx}",
                    output_action=review.get("corrected_treatment", "observe"),
                    confidence=1.0,
                    verifier=Verifier.DECK_CREW,  # nearest analogue: resident/peer
                    metadata={"source": "peer_review", "reviewer_id": review.get("id")},
                )
            )
        return truth

    # -- verify --------------------------------------------------------

    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        """Compare clinical tiles against outcome data and peer review.

        Because patient safety is paramount, a peer-review mismatch
        carries a larger penalty than other domains (-0.15 vs -0.10).
        """
        truth = {t.input_pattern: t for t in self.ground_truth()}
        results: list[VerificationResult] = []

        for tile in tiles:
            gold = truth.get(tile.input_pattern)
            if gold is None:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=False,
                        confidence_delta=-0.05,
                        notes="No outcome or peer-review record for this diagnosis.",
                    )
                )
                continue

            if tile.output_action == gold.output_action:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=True,
                        verifier=gold.verifier,
                        confidence_delta=+0.20,
                        notes=f"Concurs with {gold.verifier.value} ground truth.",
                    )
                )
            else:
                delta = -0.15 if gold.verifier == Verifier.DECK_CREW else -0.10
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=False,
                        correction=gold.output_action,
                        verifier=gold.verifier,
                        confidence_delta=delta,
                        notes=(
                            f"{gold.verifier.value} record recommends "
                            f"'{gold.output_action}' — patient safety check."
                        ),
                    )
                )
        return results

    # -- snap hook -----------------------------------------------------

    def on_snap(self, tile: Tile) -> None:
        """When a clinical tile snaps, lock it for protocol inclusion review."""
        tile.metadata["protocol_review"] = True
        tile.metadata["requires_attending_signoff"] = True


# ---------------------------------------------------------------------------
# Web domain
# ---------------------------------------------------------------------------

class WebAdapter(DomainAdapter):
    """Website optimisation domain.

    Ground truth comes from:

    1. **Conversion logs** — the actual click-through and purchase
       events that happened in production.
    2. **A/B test results** — statistically significant winner from
       controlled experiments.
    """

    def __init__(
        self,
        conversion_log: Optional[dict] = None,
        ab_tests: Optional[dict] = None,
    ) -> None:
        self.conversion_log = conversion_log or {}
        self.ab_tests = ab_tests or {}

    # -- ground truth --------------------------------------------------

    def ground_truth(self) -> list[Tile]:
        """Return conversion-log and A/B-test validated web tiles."""
        truth: list[Tile] = []
        for path, conv in self.conversion_log.items():
            truth.append(
                Tile(
                    tile_type=TileType.COMMAND,
                    input_pattern=f"optimise {path}",
                    output_action=conv.get("best_variant", "control"),
                    confidence=1.0,
                    verifier=Verifier.SIMULATION,  # A/B is a simulation of reality
                    metadata={
                        "source": "conversion_log",
                        "conversion_rate": conv.get("rate", 0.0),
                        "sample_size": conv.get("n", 0),
                    },
                )
            )
        for test_id, test in self.ab_tests.items():
            truth.append(
                Tile(
                    tile_type=TileType.RESPONSE,
                    input_pattern=f"ab_test {test_id}",
                    output_action=test.get("winner", "inconclusive"),
                    confidence=1.0,
                    verifier=Verifier.SIMULATION,
                    metadata={
                        "source": "ab_test",
                        "p_value": test.get("p_value", 1.0),
                        "uplift": test.get("uplift", 0.0),
                    },
                )
            )
        return truth

    # -- verify --------------------------------------------------------

    def verify(self, tiles: list[Tile]) -> list[VerificationResult]:
        """Compare optimisation tiles against conversion and A/B data.

        A tile proposing a page variant that lost an A/B test is
        heavily penalised (-0.10).  A tile matching the winner gets
        a modest boost (+0.10) because web traffic patterns drift
        faster than maritime or clinical truth.
        """
        truth = {t.input_pattern: t for t in self.ground_truth()}
        results: list[VerificationResult] = []

        for tile in tiles:
            gold = truth.get(tile.input_pattern)
            if gold is None:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=False,
                        confidence_delta=-0.02,
                        notes="No conversion log or A/B test for this path.",
                    )
                )
                continue

            if tile.output_action == gold.output_action:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=True,
                        verifier=gold.verifier,
                        confidence_delta=+0.10,
                        notes=f"Matches {gold.metadata.get('source')} winner.",
                    )
                )
            else:
                results.append(
                    VerificationResult(
                        tile_id=tile.tile_id,
                        passed=False,
                        correction=gold.output_action,
                        verifier=gold.verifier,
                        confidence_delta=-0.10,
                        notes=(
                            f"{gold.metadata.get('source')} winner was "
                            f"'{gold.output_action}'."
                        ),
                    )
                )
        return results

    # -- snap hook -----------------------------------------------------

    def on_snap(self, tile: Tile) -> None:
        """When a web tile snaps, mark it for CDN cache pre-warming."""
        tile.metadata["cdn_prewarm"] = True
        tile.metadata["invalidate_cache"] = tile.input_pattern
