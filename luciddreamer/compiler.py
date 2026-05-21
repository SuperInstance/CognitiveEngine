"""Rigid structure finder — reverse-engineers soft model behavior into hard code.

The compiler watches tile accumulation and identifies when enough evidence
exists to compile a pattern into deterministic regex+lookup code. Once compiled,
a command needs ZERO inference — no model, no tokens, no latency.

Compile threshold (from flux-lucid dream.rs experimental data):
- Literal extraction accuracy: 97.5% → compile when confidence > 0.975
- Amnesia cliff: 10% coverage → don't compile with fewer than 3 samples
"""

__all__ = ["CompiledCommand", "RigidFinder"]


import re
from typing import Optional
from .tiles import Tile, TileType, TileStore, CommandTile


class CompiledCommand:
    """A compiled regex → action mapping. Zero inference needed.

    This is what a soft model's behavior becomes after enough verified
    interactions. The regex is deterministic. The action is fixed.
    No model required.
    """
    def __init__(self, pattern: str, action: str, parameters: dict = None,
                 audio_response: str = "", requires_confirmation: bool = False):
        self.pattern = pattern
        self.compiled_re = re.compile(pattern, re.IGNORECASE)
        self.action = action
        self.parameters = parameters or {}
        self.audio_response = audio_response
        self.requires_confirmation = requires_confirmation

    def match(self, text: str) -> Optional[dict]:
        m = self.compiled_re.match(text.strip())
        if m:
            result = {"action": self.action}
            result.update(m.groupdict())
            result.update(self.parameters)
            return result
        return None

    def __repr__(self):
        return f"CompiledCommand({self.pattern!r} → {self.action!r})"


class RigidFinder:
    """Find rigid structures in soft model behavior and compile them.

    A rigid structure is a region of the model's behavior space where the
    output is deterministic — the same input always produces the same output.

    The compiler watches tile accumulation and compiles when:
    1. Confidence > 97.5% (literal extraction accuracy from dream.rs)
    2. At least 3 verified uses (amnesia cliff at 10% coverage)
    3. Error rate < 5% in recent uses (stability check)
    """

    COMPILE_THRESHOLD = 0.975
    MIN_SAMPLES = 3
    STABILITY_THRESHOLD = 0.05

    def __init__(self, store: TileStore):
        self.store = store
        self._compiled: list[CompiledCommand] = []

    def try_compile(self, tile: Tile) -> Optional[CompiledCommand]:
        if tile.tile_type != TileType.COMMAND:
            return None
        if tile.confidence < self.COMPILE_THRESHOLD:
            return None
        if tile.times_used < self.MIN_SAMPLES:
            return None
        if tile.times_corrected > 0:
            error_rate = tile.times_corrected / max(1, tile.times_used)
            if error_rate > self.STABILITY_THRESHOLD:
                return None

        pattern = ""
        audio = ""
        confirm = False
        if isinstance(tile, CommandTile):
            pattern = tile.regex_pattern or self._auto_pattern(tile.input_pattern)
            audio = tile.audio_response
            confirm = tile.requires_confirmation
        else:
            pattern = self._auto_pattern(tile.input_pattern)

        cmd = CompiledCommand(
            pattern=pattern,
            action=tile.output_action,
            audio_response=audio,
            requires_confirmation=confirm,
        )
        self._compiled.append(cmd)
        return cmd

    def compile_all(self) -> list[CompiledCommand]:
        compiled = []
        for tile in self.store:
            cmd = self.try_compile(tile)
            if cmd:
                compiled.append(cmd)
        return compiled

    def match(self, text: str) -> Optional[dict]:
        for cmd in self._compiled:
            result = cmd.match(text)
            if result is not None:
                return result
        return None

    def _auto_pattern(self, text: str) -> str:
        """Generate a regex pattern from an input example.

        Replaces digit sequences with named capture groups.
        e.g. "turn port 10 degrees" → "^turn port (?P<n>\\d+) degrees$"
        """
        # Replace digit sequences with capture groups before escaping
        result = re.sub(r'\d+', r'PLACEHOLDER_DIGITS', text)
        # Escape regex special chars
        result = re.escape(result)
        # Put capture groups back (re.escape doesn't touch our placeholder)
        result = result.replace('PLACEHOLDER_DIGITS', r'(?P<n>\d+)')
        return f"^{result}$"

    def __repr__(self) -> str:
        return f"RigidFinder(compiled={self.compiled_count}, coverage={self.coverage:.1%})"

    @property
    def compiled_count(self) -> int:
        return len(self._compiled)

    @property
    def coverage(self) -> float:
        total = len(self.store)
        if total == 0:
            return 0.0
        compiled_tiles = sum(1 for t in self.store if t.confidence >= self.COMPILE_THRESHOLD)
        return compiled_tiles / total
