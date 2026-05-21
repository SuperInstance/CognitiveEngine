"""Simulators for testing LucidDreamer before going to sea.

Every simulator generates fake data that mimics real maritime operations.
Use these to test your tile system, compilation pipeline, and review workflows
without risking anything on the water.

Quick start:
    from luciddreamer.simulators import AutopilotSimulator
    sim = AutopilotSimulator()
    for command in sim.generate_commands(50):
        print(command)
"""


from __future__ import annotations

__all__ = ["AutopilotSimulator", "FishSortSimulator", "ChartSimulator", "CaptainReviewSimulator", "FullTripSimulator"]

import random
import time
from dataclasses import dataclass, field
from typing import Optional

from .tiles import (
    Tile,
    TileType,
    Confidence,
    Verifier,
    CommandTile,
    VisionTile,
    ChartTile,
    TileStore,
)
from .compiler import RigidFinder
from .bathymetry import BathymetricMap
from .router import Router, RouteDecision


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PACIFIC_SALMON = [
    ("Chinook", "Oncorhynchus tshawytscha", "king"),
    ("Sockeye", "Oncorhynchus nerka", "red"),
    ("Pink", "Oncorhynchus gorbuscha", "humpy"),
    ("Chum", "Oncorhynchus keta", "dog"),
    ("Coho", "Oncorhynchus kisutch", "silver"),
]

_GROUND_FISH = [
    ("Halibut", "Hippoglossus stenolepis"),
    ("Pollock", "Gadus chalcogrammus"),
    ("Pacific Cod", "Gadus macrocephalus"),
    ("Lingcod", "Ophiodon elongatus"),
    ("Yelloweye Rockfish", "Sebastes ruberrimus"),
]

_COMPASS_DIRS = {
    "north": 0, "northeast": 45, "east": 90, "southeast": 135,
    "south": 180, "southwest": 225, "west": 270, "northwest": 315,
}

_CLOCK_POSITIONS = {
    "12 o'clock": 0, "1 o'clock": 30, "2 o'clock": 60, "3 o'clock": 90,
    "4 o'clock": 120, "5 o'clock": 150, "6 o'clock": 180, "7 o'clock": 210,
    "8 o'clock": 240, "9 o'clock": 270, "10 o'clock": 300, "11 o'clock": 330,
}


def _heading_true(h: float) -> float:
    """Normalize a heading to 0-359."""
    return round(h % 360, 1)


# ---------------------------------------------------------------------------
# AutopilotSimulator
# ---------------------------------------------------------------------------

