"""Pre-configured room types: SoftRoom and HardRoom.

SoftRoom  (dial locked at 1.0)
    Every signal is admitted.  The threshold is zero.  Low-confidence
    inferences accumulate via the EpsilonAccumulator and auto-compile
    when their running confidence crosses the compile threshold (97.5 %).

HardRoom  (dial locked at 0.0)
    Only snaps — fully compiled, confidence == 1.0 tiles — pass through.
    Inferences are rejected.  Fallback is disabled.  The room cannot be
    fooled.
"""

from __future__ import annotations

from typing import Optional, Callable, Any

from .signal_chain import SignalChainRoom, EpsilonAccumulator
from .tiles import Tile, TileType, TileStore
from .compiler import RigidFinder
from .router import Router, RouteDecision


class SoftRoom(SignalChainRoom):
    """A room that admits everything and trusts the cascade to verify.

    * Dial is locked at 1.0 (pure inference / soft).
    * Every tile is admitted regardless of confidence.
    * An EpsilonAccumulator tracks running confidence on each input
      pattern.  When the accumulated confidence reaches the compile
      threshold (0.975 by default), the tile is auto-compiled into a
      snap (confidence set to 1.0).
    * Fallback is always permitted (dial ≥ fallback_threshold).
    """

    FIXED_DIAL: float = 1.0

    def __init__(
        self,
        name: str = "soft",
        anchor: Optional[dict] = None,
        fallback_fn: Optional[Callable[[str], Any]] = None,
        compile_threshold: float = 0.975,
        epsilon: float = 0.01,
        **kwargs,
    ):
        store = kwargs.pop("store", TileStore())
        super().__init__(
            name=name,
            dial=self.FIXED_DIAL,
            anchor=anchor or {},
            store=store,
            fallback_fn=fallback_fn,
            fallback_threshold=0.3,
            **kwargs,
        )
        self.compile_threshold = compile_threshold
        self._accumulator = EpsilonAccumulator(epsilon=epsilon)

    # ------------------------------------------------------------------
    # Lock the dial
    # ------------------------------------------------------------------
    def set_dial(self, value: float) -> None:
        """SoftRoom dial is fixed at 1.0 — setting it is a no-op."""
        # Intentionally ignored; dial stays at FIXED_DIAL.

    # ------------------------------------------------------------------
    # Admit — everything passes
    # ------------------------------------------------------------------
    def admit(self, tile: Tile) -> Tile:
        """Admit *tile* unconditionally and accumulate epsilon.

        If the running confidence for the tile's input pattern crosses
        the compile threshold, the tile is auto-compiled into a snap.
        """
        self.store.add(tile)

        # Accumulate toward compilation
        delta = self._accumulator.update(tile.confidence)
        if delta is not None and delta >= self.compile_threshold:
            tile.confidence = 1.0  # auto-compile → snap
        return tile

    # ------------------------------------------------------------------
    # Override route to always allow fallback
    # ------------------------------------------------------------------
    def route(self, text: str) -> tuple[RouteDecision, Optional[dict]]:
        """Route with full softness — fallback always available."""
        decision, payload = super().route(text)
        # If base class rejected fallback, re-enable it
        if decision == RouteDecision.FALLBACK and isinstance(payload, dict):
            if payload.get("action") == "UNKNOWN" and self.fallback_fn is not None:
                result = self.fallback_fn(text)
                return (RouteDecision.FALLBACK, result)
        return decision, payload


class HardRoom(SignalChainRoom):
    """A room that only admits snaps — fully proven, compiled tiles.

    * Dial is locked at 0.0 (fully hard).
    * Only tiles with confidence == 1.0 are admitted.
    * Inferences are rejected outright.
    * Fallback is disabled (dial < fallback_threshold).
    * The room cannot be fooled.
    """

    FIXED_DIAL: float = 0.0

    def __init__(
        self,
        name: str = "hard",
        anchor: Optional[dict] = None,
        **kwargs,
    ):
        store = kwargs.pop("store", TileStore())
        super().__init__(
            name=name,
            dial=self.FIXED_DIAL,
            anchor=anchor or {},
            store=store,
            fallback_fn=None,       # no fallback ever
            fallback_threshold=1.1, # unreachable
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Lock the dial
    # ------------------------------------------------------------------
    def set_dial(self, value: float) -> None:
        """HardRoom dial is fixed at 0.0 — setting it is a no-op."""
        # Intentionally ignored; dial stays at FIXED_DIAL.

    # ------------------------------------------------------------------
    # Admit — only snaps
    # ------------------------------------------------------------------
    def admit(self, tile: Tile) -> Optional[Tile]:
        """Admit *tile* only if it is a snap (confidence == 1.0).

        Returns the tile if admitted, None if rejected.
        """
        if tile.confidence >= 1.0:
            self.store.add(tile)
            return tile
        return None

    # ------------------------------------------------------------------
    # Override route to block inferences
    # ------------------------------------------------------------------
    def route(self, text: str) -> tuple[RouteDecision, Optional[dict]]:
        """Route with maximum hardness — only compiled commands match."""
        # Only compiled matches are considered
        compiled_result = self.finder.match(text)
        if compiled_result is not None:
            return (RouteDecision.COMPILED, compiled_result)

        # Negative constraints
        for tile in self.store:
            if tile.tile_type == TileType.NEGATIVE:
                if tile.input_pattern and tile.input_pattern in text.lower():
                    return (RouteDecision.NEGATIVE, {
                        "action": "BLOCKED",
                        "reason": tile.output_action,
                        "tile_id": tile.tile_id,
                    })

        # Nothing else passes — no fuzzy, no fallback
        return (RouteDecision.FALLBACK, {
            "action": "REJECTED",
            "input": text,
            "dial": self.dial,
            "reason": "hard room: no compiled match and fallback disabled",
        })
