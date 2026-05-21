"""SignalRouter — bridge between SignalChainRoom and Router.

The Router (from router.py) routes queries against a TileStore with a
RigidFinder.  The SignalChainRoom (from signal_chain.py) wraps a TileStore
plus a tunable dial that gates which tiles are active at a given position.

SignalRouter bridges the two: it uses the room's dial position to control
routing priority, so that a low dial (hard) prefers compiled tiles and
rejects low-confidence matches, while a high dial (soft) accepts all tiles
and gives the fallback model more weight.

Usage::

    from luciddreamer.signal_router import SignalRouter

    room = SignalChainRoom(name="main", dial=0.5)
    sr = SignalRouter(room, fallback_model=my_llm)
    decision, payload = sr.route("what's the weather?")
    sr.set_dial(0.2)  # go harder
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Optional

from .router import RouteDecision
from .signal_chain import SignalChainRoom
from .tiles import Tile


class SignalRouter:
    """Bridge between SignalChainRoom (dial-aware tile storage) and Router
    (priority routing).

    Uses the room's dial position to control routing priority:

    - **Low dial (hard):** prefer compiled tiles, reject low-confidence
      matches, block fallback unless dial is very high.
    - **High dial (soft):** accept all tiles including ambiguous ones, allow
      fallback model to run freely.

    Thread-safe: all mutations are guarded by an internal lock.
    """

    def __init__(
        self,
        room: SignalChainRoom,
        fallback_model: Optional[Callable[[str], Any]] = None,
    ) -> None:
        self._room = room
        self._fallback_model = fallback_model
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Core routing
    # ------------------------------------------------------------------
    def route(
        self,
        query: str,
        dial: Optional[float] = None,
    ) -> tuple[RouteDecision, Optional[dict]]:
        """Route *query* through the room at the given dial position.

        Procedure:

        1. Optionally move the dial to *dial* (if provided).
        2. Ask the room for tiles valid at the current dial position.
        3. Pick the best match among valid tiles.
        4. If match confidence >= snap threshold → **compiled** route.
        5. If match confidence > 0 → **fuzzy** (ambiguous) route.
        6. If no match → **fallback** to model.

        Args:
            query: The text to route.
            dial: Optional override for the room's dial position.  When
                ``None`` the room's current dial is used unchanged.

        Returns:
            A ``(RouteDecision, payload)`` tuple following the same
            convention as :class:`Router` and :class:`SignalChainRoom`.
        """
        with self._lock:
            if dial is not None:
                self._room.set_dial(dial)

            return self._room.route(query)

    # ------------------------------------------------------------------
    # Dial control
    # ------------------------------------------------------------------
    def set_dial(self, position: float) -> None:
        """Update the room's dial position (clamped to [0.0, 1.0]).

        Args:
            position: 0.0 = fully hard, 1.0 = fully soft.
        """
        with self._lock:
            self._room.set_dial(position)

    @property
    def dial(self) -> float:
        """Current dial position of the underlying room."""
        return self._room.dial

    # ------------------------------------------------------------------
    # Tile access
    # ------------------------------------------------------------------
    @property
    def available_tiles(self) -> list[Tile]:
        """Tiles available at the current dial position.

        Returns every tile in the room's store whose ``dial_position``
        is within the current dial setting.
        """
        with self._lock:
            current_dial = self._room.dial
            return [t for t in self._room.store if t.matches_dial(current_dial)]

    # ------------------------------------------------------------------
    # Delegated convenience
    # ------------------------------------------------------------------
    @property
    def room(self) -> SignalChainRoom:
        """The underlying :class:`SignalChainRoom`."""
        return self._room

    @property
    def stats(self) -> dict:
        """Aggregated stats from the room plus bridge-level metadata."""
        with self._lock:
            room_stats = self._room.stats
        return {
            **room_stats,
            "bridge": "SignalRouter",
            "available_tiles": len(self.available_tiles),
        }

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"SignalRouter(room={self._room.name!r}, "
            f"dial={self._room.dial:.2f}, "
            f"tiles={len(self._room.store)}, "
            f"available={len(self.available_tiles)})"
        )
