"""Signal-chain integration for LucidDreamer.

Maps signal-chain primitives (Dial, Room, Snap, Inference) onto
LucidDreamer's Tile/TileStore/Router/RigidFinder.

Concept mapping
---------------
- Dial (0.0 hard → 1.0 soft)
    ↔ Tile confidence threshold + fallback gating in the room.
- Room (spatial/temporal anchor with snaps + inferences)
    ↔ SignalChainRoom wraps a TileStore, adds a dial, an anchor dict,
      and a parent/child chain.
- Snap (hard binding)
    ↔ Tile with confidence >= 1.0 (fully compiled).
- Inference (soft prediction)
    ↔ Tile with confidence < compile threshold, or a fallback model result.

Every room has a dial. The dial controls model vs code.
Tune the chain like a synth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Callable, Any
import re
import time

from .tiles import Tile, TileStore, TileType
from .router import Router, RouteDecision
from .compiler import RigidFinder


@dataclass
class SignalChainRoom:
    """A room in the signal chain — a TileStore with a tunable dial.

    Dial semantics
    --------------
    0.0  hard   → only compiled tiles, zero inference, fallback blocked.
    0.25 firm   → verified tiles allowed (confidence ≥ 0.9).
    0.5  mixed  → tentative tiles allowed (confidence ≥ 0.7).
    0.75 soft   → ambiguous tiles allowed (confidence ≥ 0.5).
    1.0  soft   → full model fallback permitted.

    Rooms chain together.  Snaps (high-confidence tiles) cascade down to
    children so that hard bindings from parent rooms remain in effect.
    """
    name: str
    dial: float = 0.5
    anchor: dict = field(default_factory=dict)
    store: TileStore = field(default_factory=TileStore)
    fallback_fn: Optional[Callable[[str], Any]] = None
    fallback_threshold: float = 0.3
    parent: Optional[SignalChainRoom] = None
    children: list[SignalChainRoom] = field(default_factory=list)

    # Internal machinery created in __post_init__
    finder: RigidFinder = field(default=None, repr=False)
    router: Router = field(default=None, repr=False)

    def __post_init__(self):
        if self.finder is None:
            self.finder = RigidFinder(self.store)
        if self.router is None:
            self.router = Router(self.store, self.finder, self.fallback_fn)

    # ------------------------------------------------------------------
    # Snap / inference views
    # ------------------------------------------------------------------
    @property
    def snaps(self) -> list[Tile]:
        """Hard bindings — tiles that are fully compiled (confidence == 1.0)."""
        return [t for t in self.store if t.confidence >= 1.0]

    @property
    def inferences(self) -> list[Tile]:
        """Soft predictions — tiles below the compile threshold."""
        return [t for t in self.store
                if t.confidence < self.finder.COMPILE_THRESHOLD]

    # ------------------------------------------------------------------
    # Dial helpers
    # ------------------------------------------------------------------
    def _confidence_threshold(self) -> float:
        """Minimum tile confidence required at the current dial position."""
        return max(0.0, 1.0 - self.dial)

    def set_dial(self, value: float) -> None:
        """Set the dial with clamping to [0.0, 1.0]."""
        self.dial = max(0.0, min(1.0, float(value)))

    # ------------------------------------------------------------------
    # Inherited snaps (runtime ancestor chain)
    # ------------------------------------------------------------------
    def _inherited_snaps(self) -> list[Tile]:
        """Collect snaps from all ancestor rooms."""
        inherited: list[Tile] = []
        room = self.parent
        while room is not None:
            inherited.extend(room.snaps)
            room = room.parent
        return inherited

    # ------------------------------------------------------------------
    # Dial-aware querying
    # ------------------------------------------------------------------
    def find_at_dial(self, pattern: str) -> list[Tile]:
        """Find tiles matching *pattern* that are active at the current dial.

        Includes tiles from this room plus inherited snaps from ancestors.
        Results are sorted by confidence descending.
        """
        candidates: list[Tile] = []

        # Local matches via TileStore (handles literal + regex)
        candidates.extend(self.store.find_by_pattern(pattern))

        # Inherited snaps from ancestor rooms
        for snap in self._inherited_snaps():
            if snap.input_pattern == pattern:
                candidates.append(snap)
            elif hasattr(snap, "regex_pattern") and snap.regex_pattern:
                try:
                    if re.match(snap.regex_pattern, pattern, re.IGNORECASE):
                        candidates.append(snap)
                except re.error:
                    pass

        # Filter by dial position
        dial = self.dial
        active = [t for t in candidates if t.matches_dial(dial)]

        # Sort by confidence descending
        return sorted(active, key=lambda t: t.confidence, reverse=True)

    # ------------------------------------------------------------------
    # Routing — dial-aware priority
    # ------------------------------------------------------------------
    def route(self, text: str) -> tuple[RouteDecision, Optional[dict]]:
        """Route *text* through this room with dial-aware priority.

        Priority:
        1. Compiled commands   (zero inference)
        2. Negative constraints
        3. Dial-aware fuzzy match on existing tiles
        4. Fallback model      (gated by dial >= fallback_threshold)
        """
        # 1. Compiled commands — always checked first
        compiled_result = self.finder.match(text)
        if compiled_result is not None:
            return (RouteDecision.COMPILED, compiled_result)

        # 2. Negative constraints — always checked second
        for tile in self.store:
            if tile.tile_type == TileType.NEGATIVE:
                if tile.input_pattern and tile.input_pattern in text.lower():
                    return (RouteDecision.NEGATIVE, {
                        "action": "BLOCKED",
                        "reason": tile.output_action,
                        "tile_id": tile.tile_id,
                    })

        # 3. Dial-aware fuzzy match
        threshold = self._confidence_threshold()
        existing = self.find_at_dial(text)
        if existing:
            best = existing[0]
            if best.confidence >= max(0.7, threshold):
                best.record_use(True)
                return (RouteDecision.COMPILED, {
                    "action": best.output_action,
                    "confidence": best.confidence,
                    "tile_id": best.tile_id,
                })
            elif best.confidence >= max(0.5, threshold):
                return (RouteDecision.AMBIGUOUS, {
                    "action": best.output_action,
                    "confidence": best.confidence,
                    "tile_id": best.tile_id,
                    "message": "Partial match — please confirm",
                })

        # 4. Fallback — only if dial permits soft inference
        if self.dial >= self.fallback_threshold and self.fallback_fn is not None:
            result = self.fallback_fn(text)
            # Mirror Router's pending-logging behaviour
            self.router.log_pending(text, result)
            return (RouteDecision.FALLBACK, result)

        return (RouteDecision.FALLBACK, {
            "action": "UNKNOWN",
            "input": text,
            "dial": self.dial,
            "reason": "no match and fallback disabled by dial",
        })

    # ------------------------------------------------------------------
    # Snap propagation (cascade through children)
    # ------------------------------------------------------------------
    def propagate_snaps(self) -> None:
        """Push snaps down to all children, cascading recursively.

        Each child receives a copy of every snap it does not already have.
        After propagation a child's own store contains its inherited hard
        bindings, so queries remain fast and do not need to walk the
        ancestor chain at runtime.
        """
        for child in self.children:
            for snap in self.snaps:
                if child.store.get(snap.tile_id) is None:
                    child.store.add(snap)
            # Recurse so grandchildren receive snaps too
            child.propagate_snaps()

    def add_child(self, room: SignalChainRoom) -> SignalChainRoom:
        """Wire *room* in as a child of this room."""
        room.parent = self
        if room not in self.children:
            self.children.append(room)
        return room

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def stats(self) -> dict:
        """Room statistics."""
        return {
            "name": self.name,
            "dial": self.dial,
            "tiles": len(self.store),
            "snaps": len(self.snaps),
            "inferences": len(self.inferences),
            "children": len(self.children),
            "coverage": self.finder.coverage,
            "confidence_threshold": self._confidence_threshold(),
        }

    def __repr__(self) -> str:
        return (f"SignalChainRoom({self.name!r}, dial={self.dial:.2f}, "
                f"tiles={len(self.store)}, children={len(self.children)})")


class EpsilonAccumulator:
    """Accumulates a stream of values and only reports changes that exceed epsilon.

    Useful for dial smoothing: you do not want to recompile or trigger
    side-effects on every microscopic confidence tick.  Only act when the
    delta is meaningful.
    """

    def __init__(self, epsilon: float = 0.01, initial: float = 0.0):
        self.epsilon = float(epsilon)
        self._last = float(initial)

    def update(self, value: float) -> Optional[float]:
        """Return *value* if it differs from the last reported value by at
        least *epsilon*, otherwise return None."""
        if abs(value - self._last) >= self.epsilon:
            self._last = float(value)
            return self._last
        return None

    @property
    def last(self) -> float:
        return self._last

    def reset(self, value: float = 0.0) -> None:
        self._last = float(value)


class RoomChain:
    """A linear chain of SignalChainRooms.

    Provides convenience methods for wiring rooms together, propagating
    snaps, and setting dials across the whole chain.
    """

    def __init__(self, rooms: Optional[list[SignalChainRoom]] = None):
        self.rooms: list[SignalChainRoom] = list(rooms) if rooms else []
        self._link_rooms()

    def _link_rooms(self) -> None:
        """Wire parent/child relationships between consecutive rooms."""
        for i in range(1, len(self.rooms)):
            self.rooms[i - 1].add_child(self.rooms[i])

    def add(self, room: SignalChainRoom) -> RoomChain:
        """Append *room* to the end of the chain."""
        if self.rooms:
            self.rooms[-1].add_child(room)
        self.rooms.append(room)
        return self

    def propagate_snaps(self) -> None:
        """Cascade snaps from each room down through its children."""
        for room in self.rooms:
            room.propagate_snaps()

    def set_dial(self, value: float) -> None:
        """Set every room's dial to *value*."""
        for room in self.rooms:
            room.set_dial(value)

    def route(self, text: str, start: int = 0) -> tuple[RouteDecision, Optional[dict]]:
        """Route *text* starting at room *start* (default 0, the first room).

        If the start room returns FALLBACK with an UNKNOWN action, the chain
        walks forward to the next room until a match is found or the chain
        ends.
        """
        for room in self.rooms[start:]:
            decision, payload = room.route(text)
            if decision != RouteDecision.FALLBACK:
                return decision, payload
            if isinstance(payload, dict) and payload.get("action") != "UNKNOWN":
                return decision, payload
        return RouteDecision.FALLBACK, {"action": "UNKNOWN", "input": text}

    def __len__(self) -> int:
        return len(self.rooms)

    def __iter__(self):
        return iter(self.rooms)

    def __getitem__(self, index: int) -> SignalChainRoom:
        return self.rooms[index]

    def __repr__(self) -> str:
        return f"RoomChain({len(self.rooms)} rooms)"
