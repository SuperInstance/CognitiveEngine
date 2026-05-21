"""Core tile system — every interaction creates a tile, every tile is a sounding line.

Tiles are the fundamental unit of the LucidDreamer system. Every command,
every classification, every chart query becomes a tile. Tiles can be verified,
corrected, generalized, and compiled into deterministic code.

Design principle: Zero-shot first. Every tile must work standalone — no
conversation context assumed. The tile's confidence and compiled regex
ARE the context.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import hashlib
import json
import re
import threading
import time


class DialMixin:
    """Mixin that gives tile-like objects a position on the hard→soft dial.

    The dial runs 0.0 (fully hard / compiled) → 1.0 (fully soft / model).
    By default dial_position is derived from confidence:
        dial_position = 1.0 - confidence
    Set *dial_override* to pin a tile to a specific position.
    """

    @property
    def dial_position(self) -> float:
        override = getattr(self, "dial_override", None)
        if override is not None:
            return float(override)
        return 1.0 - getattr(self, "confidence", 0.0)

    def matches_dial(self, dial: float) -> bool:
        """Return True if this tile is active at the given dial position."""
        return self.dial_position <= dial + 1e-9

    def effective_hardness(self) -> float:
        """How 'hard' this tile is — inverse of dial_position."""
        return 1.0 - self.dial_position


class TileType(Enum):
    """What kind of knowledge this tile represents."""
    COMMAND = "command"
    RESPONSE = "response"
    VISION = "vision"
    CHART = "chart"
    CORRECTION = "correction"
    NEGATIVE = "negative"
    ABSTRACTION = "abstraction"


class Confidence(Enum):
    """Confidence levels for tile matching.

    These map directly to the captain's interaction mode:
    - COMPILED: execute silently, respond with audio
    - VERIFIED: execute, confirm with "Roger"
    - TENTATIVE: execute tentatively, ask "Confirm?"
    - AMBIGUOUS: don't execute, ask captain to repeat
    - UNKNOWN: batch for review during transit
    """
    COMPILED = "compiled"         # 100% — deterministic, zero inference
    VERIFIED = "verified"         # 90-99% — execute + confirm
    TENTATIVE = "tentative"       # 70-90% — execute tentatively, ask
    AMBIGUOUS = "ambiguous"       # 50-70% — don't execute, ask captain
    UNKNOWN = "unknown"           # <50% — batch for review


class Verifier(Enum):
    """Who verified this tile's correctness."""
    MODEL = "model"
    CAPTAIN = "captain"
    DECK_CREW = "deck_crew"
    BUYER = "buyer"
    SIMULATION = "simulation"