class AutopilotSimulator:
    """Generate realistic voice commands as heard on a fishing vessel's helm.

    Categories generated (controlled by *difficulty*):
    - Exact matches: ``"turn port 10 degrees"``, ``"steer 270"``, ``"steady"``
    - Abstractions: ``"turn to 1 o'clock"``, ``"hard to port"``
    - Captain dialect: ``"come left 15"``, ``"put her head to the west"``
    - Ambiguous: ``"turn a bit"``, ``"head that way"``
    - Negative (should NOT match): ``"what's the weather?"``, ``"how far to port?"``

    Parameters:
        count: Number of commands to generate per batch.
        difficulty: 0.0-1.0. Higher = more ambiguous and dialect commands.
        seed: Optional RNG seed for reproducibility.
        vessel: Vessel name injected into tile metadata.

    Each generated command is a dict with keys:
        ``text``, ``expected_action``, ``heading``, ``confidence``,
        ``category``, ``tile`` (a :class:`CommandTile`).

    Example::

        sim = AutopilotSimulator(count=20, seed=42)
        for cmd in sim.generate():
            print(cmd["text"], "→", cmd["expected_action"])
    """

    def __init__(self, count: int = 50, difficulty: float = 0.3,
                 seed: Optional[int] = None, vessel: str = "F/V Horizon"):
        self.count = count
        self.difficulty = max(0.0, min(1.0, difficulty))
        self.vessel = vessel
        self._rng = random.Random(seed)

    def __repr__(self) -> str:
        return f"AutopilotSimulator(count={self.count}, difficulty={self.difficulty:.2f})"

    # -- generators by category --

    def _exact_match(self) -> dict:
        """Deterministic commands with numeric parameters."""
        templates = [
            ("turn port {deg} degrees", "TURN_PORT", -1),
            ("turn starboard {deg} degrees", "TURN_STARBOARD", 1),
            ("steer {hdg}", "SET_HEADING", 0),
            ("head {hdg}", "SET_HEADING", 0),
            ("come to {hdg}", "SET_HEADING", 0),
            ("steady on {hdg}", "STEADY_HEADING", 0),
            ("increase speed {kts} knots", "INCREASE_SPEED", 0),
            ("decrease speed {kts} knots", "DECREASE_SPEED", 0),
            ("maintain course", "MAINTAIN_COURSE", 0),
            ("steady as she goes", "MAINTAIN_COURSE", 0),
            ("all stop", "ALL_STOP", 0),
            ("full ahead", "FULL_AHEAD", 0),
            ("half ahead", "HALF_AHEAD", 0),
            ("slow ahead", "SLOW_AHEAD", 0),
            "dead slow ahead",
            "astern {kts}",
            "hard to port",
            "hard to starboard",
            "rudder amidships",
            "neutral",
        ]
        t = self._rng.choice(templates)
        if isinstance(t, tuple):
            template, action, direction = t
            if "{deg}" in template:
                deg = self._rng.choice([5, 10, 15, 20, 30])
                text = template.format(deg=deg)
                hdg = _heading_true((180 if direction < 0 else 0) + deg)
            elif "{hdg}" in template:
                hdg = self._rng.choice(range(0, 360, 5))
                text = template.format(hdg=hdg)
            elif "{kts}" in template:
                kts = self._rng.choice([1, 2, 3, 5])
                text = template.format(kts=kts)
                hdg = 0.0
            else:
                text = template
                hdg = 0.0
        else:
            text = t
            action = "ENGINE_COMMAND"
            hdg = 0.0

        return {"text": text, "expected_action": action, "heading": hdg,
                "confidence": 0.95, "category": "exact"}

    def _abstraction(self) -> dict:
        """Relative direction commands without exact numbers."""
        templates = [
            ("turn to {clock}", "TURN_CLOCK", _CLOCK_POSITIONS),
            ("head to {clock}", "TURN_CLOCK", _CLOCK_POSITIONS),
            ("bear left", "TURN_PORT_GENERAL", {}),
            ("bear right", "TURN_STARBOARD_GENERAL", {}),
            ("come around", "TURN_180", {}),
            ("hard to port", "HARD_PORT", {}),
            ("hard to starboard", "HARD_STARBOARD", {}),
            ("ease to port", "EASE_PORT", {}),
            ("ease to starboard", "EASE_STARBOARD", {}),
            ("put the wheel over", "HARD_TURN", {}),
        ]
        template, action, extra = self._rng.choice(templates)
        if extra:
            clock = self._rng.choice(list(extra.keys()))
            text = template.format(clock=clock)
            hdg = _heading_true(extra[clock])
        else:
            text = template
            hdg = 0.0

        return {"text": text, "expected_action": action, "heading": hdg,
                "confidence": 0.75, "category": "abstraction"}

    def _captain_dialect(self) -> dict:
        """Colloquial commands from experienced skippers."""
        templates = [
            ("come left {deg}", "TURN_PORT"),
            ("come right {deg}", "TURN_STARBOARD"),
            ("put her head to the {dirn}", "SET_HEADING"),
            ("point her {dirn}", "SET_HEADING"),
            ("give her {deg} to port", "TURN_PORT"),
            ("give her {deg} to starboard", "TURN_STARBOARD"),
            ("bring her around to {hdg}", "SET_HEADING"),
            ("square away on {hdg}", "STEADY_HEADING"),
            ("let her run", "MAINTAIN_COURSE"),
            ("hold your course", "MAINTAIN_COURSE"),
            ("back her down", "DECREASE_SPEED"),
            ("push her up a bit", "INCREASE_SPEED"),
            ("kick her ahead", "INCREASE_SPEED"),
            ("check her head", "SLOW_TURN"),
        ]
        template, action = self._rng.choice(templates)
        if "{deg}" in template:
            deg = self._rng.choice([5, 10, 15, 20, 25])
            text = template.format(deg=deg)
            hdg = deg
        elif "{dirn}" in template:
            dirn = self._rng.choice(list(_COMPASS_DIRS.keys()))
            text = template.format(dirn=dirn)
            hdg = _heading_true(_COMPASS_DIRS[dirn])
        elif "{hdg}" in template:
            hdg = self._rng.choice(range(0, 360, 10))
            text = template.format(hdg=hdg)
        else:
            text = template
            hdg = 0.0

        return {"text": text, "expected_action": action, "heading": hdg,
                "confidence": 0.70, "category": "dialect"}

    def _ambiguous(self) -> dict:
        """Commands that need clarification."""
        templates = [
            ("turn a bit", "TURN_GENERAL"),
            ("head that way", "TURN_GENERAL"),
            ("go a little more", "TURN_GENERAL"),
            ("not that way", "TURN_GENERAL"),
            ("the other way", "TURN_GENERAL"),
            ("a touch to port", "TURN_PORT_SMALL"),
            ("just a hair to starboard", "TURN_STARBOARD_SMALL"),
            ("more", "INCREASE_SPEED_OR_TURN"),
            ("less", "DECREASE_SPEED_OR_TURN"),
            ("over there", "TURN_GENERAL"),
        ]
        text, action = self._rng.choice(templates)
        return {"text": text, "expected_action": action, "heading": 0.0,
                "confidence": 0.40, "category": "ambiguous"}

    def _negative(self) -> dict:
        """Sentences that sound nautical but are NOT helm commands."""
        templates = [
            "what's the weather doing?",
            "how far to port?",
            "what time is high tide?",
            "any traffic on the AIS?",
            "call me when we're at the waypoint",
            "set the drag for 50 fathoms",
            "we need more ice",
            "how many fish in the hold?",
            "get the deck ready",
            "check the hydraulics",
            "what's our ETA?",
            "radio the tender",
            "did you log that haul?",
            "water temperature?",
            "any birds working?",
        ]
        return {"text": self._rng.choice(templates), "expected_action": "NONE",
                "heading": 0.0, "confidence": 0.10, "category": "negative"}

    # -- public API --

    def generate_commands(self, count: Optional[int] = None) -> list[dict]:
        """Generate *count* command samples (defaults to ``self.count``).

        Returns a list of dicts, each with ``text``, ``expected_action``,
        ``heading``, ``confidence``, ``category``, and ``tile``.
        """
        n = count or self.count
        results: list[dict] = []
        for _ in range(n):
            roll = self._rng.random()
            d = self.difficulty
            if roll < 0.30 * (1 - d):
                cmd = self._exact_match()
            elif roll < 0.50 * (1 - d):
                cmd = self._exact_match()  # more exact when easy
            elif roll < 0.55 + 0.15 * d:
                cmd = self._abstraction()
            elif roll < 0.70 + 0.15 * d:
                cmd = self._captain_dialect()
            elif roll < 0.85 + 0.05 * d:
                cmd = self._ambiguous()
            else:
                cmd = self._negative()

            tile = CommandTile(
                input_pattern=cmd["text"],
                output_action=cmd["expected_action"],
                confidence=cmd["confidence"],
                verifier=Verifier.SIMULATION,
                source="simulation",
                vessel=self.vessel,
                metadata={"category": cmd["category"], "heading": cmd["heading"]},
            )
            cmd["tile"] = tile
            results.append(cmd)
        return results

    def generate(self, count: Optional[int] = None) -> list[dict]:
        """Alias for :meth:`generate_commands`."""
        return self.generate_commands(count)

    def run(self) -> dict:
        """Generate a full batch and return summary statistics.

        Returns a dict with keys:
            ``total``, ``by_category``, ``avg_confidence``,
            ``tiles`` (list of generated Tile objects).
        """
        commands = self.generate_commands()
        by_category: dict[str, int] = {}
        total_conf = 0.0
        tiles: list[CommandTile] = []

        for cmd in commands:
            cat = cmd["category"]
            by_category[cat] = by_category.get(cat, 0) + 1
            total_conf += cmd["confidence"]
            tiles.append(cmd["tile"])

        return {
            "simulator": "autopilot",
            "total": len(commands),
            "by_category": by_category,
            "avg_confidence": round(total_conf / max(1, len(commands)), 3),
            "tiles": tiles,
        }


