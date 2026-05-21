"""Bathymetric map — visualize model competency as ocean depth.

Compiled code = shallow water (solid bottom, fully mapped).
Inference = deep water (unknown, still exploring).
The goal: tile the ocean floor until the model only swims in deep water for novel inputs.
"""

__all__ = ["DepthSounding", "BathymetricMap"]


from dataclasses import dataclass, field
from typing import Optional
from .tiles import TileStore, Confidence


@dataclass
class DepthSounding:
    """A single sounding line — how well do we know this region?"""
    region: str
    total_commands: int = 0
    compiled_commands: int = 0
    ambiguous_commands: int = 0
    unknown_commands: int = 0

    @property
    def coverage(self) -> float:
        if self.total_commands == 0:
            return 0.0
        return self.compiled_commands / self.total_commands

    @property
    def depth(self) -> float:
        return 1.0 - self.coverage


@dataclass
class BathymetricMap:
    """The full coverage map of model competency.

    Visualizes as an ocean depth chart:
    ████████ = shallow (compiled, zero inference)
    ████     = moderate (mostly compiled)
    ░░░░     = deep (still needs model)
    """
    soundings: dict[str, DepthSounding] = field(default_factory=dict)

    def update(self, region: str, compiled: int, total: int,
               ambiguous: int = 0, unknown: int = 0) -> None:
        self.soundings[region] = DepthSounding(
            region=region,
            total_commands=total,
            compiled_commands=compiled,
            ambiguous_commands=ambiguous,
            unknown_commands=unknown,
        )

    def build_from_store(self, store: TileStore) -> None:
        categories: dict[str, dict] = {}
        for tile in store:
            category = tile.input_pattern.split()[0] if tile.input_pattern else "other"
            if category not in categories:
                categories[category] = {"total": 0, "compiled": 0, "ambiguous": 0, "unknown": 0}
            categories[category]["total"] += 1
            cc = tile.confidence_class
            if cc == Confidence.COMPILED:
                categories[category]["compiled"] += 1
            elif cc in (Confidence.VERIFIED, Confidence.TENTATIVE):
                categories[category]["ambiguous"] += 1
            else:
                categories[category]["unknown"] += 1
        for cat, counts in categories.items():
            self.update(cat, **counts)

    def render(self, width: int = 40) -> str:
        lines = ["Bathymetric Coverage Map", "=" * (width + 20), ""]
        for region, sounding in sorted(self.soundings.items()):
            coverage = sounding.coverage
            filled = int(coverage * width)
            empty = width - filled
            bar = "█" * filled + "░" * empty
            lines.append(f"  {region:15s} {bar} {coverage*100:5.1f}%")
        lines.append("")
        lines.append("  █ = compiled (zero inference)  ░ = needs model")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"BathymetricMap({len(self.soundings)} regions, coverage={self.overall_coverage:.1%})"

    @property
    def overall_coverage(self) -> float:
        if not self.soundings:
            return 0.0
        total = sum(s.total_commands for s in self.soundings.values())
        compiled = sum(s.compiled_commands for s in self.soundings.values())
        return compiled / total if total > 0 else 0.0