@dataclass
class Tile(DialMixin):
    """A single piece of compiled knowledge.

    This is the fundamental unit of the LucidDreamer system.
    Every interaction, every command, every classification becomes a tile.
    Tiles can be verified, corrected, generalized, and compiled.

    Confidence evolves over time:
    - Starts at the model's confidence (0.0-1.0)
    - Increases with each correct use (+0.02)
    - Decreases with each correction (-0.1)
    - Reaches 1.0 (COMPILED) after consistent verified use
    """
    tile_type: TileType
    input_pattern: str
    output_action: str
    confidence: float = 0.0
    verifier: Verifier = Verifier.MODEL

    created_at: float = field(default_factory=time.time)
    source: str = ""
    trip_id: str = ""
    vessel: str = ""

    times_used: int = 0
    times_correct: int = 0
    times_corrected: int = 0

    parent_tile_id: Optional[str] = None
    negative_of: Optional[str] = None

    metadata: dict = field(default_factory=dict)
    dial_override: Optional[float] = None

    @property
    def tile_id(self) -> str:
        content = f"{self.tile_type.value}:{self.input_pattern}:{self.output_action}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    @property
    def success_rate(self) -> float:
        if self.times_used == 0:
            return self.confidence
        return self.times_correct / self.times_used

    @property
    def confidence_class(self) -> Confidence:
        if self.confidence >= 1.0:
            return Confidence.COMPILED
        elif self.confidence >= 0.90:
            return Confidence.VERIFIED
        elif self.confidence >= 0.70:
            return Confidence.TENTATIVE
        elif self.confidence >= 0.50:
            return Confidence.AMBIGUOUS
        return Confidence.UNKNOWN

    def __repr__(self) -> str:
        return (
            f"Tile({self.tile_type.value}, {self.input_pattern!r}, "
            f"conf={self.confidence:.2f})"
        )

    def record_use(self, correct: bool) -> None:
        if not isinstance(correct, bool):
            raise TypeError(f"correct must be bool, got {type(correct).__name__}")
        self.times_used += 1
        if correct:
            self.times_correct += 1
            self.confidence = min(1.0, self.confidence + 0.02)
        else:
            self.times_corrected += 1
            self.confidence = max(0.0, self.confidence - 0.1)

    def to_dict(self) -> dict:
        return {
            "tile_id": self.tile_id,
            "tile_type": self.tile_type.value,
            "input_pattern": self.input_pattern,
            "output_action": self.output_action,
            "confidence": self.confidence,
            "confidence_class": self.confidence_class.value,
            "verifier": self.verifier.value,
            "created_at": self.created_at,
            "source": self.source,
            "trip_id": self.trip_id,
            "vessel": self.vessel,
            "times_used": self.times_used,
            "times_correct": self.times_correct,
            "times_corrected": self.times_corrected,
            "parent_tile_id": self.parent_tile_id,
            "negative_of": self.negative_of,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Tile":
        data = data.copy()
        data["tile_type"] = TileType(data["tile_type"])
        data["verifier"] = Verifier(data.get("verifier", "model"))
        for skip in ["tile_id", "confidence_class", "success_rate"]:
            data.pop(skip, None)
        return cls(**data)


@dataclass
class CommandTile(Tile):
    """A voice command → action mapping.

    The core tile type for autopilot voice control.
    Includes a regex pattern for compiled matching and
    audio response path for pre-generated TTS.
    """
    tile_type: TileType = field(default=TileType.COMMAND, init=False)
    regex_pattern: str = ""
    parameters: dict = field(default_factory=dict)
    audio_response: str = ""
    requires_confirmation: bool = False


@dataclass
class VisionTile(Tile):
    """A fish/species classification tile.

    Every fish gets a photo, a species ID, a hold assignment,
    and a confidence score. Low-confidence calls alert deck crew.
    """
    tile_type: TileType = field(default=TileType.VISION, init=False)
    species: str = ""
    hold_number: int = 0
    photo_path: str = ""
    weight_estimate: float = 0.0


@dataclass
class ChartTile(Tile):
    """A chart/navigation interpretation tile.

    Captures knowledge about depth contours, chart features,
    predictor lines, and navigation queries.
    """
    tile_type: TileType = field(default=TileType.CHART, init=False)
    region: str = ""
    depth_range: tuple = (0.0, 0.0)
    features: list = field(default_factory=list)


class TileStore:
    """In-memory tile storage with fast lookup.

    Tiles are indexed by tile_id, input_pattern (regex match),
    tile_type, and confidence level. Supports JSON export/import
    for persistence between sessions.

    Thread-safe: all mutations are protected by a lock.
    """
    def __init__(self):
        self._tiles: dict[str, Tile] = {}
        self._by_type: dict[TileType, list[str]] = {t: [] for t in TileType}
        self._lock = threading.Lock()

    def add(self, tile: Tile) -> str:
        """Add a tile to the store. Returns the tile_id."""
        if not isinstance(tile, Tile):
            raise TypeError(f"Expected Tile, got {type(tile).__name__}")
        with self._lock:
            tid = tile.tile_id
            self._tiles[tid] = tile
            if tile.tile_type in self._by_type:
                self._by_type[tile.tile_type].append(tid)
            return tid

    def get(self, tile_id: str) -> Optional[Tile]:
        return self._tiles.get(tile_id)  # read-only, no lock needed

    def find_by_pattern(self, pattern: str) -> list[Tile]:
        results = []
        for tile in self._tiles.values():
            if tile.input_pattern == pattern:
                results.append(tile)
            elif hasattr(tile, 'regex_pattern') and tile.regex_pattern:
                try:
                    if re.match(tile.regex_pattern, pattern, re.IGNORECASE):
                        results.append(tile)
                except re.error:
                    pass
        return sorted(results, key=lambda t: t.confidence, reverse=True)

    def find_by_type(self, tile_type: TileType) -> list[Tile]:
        return [self._tiles[tid] for tid in self._by_type.get(tile_type, []) if tid in self._tiles]

    def find_compiled(self) -> list[Tile]:
        return [t for t in self._tiles.values() if t.confidence >= 1.0]

    def find_ambiguous(self) -> list[Tile]:
        return [t for t in self._tiles.values() if 0.5 <= t.confidence < 0.9]

    def remove(self, tile_id: str) -> bool:
        with self._lock:
            if tile_id in self._tiles:
                tile = self._tiles.pop(tile_id)
                if tile.tile_type in self._by_type:
                    try:
                        self._by_type[tile.tile_type].remove(tile_id)
                    except ValueError:
                        pass
                return True
            return False

    def __repr__(self) -> str:
        return f"TileStore({len(self._tiles)} tiles)"

    def __len__(self) -> int:
        return len(self._tiles)

    def __iter__(self):
        return iter(self._tiles.values())

    def export_json(self) -> str:
        return json.dumps([t.to_dict() for t in self._tiles.values()], indent=2)

    def import_json(self, data: str) -> int:
        tiles = json.loads(data)
        count = 0
        for t in tiles:
            tile = Tile.from_dict(t)
            self.add(tile)
            count += 1
        return count
