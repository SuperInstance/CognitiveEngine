"""Chart intelligence — reading navigation displays and answering depth queries.

The chart module understands:
- Depth contours (fathoms, color-coded)
- The 5-minute predictor line (where the boat will be)
- Speed over ground (SOG) and course over ground (COG)
- Bathymetric data along the projected course
- Radar overlay information

Key queries:
- "Are we going to remain deep enough for the next 10 minutes?"
- "What's the shallowest we'll be in the next 5 minutes?"
- "Show me the depth along our projected course"
- "What do the blue contours mean?"
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from .tiles import ChartTile, TileStore, Verifier


# ---------------------------------------------------------------------------
# Chart data — the raw information from the navigation display
# ---------------------------------------------------------------------------

@dataclass
class ChartData:
    """Current chart/navigation data from the boat.

    Contains the kind of information you'd get from a chartplotter:
    - A depth grid (bathymetry) around the boat's position
    - Current position, speed, and heading
    - Position history (for the predictor line)
    - Any active waypoints
    """
    # Current position
    latitude: float = 57.0           # degrees N
    longitude: float = -152.0        # degrees E (negative = West)
    speed_over_ground: float = 3.5   # knots
    course_over_ground: float = 240.0  # degrees true

    # Depth grid: list of (lat, lon, depth_fathoms) samples
    # In production, this would come from the chartplotter's bathymetric database
    depth_samples: list[tuple[float, float, float]] = field(default_factory=list)

    # Position history (last N positions for predictor)
    position_history: list[tuple[float, float, float]] = field(default_factory=list)
    # Each entry: (lat, lon, timestamp)

    # Current depth (from depth sounder)
    current_depth: Optional[float] = None

    # Active waypoints
    waypoints: list[tuple[float, float, str]] = field(default_factory=list)
    # Each: (lat, lon, name)

    def depth_at(self, lat: float, lon: float) -> Optional[float]:
        """Estimate depth at a given position using nearest-neighbor from samples.

        In production this would use proper bathymetric interpolation.
        """
        if not self.depth_samples:
            # Generate synthetic depth from a simple model:
            # Depth increases with distance from shoal area at (57.05, -152.1)
            dlat = lat - 57.05
            dlon = lon - (-152.1)
            dist = math.sqrt(dlat**2 + dlon**2)
            depth = 20 + dist * 600  # roughly 20 fathoms at shoal, deeper further out
            return round(depth, 1)

        # Nearest-neighbor interpolation
        best_dist = float('inf')
        best_depth = None
        for slat, slon, sdepth in self.depth_samples:
            d = (slat - lat)**2 + (slon - lon)**2
            if d < best_dist:
                best_dist = d
                best_depth = sdepth
        return best_depth

    def add_depth_sample(self, lat: float, lon: float, depth: float) -> None:
        """Add a depth sample to the grid."""
        self.depth_samples.append((lat, lon, depth))

    def add_position(self, lat: float, lon: float, timestamp: float = 0.0) -> None:
        """Record a position in the history."""
        self.position_history.append((lat, lon, timestamp))

    @property
    def heading_rad(self) -> float:
        """Course over ground in radians."""
        return math.radians(self.course_over_ground)


# ---------------------------------------------------------------------------
# Position prediction
# ---------------------------------------------------------------------------

def predict_position(chart_data: ChartData, minutes_ahead: float) -> dict:
    """Predict the boat's position N minutes from now.

    Uses speed over ground (SOG) and course over ground (COG) to
    extrapolate a dead-reckoning position. This is what the predictor
    line shows on the chart display.

    Returns dict with lat, lon, distance_nm, bearing.
    """
    sog = chart_data.speed_over_ground  # knots
    cog = chart_data.heading_rad
    hours = minutes_ahead / 60.0
    distance_nm = sog * hours

    # Dead reckoning: move along current heading
    # 1 nautical mile = 1/60 degree latitude
    dlat = distance_nm * math.cos(cog) / 60.0
    # Longitude adjustment for latitude (meridional parts)
    dlon = distance_nm * math.sin(cog) / (60.0 * math.cos(chart_data.heading_rad))

    # Actually, for small distances:
    dlon = distance_nm * math.sin(cog) / (60.0 * math.cos(math.radians(chart_data.latitude)))

    pred_lat = chart_data.latitude + dlat
    pred_lon = chart_data.longitude + dlon

    return {
        "lat": round(pred_lat, 6),
        "lon": round(pred_lon, 6),
        "distance_nm": round(distance_nm, 3),
        "bearing": chart_data.course_over_ground,
        "minutes_ahead": minutes_ahead,
    }


# ---------------------------------------------------------------------------
# Depth along route
# ---------------------------------------------------------------------------

def min_depth_along_route(chart_data: ChartData, minutes: float,
                          steps: int = 20) -> dict:
    """Find the minimum depth along the projected course.

    Samples the depth at regular intervals along the predicted route
    and returns the shallowest point found.

    This answers: "What's the shallowest we'll be in the next N minutes?"
    """
    min_depth = float('inf')
    min_depth_at = 0.0
    depths: list[tuple[float, float]] = []  # (minutes_ahead, depth)

    for i in range(steps + 1):
        t = minutes * i / steps
        pred = predict_position(chart_data, t)
        depth = chart_data.depth_at(pred["lat"], pred["lon"])

        if depth is not None:
            depths.append((t, depth))
            if depth < min_depth:
                min_depth = depth
                min_depth_at = t

    if min_depth == float('inf'):
        min_depth = 0.0

    return {
        "min_depth": round(min_depth, 1),
        "min_depth_at_minutes": round(min_depth_at, 1),
        "current_depth": chart_data.current_depth,
        "depths_along_route": depths,
        "course": chart_data.course_over_ground,
        "speed": chart_data.speed_over_ground,
    }


# ---------------------------------------------------------------------------
# Natural language depth query answering
# ---------------------------------------------------------------------------

def answer_depth_query(question: str, chart_data: ChartData) -> str:
    """Answer a natural language question about depth/navigation.

    Parses the question to determine what kind of answer is needed,
    then uses the chart data to compute and format the answer.
    """
    q = question.lower().strip()

    # Extract time parameter (minutes)
    minutes = _extract_minutes(q)
    min_required = _extract_required_depth(q)

    # Current depth query
    if any(p in q for p in ["current depth", "how deep", "what depth"]):
        if chart_data.current_depth is not None:
            return f"Current depth is {chart_data.current_depth:.1f} fathoms."
        return "No current depth reading available."

    # "Remain deep enough" query
    if "deep enough" in q or "remain" in q or "stay" in q:
        result = min_depth_along_route(chart_data, minutes)
        min_d = result["min_depth"]
        required = min_required or 30.0
        safe = min_d >= required
        status = "✓ Yes" if safe else "⚠ NO"
        return (
            f"{status}, you will remain deep enough for the next {minutes:.0f} minutes. "
            f"Minimum depth: {min_d:.1f} fathoms (at {result['min_depth_at_minutes']:.1f} min ahead). "
            f"Required: {required:.0f} fathoms."
        )

    # "Shallowest" query
    if "shallowest" in q or "minimum depth" in q or "min depth" in q:
        result = min_depth_along_route(chart_data, minutes)
        return (
            f"The shallowest you'll be in the next {minutes:.0f} minutes is "
            f"{result['min_depth']:.1f} fathoms, at {result['min_depth_at_minutes']:.1f} "
            f"minutes ahead on course {chart_data.course_over_ground:.0f}° at "
            f"{chart_data.speed_over_ground:.1f} knots."
        )

    # "Depth along course" query
    if "depth along" in q or "depth on" in q:
        result = min_depth_along_route(chart_data, minutes)
        lines = [f"Depth along projected course (COG {chart_data.course_over_ground:.0f}°, "
                 f"SOG {chart_data.speed_over_ground:.1f} kts):"]
        for t, d in result["depths_along_route"]:
            lines.append(f"  {t:5.1f} min: {d:6.1f} fathoms")
        return "\n".join(lines)

    # Predictor query
    if "predictor" in q:
        pred = predict_position(chart_data, 5)
        pred_depth = chart_data.depth_at(pred["lat"], pred["lon"])
        depth_str = f"{pred_depth:.1f} fathoms" if pred_depth else "unknown depth"
        return (
            f"The 5-minute predictor shows position {pred['lat']:.4f}N, "
            f"{abs(pred['lon']):.4f}W at {depth_str}, "
            f"{pred['distance_nm']:.2f} nm ahead on course {pred['bearing']:.0f}°."
        )

    # Crossing/contour query
    if "cross" in q or "hit" in q:
        result = min_depth_along_route(chart_data, minutes)
        if result["current_depth"] and result["min_depth"] < result["current_depth"]:
            return (
                f"Yes, you'll cross into shallower water. Minimum depth: "
                f"{result['min_depth']:.1f} fathoms at {result['min_depth_at_minutes']:.1f} "
                f"minutes ahead (currently {result['current_depth']:.1f} fathoms)."
            )
        return "No significant shoaling detected in the projected course."

    # Generic depth query
    result = min_depth_along_route(chart_data, minutes)
    return (
        f"At {chart_data.speed_over_ground:.1f} knots on course "
        f"{chart_data.course_over_ground:.0f}°, minimum depth in next "
        f"{minutes:.0f} minutes is {result['min_depth']:.1f} fathoms."
    )


def _extract_minutes(text: str) -> float:
    """Extract a time parameter in minutes from natural language."""
    # "10 minutes", "5 min", "next 10"
    m = re.search(r'(\d+)\s*(?:minutes?|mins?|min)', text)
    if m:
        return float(m.group(1))

    # "next 10" (minutes implied)
    m = re.search(r'next\s+(\d+)', text)
    if m:
        return float(m.group(1))

    # Default to 10 minutes
    return 10.0


def _extract_required_depth(text: str) -> Optional[float]:
    """Extract a required minimum depth from natural language."""
    # "deep enough for 50 fathoms", "need at least 30 fathoms"
    m = re.search(r'(?:at least|minimum|need|require|deep enough(?:\s+for)?)\s+(\d+)\s*fathoms?', text)
    if m:
        return float(m.group(1))

    # "50 fathom" as a standalone
    m = re.search(r'(\d+)\s*fathoms?', text)
    if m:
        return float(m.group(1))

    return None