# ---------------------------------------------------------------------------
# FishSortSimulator
# ---------------------------------------------------------------------------

class FishSortSimulator:
    """Generate fish sorting events for testing vision tiles.

    Covers Pacific salmon species plus groundfish. Injects misclassifications
    and buyer reconciliation discrepancies based on *error_rate*.

    Parameters:
        count: Number of fish events per batch.
        error_rate: 0.0-1.0 probability of injecting a misclassification.
        seed: Optional RNG seed.
        vessel: Vessel name.
        holds: Number of fish holds on the vessel (1-indexed).

    Example::

        sim = FishSortSimulator(count=100, error_rate=0.05)
        report = sim.run()
        print(report["species_distribution"])
    """

    def __init__(self, count: int = 100, error_rate: float = 0.05,
                 seed: Optional[int] = None, vessel: str = "F/V Horizon",
                 holds: int = 6):
        self.count = count
        self.error_rate = max(0.0, min(1.0, error_rate))
        self.vessel = vessel
        self.holds = holds
        self._rng = random.Random(seed)

    def __repr__(self) -> str:
        return f"FishSortSimulator(count={self.count}, error_rate={self.error_rate:.2f}, holds={self.holds})"

    def _pick_species(self) -> tuple[str, str, str]:
        """Returns (common_name, scientific_name, slang)."""
        if self._rng.random() < 0.7:
            return self._rng.choice(_PACIFIC_SALMON)
        else:
            name, sci = self._rng.choice(_GROUND_FISH)
            return (name, sci, name.lower())

    def _fish_event(self) -> dict:
        """Generate a single fish sorting event."""
        common, sci, slang = self._pick_species()
        # Confidence depends on species — Chinook and Halibut easy, Pink/Chum harder
        easy_species = {"Chinook", "Halibut", "Lingcod"}
        base_conf = 0.95 if common in easy_species else 0.80

        # Weight varies by species
        weight_ranges = {
            "Chinook": (8, 50), "Sockeye": (4, 15), "Pink": (2, 8),
            "Chum": (6, 20), "Coho": (4, 15), "Halibut": (20, 300),
            "Pollock": (1, 10), "Pacific Cod": (3, 30), "Lingcod": (5, 50),
            "Yelloweye Rockfish": (5, 25),
        }
        lo, hi = weight_ranges.get(common, (2, 20))
        weight = round(self._rng.uniform(lo, hi), 1)

        hold = self._rng.randint(1, self.holds)
        photo = f"photos/{slang}_{self._rng.randint(1000, 9999)}.jpg"
        misclassified = False
        actual_species = common

        if self._rng.random() < self.error_rate:
            # Inject misclassification
            misclassified = True
            all_species = [s[0] for s in _PACIFIC_SALMON] + [g[0] for g in _GROUND_FISH]
            wrong_choices = [s for s in all_species if s != common]
            common = self._rng.choice(wrong_choices)
            base_conf *= 0.6  # lower confidence for wrong ID

        confidence = min(1.0, max(0.1, base_conf + self._rng.uniform(-0.1, 0.05)))

        tile = VisionTile(
            input_pattern=f"sort:{actual_species}",
            output_action=f"HOLD_{hold}",
            confidence=confidence,
            verifier=Verifier.SIMULATION,
            source="simulation",
            vessel=self.vessel,
            species=common,
            hold_number=hold,
            photo_path=photo,
            weight_estimate=weight,
            metadata={
                "scientific_name": sci,
                "slang": slang,
                "misclassified": misclassified,
                "actual_species": actual_species,
            },
        )

        return {
            "classified_species": common,
            "actual_species": actual_species,
            "misclassified": misclassified,
            "weight": weight,
            "hold": hold,
            "photo": photo,
            "confidence": round(confidence, 3),
            "tile": tile,
        }

    def generate_events(self, count: Optional[int] = None) -> list[dict]:
        """Generate *count* fish sorting events."""
        n = count or self.count
        return [self._fish_event() for _ in range(n)]

    def generate_reconciliation(self, events: list[dict]) -> list[dict]:
        """Generate buyer reconciliation data from sorting events.

        Simulates what the buyer reports back — may show count
        discrepancies due to misclassifications.
        """
        species_counts: dict[str, int] = {}
        for e in events:
            sp = e["classified_species"]
            species_counts[sp] = species_counts.get(sp, 0) + 1

        reconciliation = []
        for sp, count in species_counts.items():
            discrepancy = 0
            if self._rng.random() < self.error_rate:
                discrepancy = self._rng.randint(-3, 3)
            reconciliation.append({
                "species": sp,
                "vessel_count": count,
                "buyer_count": max(0, count + discrepancy),
                "discrepancy": discrepancy,
            })
        return reconciliation

    def run(self) -> dict:
        """Generate a full batch and return summary statistics."""
        events = self.generate_events()
        species_dist: dict[str, int] = {}
        total_weight = 0.0
        misclass_count = 0
        tiles: list[VisionTile] = []

        for e in events:
            sp = e["actual_species"]
            species_dist[sp] = species_dist.get(sp, 0) + 1
            total_weight += e["weight"]
            if e["misclassified"]:
                misclass_count += 1
            tiles.append(e["tile"])

        reconciliation = self.generate_reconciliation(events)

        return {
            "simulator": "fish_sort",
            "total": len(events),
            "species_distribution": species_dist,
            "total_weight": round(total_weight, 1),
            "misclassifications": misclass_count,
            "misclassification_rate": round(misclass_count / max(1, len(events)), 3),
            "reconciliation": reconciliation,
            "tiles": tiles,
        }


