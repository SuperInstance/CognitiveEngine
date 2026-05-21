"""Router — decide compiled tile or model inference.

The router is the gatekeeper. Every input comes here first.
If a compiled tile matches, it's free (zero tokens).
If not, the fallback model runs (costs tokens).
Every fallback interaction is logged as a potential future tile.

Priority:
1. Compiled commands (regex match, zero inference)
2. Negative constraints (known-bad patterns)
3. Fuzzy match on existing tiles
4. Fallback model (costs tokens, creates training data)
"""

__all__ = ["RouteDecision", "Router"]


from enum import Enum
from typing import Optional, Callable
from .tiles import TileStore, Tile, TileType
from .compiler import RigidFinder


class RouteDecision(Enum):
    COMPILED = "compiled"
    FALLBACK = "fallback"
    AMBIGUOUS = "ambiguous"
    NEGATIVE = "negative"


class Router:
    def __init__(self, store: TileStore, finder: RigidFinder,
                 fallback_fn: Optional[Callable] = None):
        self.store = store
        self.finder = finder
        self.fallback_fn = fallback_fn
        self._pending: list[dict] = []

    def route(self, text: str) -> tuple[RouteDecision, Optional[dict]]:
        # 1. Compiled commands
        compiled_result = self.finder.match(text)
        if compiled_result is not None:
            return (RouteDecision.COMPILED, compiled_result)

        # 2. Negative constraints
        for tile in self.store:
            if tile.tile_type == TileType.NEGATIVE:
                if tile.input_pattern and tile.input_pattern in text.lower():
                    return (RouteDecision.NEGATIVE, {
                        "action": "BLOCKED",
                        "reason": tile.output_action,
                        "tile_id": tile.tile_id,
                    })

        # 3. Fuzzy match
        existing = self.store.find_by_pattern(text)
        if existing:
            best = existing[0]
            if best.confidence >= 0.7:
                best.record_use(True)
                return (RouteDecision.COMPILED, {
                    "action": best.output_action,
                    "confidence": best.confidence,
                    "tile_id": best.tile_id,
                })
            elif best.confidence >= 0.5:
                return (RouteDecision.AMBIGUOUS, {
                    "action": best.output_action,
                    "confidence": best.confidence,
                    "tile_id": best.tile_id,
                    "message": "Partial match — please confirm",
                })

        # 4. Fallback
        if self.fallback_fn:
            result = self.fallback_fn(text)
            self._pending.append({
                "input": text,
                "output": result,
                "confidence": 0.0,
            })
            return (RouteDecision.FALLBACK, result)

        return (RouteDecision.FALLBACK, {"action": "UNKNOWN", "input": text})

    def __repr__(self) -> str:
        return f"Router(tiles={len(self.store)}, compiled={self.finder.compiled_count}, pending={self.pending_count})"

    def confirm_pending(self, index: int, correct: bool,
                        correction: str = "") -> Optional[str]:
        """Confirm or correct a pending fallback result.

        Args:
            index: 0-based index into the pending list. Negative indices
                are rejected. Raises IndexError if out of range.
            correct: True if the fallback result was correct.
            correction: Replacement action if correct=False.

        Returns:
            tile_id of the newly created tile, or None if index was invalid.
        """
        if not isinstance(index, int) or index < 0 or index >= len(self._pending):
            return None
        pending = self._pending.pop(index)
        tile_type = TileType.COMMAND if correct else TileType.CORRECTION
        tile = Tile(
            tile_type=tile_type,
            input_pattern=pending["input"],
            output_action=correction or str(pending["output"]),
            confidence=0.9 if correct else 0.8,
            source="captain",
        )
        return self.store.add(tile)

    def log_pending(self, text: str, result, confidence: float = 0.0) -> None:
        """Log a fallback interaction as a potential future tile."""
        self._pending.append({
            "input": text,
            "output": result,
            "confidence": confidence,
        })

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def stats(self) -> dict:
        compiled = self.finder.compiled_count
        total = len(self.store)
        return {
            "compiled_tiles": compiled,
            "total_tiles": total,
            "pending_reviews": self.pending_count,
            "coverage": compiled / max(1, total),
        }
