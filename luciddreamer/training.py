"""Self-training and LoRA fine-tuning pipeline.

Generates training data from verified tiles, creates LoRA adapters,
manages checkpoints, and handles rollback analysis.

The system trains itself overnight using today's verified tiles.
Weekly, it does a bigger cloud training pass. Every checkpoint is
compared against the previous one - if accuracy drops, rollback
and diagnose what went wrong.

Design principle: ZERO-SHOT FIRST.
Every training example must work without conversation context.
The model's weights ARE the context. The tiles ARE the memory.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json
import hashlib
import time
import threading

from .tiles import Tile, TileStore, TileType, Verifier, Confidence


# ---------------------------------------------------------------------------
# Training data generation
# ---------------------------------------------------------------------------

# Paraphrase templates for maritime commands
# Maps (action_type, parameter_count) → list of templates
_PARAPHRASE_TEMPLATES = {
    "TURN_PORT": [
        "turn port {n}",
        "port {n}",
        "come left {n}",
        "turn left {n}",
        "turn to port {n}",
        "{n} degrees port",
        "{n} port",
        "come around to port {n}",
        "port {n} degrees",
        "hard to port" if "{n}" == "45" else "turn port {n} degrees",
        "put her {n} to port",
        "ease to port {n}",
    ],
    "TURN_STARBOARD": [
        "turn starboard {n}",
        "starboard {n}",
        "come right {n}",
        "turn right {n}",
        "turn to starboard {n}",
        "{n} degrees starboard",
        "{n} starboard",
        "come around to starboard {n}",
        "starboard {n} degrees",
        "put her {n} to starboard",
    ],
    "SET_HEADING": [
        "steer {n}",
        "heading {n}",
        "course {n}",
        "make your heading {n}",
        "put her head to {n}",
        "steer course {n}",
        "head {n}",
        "come to {n}",
    ],
    "HOLD_HEADING": [
        "steady",
        "hold course",
        "steady as she goes",
        "keep her pointing this way",
        "maintain heading",
        "hold this course",
        "steady on",
    ],
    "EMERGENCY_STOP": [
        "all stop",
        "full stop",
        "stop engines",
        "kill the engines",
        "emergency stop",
        "stop everything",
        "halt",
    ],
}

# Negative examples - things that should NOT be treated as commands
_NEGATIVE_EXAMPLES = [
    ("what's the weather like", "NOT_NAV_COMMAND: weather_query"),
    ("how far to port", "AMBIGUOUS: 'port' could mean harbor or left. Ask: 'Do you mean turn left?'"),
    ("good morning", "NOT_NAV_COMMAND: greeting"),
    ("what's for dinner", "NOT_NAV_COMMAND: casual_conversation"),
    ("turn", "INCOMPLETE_COMMAND: ask 'Turn port or starboard, how many degrees?'"),
    ("fish on!", "NOT_NAV_COMMAND: deck_alert"),
    ("head", "INCOMPLETE_COMMAND: ask 'What heading, skipper?'"),
]


@dataclass
class TrainingExample:
    """A single training example for LoRA fine-tuning."""
    instruction: str            # What the captain said
    output: str                 # What the system should do
    system_prompt: str = ""     # Context for the model
    source: str = "tile"        # tile, variation, negative, cloud
    confidence: float = 1.0     # How reliable this example is
    tile_id: str = ""           # Source tile if applicable

    def __repr__(self) -> str:
        return f"TrainingExample({self.instruction!r}, source={self.source})"

    def to_alpaca(self) -> dict:
        """Convert to Alpaca format for LoRA training."""
        return {
            "instruction": self.instruction,
            "input": "",
            "output": self.output,
            "system": self.system_prompt,
        }

    def to_chatml(self) -> list[dict]:
        """Convert to ChatML format."""
        msgs = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.append({"role": "user", "content": self.instruction})
        msgs.append({"role": "assistant", "content": self.output})
        return msgs


class TrainingDataGenerator:
    """Generate LoRA training data from accumulated tiles.

    Every verified tile becomes a training example. The generator also
    creates variations (paraphrases), negative examples, and curriculum
    mixes for stable training.

    Usage:
        gen = TrainingDataGenerator(store, system_prompt="You are Cocapn...")
        data = gen.generate()
        # data is ready for LoRA fine-tuning
    """

    def __init__(self, store: TileStore, system_prompt: str = "",
                 min_confidence: float = 0.8):
        self.store = store
        self.system_prompt = system_prompt
        self.min_confidence = min_confidence

    def __repr__(self) -> str:
        return f"TrainingDataGenerator(tiles={len(self.store)}, min_conf={self.min_confidence})"

    def generate(self, include_variations: bool = True,
                 include_negatives: bool = True,
                 variations_per_tile: int = 10) -> list[TrainingExample]:
        """Generate complete training dataset.

        Mix:
        - All verified tiles (high confidence)
        - Paraphrase variations (for zero-shot generalization)
        - Negative examples (for rejection learning)
        - Historical data (for curriculum stability)
        """
        examples = []

        # 1. Verified tiles (ground truth from captain interactions)
        for tile in self.store:
            if tile.confidence >= self.min_confidence:
                ex = TrainingExample(
                    instruction=tile.input_pattern,
                    output=tile.output_action,
                    system_prompt=self.system_prompt,
                    source="tile",
                    confidence=tile.confidence,
                    tile_id=tile.tile_id,
                )
                examples.append(ex)

        # 2. Paraphrase variations (zero-shot generalization)
        if include_variations:
            for tile in self.store:
                if tile.confidence >= 0.9 and tile.tile_type == TileType.COMMAND:
                    variations = self._generate_variations(tile, variations_per_tile)
                    examples.extend(variations)

        # 3. Negative examples (rejection learning)
        if include_negatives:
            for inp, out in _NEGATIVE_EXAMPLES:
                examples.append(TrainingExample(
                    instruction=inp,
                    output=out,
                    system_prompt=self.system_prompt,
                    source="negative",
                    confidence=1.0,
                ))

            # Also from negative tiles in the store
            for tile in self.store:
                if tile.tile_type == TileType.NEGATIVE:
                    examples.append(TrainingExample(
                        instruction=tile.input_pattern,
                        output=f"NEGATIVE: {tile.output_action}",
                        system_prompt=self.system_prompt,
                        source="negative",
                        confidence=tile.confidence,
                        tile_id=tile.tile_id,
                    ))

        return examples

    def _generate_variations(self, tile: Tile, count: int) -> list[TrainingExample]:
        """Generate paraphrase variations for a command tile."""
        import re

        # Extract the action type and number from the tile
        action = tile.output_action
        examples = []

        # Find matching template group
        for action_prefix, templates in _PARAPHRASE_TEMPLATES.items():
            if action.startswith(action_prefix):
                # Extract number from action
                nums = re.findall(r'\d+', action)
                n = nums[0] if nums else "X"

                for template in templates[:count]:
                    try:
                        variation = template.format(n=n)
                    except (KeyError, IndexError):
                        variation = template

                    examples.append(TrainingExample(
                        instruction=variation,
                        output=action,
                        system_prompt=self.system_prompt,
                        source="variation",
                        confidence=tile.confidence * 0.95,  # Slightly lower than ground truth
                        tile_id=tile.tile_id,
                    ))
                break

        return examples[:count]

    def generate_curriculum(self, examples: list[TrainingExample],
                           historical: list[TrainingExample] = None,
                           mix_ratio: float = 0.3) -> list[TrainingExample]:
        """Create a curriculum mix of new and historical data.

        Prevents catastrophic forgetting by mixing:
        - 70% new data (today's tiles)
        - 30% historical data (previous sessions)

        Args:
            examples: New training examples
            historical: Historical training examples (from previous LoRA versions)
            mix_ratio: Fraction of historical data (0.3 = 30%)
        """
        if not historical:
            return examples

        import random
        n_historical = int(len(examples) * mix_ratio / (1 - mix_ratio))
        n_historical = min(n_historical, len(historical))
        selected = random.sample(historical, n_historical)

        return examples + selected

    def export_alpaca(self, examples: list[TrainingExample]) -> str:
        """Export training data in Alpaca JSON format."""
        return json.dumps(
            [ex.to_alpaca() for ex in examples],
            indent=2,
        )

    def export_chatml(self, examples: list[TrainingExample]) -> str:
        """Export training data in ChatML JSON format."""
        return json.dumps(
            [ex.to_chatml() for ex in examples],
            indent=2,
        )


# ---------------------------------------------------------------------------
# Checkpoint management
# ---------------------------------------------------------------------------

@dataclass
class LoRACheckpoint:
    """A LoRA training checkpoint with accuracy metrics."""
    version: str
    created_at: datetime = field(default_factory=datetime.now)
    base_model: str = "gemma-3-1b-it"
    lora_rank: int = 16
    lora_alpha: int = 32

    # Training metrics
    training_examples: int = 0
    epochs: int = 0
    training_loss: float = 0.0
    validation_loss: float = 0.0

    # Accuracy by command type
    accuracy_by_type: dict[str, float] = field(default_factory=dict)
    overall_accuracy: float = 0.0

    # Simulator results
    simulator_pass_rate: float = 0.0

    # Parent checkpoint (for lineage)
    parent_version: str = ""

    # Training data hash (for reproducibility)
    training_data_hash: str = ""

    @property
    def checkpoint_id(self) -> str:
        return f"{self.version}-{self.created_at.strftime('%Y%m%d')}"

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "base_model": self.base_model,
            "lora_rank": self.lora_rank,
            "training_examples": self.training_examples,
            "overall_accuracy": self.overall_accuracy,
            "accuracy_by_type": self.accuracy_by_type,
            "simulator_pass_rate": self.simulator_pass_rate,
            "parent_version": self.parent_version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LoRACheckpoint":
        data = data.copy()
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass
class CheckpointDiff:
    """Compare two LoRA checkpoints to understand what changed."""
    old: LoRACheckpoint
    new: LoRACheckpoint

    @property
    def accuracy_delta(self) -> float:
        return self.new.overall_accuracy - self.old.overall_accuracy

    @property
    def is_improvement(self) -> bool:
        return self.accuracy_delta > 0.005

    @property
    def is_regression(self) -> bool:
        return self.accuracy_delta < -0.01

    @property
    def type_deltas(self) -> dict[str, float]:
        """Per-command-type accuracy changes."""
        deltas = {}
        for cmd_type in set(list(self.old.accuracy_by_type.keys()) +
                           list(self.new.accuracy_by_type.keys())):
            old_acc = self.old.accuracy_by_type.get(cmd_type, 0.0)
            new_acc = self.new.accuracy_by_type.get(cmd_type, 0.0)
            deltas[cmd_type] = new_acc - old_acc
        return deltas

    @property
    def worst_regressions(self) -> list[tuple[str, float]]:
        """Command types that got worse, sorted by severity."""
        return sorted(
            [(k, v) for k, v in self.type_deltas.items() if v < 0],
            key=lambda x: x[1],
        )

    def diagnose(self) -> str:
        """Generate human-readable diagnosis."""
        lines = [
            f"Checkpoint diff: {self.old.version} → {self.new.version}",
            f"Overall accuracy: {self.old.overall_accuracy:.3f} → {self.new.overall_accuracy:.3f} "
            f"({self.accuracy_delta:+.3f})",
            f"Training examples: {self.old.training_examples} → {self.new.training_examples}",
            "",
        ]

        if self.is_regression:
            lines.append("⚠️  REGRESSION DETECTED")
            lines.append("Worst areas:")
            for area, delta in self.worst_regressions[:5]:
                lines.append(f"  {area}: {delta:+.3f}")
            lines.append("")
            lines.append("Recommended action: ROLLBACK to " + self.old.version)
            lines.append("Flag ambiguous tiles for captain review")
        elif self.is_improvement:
            lines.append("✅ IMPROVEMENT")
            best = sorted(self.type_deltas.items(), key=lambda x: x[1], reverse=True)[:3]
            for area, delta in best:
                lines.append(f"  {area}: {delta:+.3f}")
            lines.append("")
            lines.append(f"Recommended action: PROMOTE {self.new.version} to production")
        else:
            lines.append("➡️  NEUTRAL (no significant change)")
            lines.append("Recommended action: KEEP current, gather more data")

        return "\n".join(lines)


class CheckpointManager:
    """Manages LoRA checkpoint versions, promotion, and rollback.

    Every training session creates a checkpoint. The manager tracks
    which checkpoint is active, handles promotion (if better) and
    rollback (if worse), and maintains the full lineage.
    """

    def __init__(self):
        self._checkpoints: list[LoRACheckpoint] = []
        self._active_version: str = ""
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return f"CheckpointManager(active={self._active_version!r}, versions={len(self._checkpoints)})"

    def add(self, checkpoint: LoRACheckpoint) -> CheckpointDiff:
        """Add a new checkpoint and compare against the current active."""
        with self._lock:
            self._checkpoints.append(checkpoint)

            if not self._active_version:
                self._active_version = checkpoint.version
                return CheckpointDiff(
                    old=checkpoint,
                    new=checkpoint,
                )

            active = self.get_active()
            diff = CheckpointDiff(old=active, new=checkpoint)

            if diff.is_improvement:
                self._active_version = checkpoint.version

            return diff

    def get_active(self) -> Optional[LoRACheckpoint]:
        for cp in self._checkpoints:
            if cp.version == self._active_version:
                return cp
        return self._checkpoints[-1] if self._checkpoints else None

    def rollback(self, version: str) -> Optional[LoRACheckpoint]:
        """Rollback to a specific version."""
        with self._lock:
            for cp in self._checkpoints:
                if cp.version == version:
                    self._active_version = version
                    return cp
            return None

    def lineage(self) -> list[str]:
        """Full checkpoint lineage."""
        return [cp.version for cp in self._checkpoints]

    def export(self) -> str:
        return json.dumps([cp.to_dict() for cp in self._checkpoints], indent=2)


# ---------------------------------------------------------------------------
# System prompt management
# ---------------------------------------------------------------------------

MARITIME_SYSTEM_PROMPT = """You are Cocapn, the maritime intelligence assistant. You understand nautical commands, fish species, navigation, and fishing operations.

CRITICAL RULES:
1. Every command works STANDALONE - no conversation context assumed
2. Emergency commands ("HARD TO PORT", "MAN OVERBOARD") are ALWAYS highest priority
3. If unsure, ASK - never guess on safety-critical commands
4. Depths are in FATHOMS, speed in KNOTS, heading in DEGREES TRUE
5. Port = left, Starboard = right (facing forward)

RESPONSE FORMAT:
- For commands: acknowledge with "Roger" + action taken
- For queries: answer directly and concisely
- For unknown: say "I'm not sure, skipper - [suggest alternative]"
"""


@dataclass
class SystemPromptVersion:
    """Versioned system prompt for the Cocapn."""
    version: str
    prompt: str
    created_at: datetime = field(default_factory=datetime.now)
    accuracy_with_prompt: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "prompt": self.prompt,
            "created_at": self.created_at.isoformat(),
            "accuracy": self.accuracy_with_prompt,
            "notes": self.notes,
        }