# ---------------------------------------------------------------------------
# ChartSimulator
# ---------------------------------------------------------------------------

class ChartSimulator:
    """Generate chart/navigation queries and bathymetric data.

    Simulates the kinds of questions a skipper asks about depth, heading,
    speed extrapolation, and bathymetric contours along a course line.

    Parameters:
        count: Number of chart queries per batch.
        depth_base: Base depth in fathoms for the operating area.
        depth_variation: +/- variation in fathoms.
        seed: Optional RNG seed.
        vessel: Vessel name.

    Example::

        sim = ChartSimulator(count=30, depth_base=80)
        report = sim.run()
        print(report["depth_queries"][0])
    """

    def __init__(self, count: int = 20, depth_base: float = 80.0,
                 depth_variation: float = 40.0, seed: Optional[int] = None,
                 vessel: str = "F/V Horizon"):
        self.count = count
        self.depth_base = depth_base
        self.depth_variation = depth_variation
        self.vessel = vessel
        self._rng = random.Random(seed)

    def __repr__(self) -> str:
        return f"ChartSimulator(count={self.count}, depth_base={self.depth_base:.0f})"

    def _random_depth(self) -> float:
        """Generate a realistic depth sounding in fathoms."""
        return round(max(2.0, self._rng.gauss(self.depth_base, self.depth_variation / 2)), 1)

    def _depth_query(self) -> dict:
        """Generate a depth-related query."""
        templates = [
            "are we going to remain deep enough?",
            "how's the bottom looking?",
            "what's the depth under the keel?",
            "are we clear of the shoal?",
            "depth ahead?",
            "what does the sounder say?",
            "are we in the channel?",
            "how much water do we have?",
            "is there enough water to pass?",
            "shallow water ahead?",
        ]
        text = self._rng.choice(templates)
        current_depth = self._random_depth()
        min_clearance = self._rng.choice([2.0, 3.0, 5.0, 10.0])

        return {
            "query": text,
            "current_depth_fathoms": current_depth,
            "min_clearance_fathoms": min_clearance,
            "safe": current_depth > min_clearance + 5,
            "confidence": round(self._rng.uniform(0.7, 1.0), 2),
        }

    def _heading_speed_extrapolation(self) -> dict:
        """Generate heading/speed history with projection."""
        current_hdg = self._rng.uniform(0, 360)
        current_speed = round(self._rng.uniform(3.0, 10.0), 1)
        history = []
        for i in range(10):
            t = i * 0.5  # every 30 seconds
            hdg = _heading_true(current_hdg + self._rng.gauss(0, 2))
            spd = round(max(0.5, current_speed + self._rng.gauss(0, 0.3)), 1)
            history.append({"time_offset_min": t, "heading": hdg, "speed_kts": spd})

        # 5-minute projection
        projected_hdg = _heading_true(current_hdg + self._rng.gauss(0, 5))
        projected_speed = round(max(0.5, current_speed + self._rng.gauss(0, 0.5)), 1)

        return {
            "query": "where will we be in 5 minutes?",
            "current_heading": round(current_hdg, 1),
            "current_speed_kts": current_speed,
            "history": history,
            "projected_heading": projected_hdg,
            "projected_speed_kts": projected_speed,
        }

    def _bathymetric_contour(self) -> dict:
        """Generate depth soundings along a course line."""
        start_hdg = self._rng.uniform(0, 360)
        points = []
        depth = self._random_depth()
        for i in range(20):
            # Random walk with drift
            depth += self._rng.gauss(0, 3)
            depth = max(1.0, depth)
            lat = round(57.0 + self._rng.uniform(-0.5, 0.5), 4)
            lon = round(-152.0 + self._rng.uniform(-1.0, 1.0), 4)
            points.append({
                "distance_nm": round(i * 0.1, 1),
                "depth_fathoms": round(depth, 1),
                "lat": lat,
                "lon": lon,
            })

        return {
            "query": f"depth contour along heading {round(start_hdg)}",
            "heading": round(start_hdg, 1),
            "points": points,
            "shallowest": min(p["depth_fathoms"] for p in points),
            "deepest": max(p["depth_fathoms"] for p in points),
        }

    def _radar_overlay(self) -> dict:
        """Simulate a radar overlay query."""
        contacts = []
        for _ in range(self._rng.randint(0, 5)):
            contacts.append({
                "bearing": round(self._rng.uniform(0, 360), 1),
                "range_nm": round(self._rng.uniform(0.5, 12.0), 1),
                "type": self._rng.choice(["vessel", "land", "buoy", "unknown"]),
                "cpa_nm": round(self._rng.uniform(0.1, 5.0), 2) if self._rng.random() > 0.3 else None,
            })

        return {
            "query": "radar picture?",
            "range_scale_nm": self._rng.choice([3, 6, 12, 24]),
            "contacts": contacts,
            "traffic_density": len(contacts),
        }

    def generate_queries(self, count: Optional[int] = None) -> list[dict]:
        """Generate *count* chart queries."""
        n = count or self.count
        results = []
        for _ in range(n):
            roll = self._rng.random()
            if roll < 0.35:
                q = self._depth_query()
                q["type"] = "depth"
            elif roll < 0.60:
                q = self._heading_speed_extrapolation()
                q["type"] = "extrapolation"
            elif roll < 0.85:
                q = self._bathymetric_contour()
                q["type"] = "contour"
            else:
                q = self._radar_overlay()
                q["type"] = "radar"

            tile = ChartTile(
                input_pattern=q["query"],
                output_action=q["type"].upper(),
                confidence=q.get("confidence", 0.85),
                verifier=Verifier.SIMULATION,
                source="simulation",
                vessel=self.vessel,
                region=f"heading_{q.get('heading', 0):.0f}" if "heading" in q else "general",
                depth_range=(
                    q.get("shallowest", 0),
                    q.get("deepest", 100),
                ) if "shallowest" in q else (0, 0),
                metadata={"query_type": q["type"]},
            )
            q["tile"] = tile
            results.append(q)
        return results

    def run(self) -> dict:
        """Generate a full batch and return summary."""
        queries = self.generate_queries()
        by_type: dict[str, int] = {}
        tiles: list[ChartTile] = []
        for q in queries:
            t = q["type"]
            by_type[t] = by_type.get(t, 0) + 1
            tiles.append(q["tile"])

        return {
            "simulator": "chart",
            "total": len(queries),
            "by_type": by_type,
            "tiles": tiles,
        }


# ---------------------------------------------------------------------------
# CaptainReviewSimulator
# ---------------------------------------------------------------------------

class CaptainReviewSimulator:
    """Simulate the captain's review of ambiguous tiles.

    Models how a captain would confirm, correct, or reject ambiguous
    items during a review session. Tracks tile evolution over multiple
    sessions and shows coverage improvement.

    Parameters:
        seed: Optional RNG seed.
        confirm_rate: Probability captain confirms an ambiguous item.
        vessel: Vessel name.

    Example::

        sim = CaptainReviewSimulator(confirm_rate=0.8)
        review = sim.review_session(ambiguous_tiles)
        print(review["confirmed"], "confirmed out of", review["total"])
    """

    def __init__(self, seed: Optional[int] = None, confirm_rate: float = 0.8,
                 vessel: str = "F/V Horizon"):
        self.confirm_rate = confirm_rate
        self.vessel = vessel
        self._rng = random.Random(seed)
        self._sessions: list[dict] = []

    def __repr__(self) -> str:
        return f"CaptainReviewSimulator(sessions={len(self._sessions)}, confirm_rate={self.confirm_rate:.2f})"

    def review_session(self, tiles: list[Tile]) -> dict:
        """Run a single review session over ambiguous tiles.

        Returns a dict with:
            ``total``, ``confirmed``, ``corrected``, ``rejected``,
            ``results`` (list of per-tile outcomes), ``coverage_before``,
            ``coverage_after``.
        """
        results = []
        confirmed = corrected = rejected = 0

        for tile in tiles:
            roll = self._rng.random()
            if roll < self.confirm_rate:
                # Confirm — boost confidence
                tile.confidence = min(1.0, tile.confidence + 0.15)
                tile.verifier = Verifier.CAPTAIN
                tile.times_used += 1
                tile.times_correct += 1
                results.append({"tile_id": tile.tile_id, "outcome": "confirmed",
                                "confidence": tile.confidence})
                confirmed += 1
            elif roll < self.confirm_rate + 0.15:
                # Correct — captain provides different action
                tile.tile_type = TileType.CORRECTION
                tile.confidence = 0.85
                tile.verifier = Verifier.CAPTAIN
                tile.times_corrected += 1
                results.append({"tile_id": tile.tile_id, "outcome": "corrected",
                                "confidence": tile.confidence})
                corrected += 1
            else:
                # Reject — mark as negative knowledge
                tile.tile_type = TileType.NEGATIVE
                tile.confidence = 0.0
                tile.verifier = Verifier.CAPTAIN
                results.append({"tile_id": tile.tile_id, "outcome": "rejected",
                                "confidence": tile.confidence})
                rejected += 1

        session_data = {
            "total": len(tiles),
            "confirmed": confirmed,
            "corrected": corrected,
            "rejected": rejected,
            "results": results,
        }
        self._sessions.append(session_data)
        return session_data

    def multi_session(self, tiles: list[Tile], sessions: int = 3) -> dict:
        """Run multiple review sessions, tracking coverage over time.

        Each session reviews the same tiles (simulating re-review
        of items that were corrected in previous sessions).
        """
        history = []
        for i in range(sessions):
            result = self.review_session(tiles)
            # Recalculate coverage
            compiled = sum(1 for t in tiles if t.confidence >= 0.975)
            coverage = compiled / max(1, len(tiles))
            result["coverage_after"] = round(coverage, 3)
            history.append(result)

        return {
            "total_sessions": sessions,
            "total_tiles": len(tiles),
            "history": history,
            "final_coverage": history[-1]["coverage_after"] if history else 0.0,
        }

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    def run(self, tiles: Optional[list[Tile]] = None) -> dict:
        """Run a default review session. Creates sample tiles if none provided."""
        if tiles is None:
            # Generate some sample ambiguous tiles
            tiles = []
            for i in range(20):
                tile = Tile(
                    tile_type=TileType.COMMAND,
                    input_pattern=f"sample command {i}",
                    output_action=f"ACTION_{i}",
                    confidence=0.5 + self._rng.uniform(0, 0.3),
                    verifier=Verifier.MODEL,
                    source="simulation",
                    vessel=self.vessel,
                )
                tiles.append(tile)

        return self.multi_session(tiles, sessions=3)


# ---------------------------------------------------------------------------
# FullTripSimulator
# ---------------------------------------------------------------------------

class FullTripSimulator:
    """End-to-end fishing trip simulation combining all simulators.

    Simulates the full lifecycle:
        1. Steam out (autopilot commands + chart queries)
        2. Fish (fish sorting events)
        3. Review (captain review of ambiguous items)
        4. Steam back (more autopilot + chart)

    Tracks tile accumulation, compilation, and coverage throughout.

    Parameters:
        autopilot_commands: Commands during steam phases.
        fish_events: Fish sorting events during fishing phase.
        chart_queries: Chart queries throughout the trip.
        seed: Optional RNG seed.
        vessel: Vessel name.
        trip_id: Trip identifier.

    Example::

        sim = FullTripSimulator(seed=42)
        report = sim.run()
        print(f"Trip {report['trip_id']}: {report['total_tiles']} tiles")
    """

    def __init__(self, autopilot_commands: int = 40, fish_events: int = 200,
                 chart_queries: int = 15, seed: Optional[int] = None,
                 vessel: str = "F/V Horizon", trip_id: str = ""):
        self.autopilot_commands = autopilot_commands
        self.fish_events = fish_events
        self.chart_queries = chart_queries
        self.vessel = vessel
        self._rng_for_id = random.Random(seed)
        self.trip_id = trip_id or f"TRIP-{self._rng_for_id.randint(1000, 9999)}"
        self._seed = seed
        self._rng = random.Random(seed)

    def __repr__(self) -> str:
        return (
            f"FullTripSimulator({self.trip_id}, "
            f"ap={self.autopilot_commands}, fish={self.fish_events}, "
            f"chart={self.chart_queries})"
        )

    def run(self) -> dict:
        """Run the full trip simulation.

        Returns a comprehensive trip report with:
            ``trip_id``, ``vessel``, ``phases``, ``total_tiles``,
            ``compilation_stats``, ``coverage``, ``bathymetry``.
        """
        base_seed = self._seed or int(time.time())

        # Phase 1: Steam out
        ap = AutopilotSimulator(
            count=self.autopilot_commands // 2,
            seed=base_seed,
            vessel=self.vessel,
        )
        ap_out = ap.run()

        ch = ChartSimulator(
            count=self.chart_queries // 2,
            seed=base_seed + 1,
            vessel=self.vessel,
        )
        ch_out = ch.run()

        # Phase 2: Fish
        fs = FishSortSimulator(
            count=self.fish_events,
            error_rate=0.05,
            seed=base_seed + 2,
            vessel=self.vessel,
        )
        fs_out = fs.run()

        # Phase 3: Review
        all_tiles = ap_out["tiles"] + fs_out["tiles"] + ch_out["tiles"]
        # Filter to ambiguous ones
        ambiguous = [t for t in all_tiles if 0.5 <= t.confidence < 0.9]
        review = CaptainReviewSimulator(seed=base_seed + 3, vessel=self.vessel)
        review_out = review.multi_session(ambiguous, sessions=2)

        # Phase 4: Steam back
        ap2 = AutopilotSimulator(
            count=self.autopilot_commands // 2,
            seed=base_seed + 4,
            vessel=self.vessel,
        )
        ap_back = ap2.run()

        ch2 = ChartSimulator(
            count=self.chart_queries - self.chart_queries // 2,
            seed=base_seed + 5,
            vessel=self.vessel,
        )
        ch_back = ch2.run()

        # Compile all tiles into a store
        store = TileStore()
        for t in ap_out["tiles"] + ap_back["tiles"] + fs_out["tiles"] + ch_out["tiles"] + ch_back["tiles"]:
            t.trip_id = self.trip_id
            store.add(t)

        # Run compiler
        finder = RigidFinder(store)
        compiled = finder.compile_all()

        # Build bathymetry
        bathy = BathymetricMap()
        bathy.build_from_store(store)

        total_tiles = len(store)
        compiled_count = len(compiled)
        coverage = compiled_count / max(1, total_tiles)

        # Clearer message when no tiles reach compile threshold
        if coverage == 0.0:
            coverage_note = (
                f"No tiles compiled — need confidence > {RigidFinder.COMPILE_THRESHOLD:.1%} "
                f"and ≥ {RigidFinder.MIN_SAMPLES} verified uses. "
                f"{total_tiles} tiles in store, none yet eligible."
            )
        else:
            coverage_note = (
                f"{compiled_count}/{total_tiles} tiles compiled ({coverage:.1%})"
            )

        return {
            "simulator": "full_trip",
            "trip_id": self.trip_id,
            "vessel": self.vessel,
            "phases": {
                "steam_out": {"autopilot": ap_out["total"], "chart": ch_out["total"]},
                "fishing": {"fish_events": fs_out["total"],
                            "misclassifications": fs_out["misclassifications"],
                            "total_weight": fs_out["total_weight"]},
                "review": {"sessions": review_out["total_sessions"],
                           "tiles_reviewed": review_out["total_tiles"],
                           "final_coverage": review_out["final_coverage"]},
                "steam_back": {"autopilot": ap_back["total"], "chart": ch_back["total"]},
            },
            "total_tiles": total_tiles,
            "compilation_stats": {
                "compiled_commands": compiled_count,
                "coverage": round(coverage, 3),
                "note": coverage_note,
            },
            "coverage_by_type": {
                t.value: len(store.find_by_type(t)) for t in TileType
            },
            "bathymetry": bathy.render(),
            "bathymetric_coverage": round(bathy.overall_coverage, 3),
            "species_distribution": fs_out["species_distribution"],
            "reconciliation": fs_out["reconciliation"],
            "store": store,
            "finder": finder,
        }
