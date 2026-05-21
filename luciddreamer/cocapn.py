"""Cocapn — the boat's AI brain.

A chatbot that lives on the boat, learns from the captain, and can interact
with the navigation computer through mouse output.

Why mouse output? Because it's deliberate and visual. The captain can SEE
what the AI is doing on the nav display and stop it if something looks wrong.
A mouse movement to "toggle radar overlay" takes 2 seconds — slow enough to
interrupt, fast enough to be useful.

The Cocapn learns:
- What the buttons on the nav computer do (by watching the captain)
- What chart features mean (depth contours, colors, symbols)
- How to answer navigation questions ("are we going to remain deep enough?")
- The captain's preferred way of asking things
- What the 5-minute predictor line shows
- What "dragging 50 fathoms" means in context

Every learned behavior becomes a tile. Over time, the Cocapn compiles
common interactions into instant responses.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .tiles import Tile, TileType, ChartTile, CommandTile, TileStore, Confidence, Verifier
from .compiler import RigidFinder, CompiledCommand
from .router import Router, RouteDecision
from .chart import ChartData, predict_position, min_depth_along_route, answer_depth_query


# ---------------------------------------------------------------------------
# Mouse actions — deliberate, visual, stoppable
# ---------------------------------------------------------------------------

class ClickType(Enum):
    SINGLE = "single"
    DOUBLE = "double"
    RIGHT = "right"


@dataclass
class MouseAction:
    """A single deliberate mouse action on the nav display.

    Every action has:
    - A human-readable description (shown on screen so captain can verify)
    - Pre/post delays for deliberate pacing (the captain can see and abort)
    - Click type for different nav computer interactions

    Why not just call an API? Because the captain needs to SEE what's happening.
    Mouse movements are visual, slow enough to interrupt, and match exactly
    what the captain would do manually.
    """
    x: int
    y: int
    click: ClickType = ClickType.SINGLE
    description: str = ""
    pre_delay: float = 0.5   # seconds before action (visual preview)
    post_delay: float = 0.5  # seconds after action (observe result)

    def to_tuple(self) -> tuple[int, int, str]:
        """Return (x, y, click_type) for nav computer input."""
        return (self.x, self.y, self.click.value)


# ---------------------------------------------------------------------------
# Nav computer — simulates the navigation display
# ---------------------------------------------------------------------------

@dataclass
class NavButton:
    """A button on the navigation display."""
    name: str
    x: int
    y: int
    toggle: bool = True         # True = on/off toggle; False = momentary
    state: bool = False         # Current state (on/off)

    def press(self) -> str:
        """Simulate pressing this button. Returns what changed."""
        if self.toggle:
            self.state = not self.state
            return f"{self.name}: {'ON' if self.state else 'OFF'}"
        else:
            return f"{self.name}: activated"


class NavComputer:
    """Simulates the boat's navigation display for testing.

    Has the kind of buttons you'd find on a real chartplotter:
    radar overlay, chart zoom, predictor line, depth contours, waypoints, etc.

    In production, this would be replaced with actual screen capture + mouse
    output to the nav computer. This simulation lets us test the whole flow
    without a boat.
    """

    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Navigation display state
        self.zoom_level: int = 3          # 1 = harbor, 5 = ocean
        self.radar_overlay: bool = False
        self.predictor_line: bool = True
        self.depth_contours: bool = True
        self.waypoints_visible: bool = True
        self.ais_targets: bool = True
        self.bearing_line: bool = False
        self.measurement_tool: bool = False

        # Chart data region currently displayed
        self.chart_center: tuple[float, float] = (57.0, -152.0)  # lat, lon (Kodiak area)
        self.chart_range: float = 12.0  # nautical miles

        # Define buttons at fixed screen positions
        self.buttons: dict[str, NavButton] = {
            "radar_overlay": NavButton("Radar Overlay", 1800, 100, toggle=True, state=False),
            "zoom_in": NavButton("Zoom In", 1800, 160, toggle=False),
            "zoom_out": NavButton("Zoom Out", 1800, 200, toggle=False),
            "predictor": NavButton("Predictor Line", 1800, 260, toggle=True, state=True),
            "depth_contours": NavButton("Depth Contours", 1800, 320, toggle=True, state=True),
            "waypoints": NavButton("Waypoints", 1800, 380, toggle=True, state=True),
            "ais_targets": NavButton("AIS Targets", 1800, 440, toggle=True, state=True),
            "bearing_line": NavButton("Bearing Line", 1800, 500, toggle=True, state=False),
            "measure": NavButton("Measure Tool", 1800, 560, toggle=False),
        }

    def accept_mouse(self, action: MouseAction) -> str:
        """Accept a mouse action and return what changed.

        This is how the Cocapn interacts with the nav display — through
        deliberate mouse clicks that the captain can see and stop.
        """
        # Find which button was clicked
        for name, btn in self.buttons.items():
            # Check if click is within ~25px of button center
            if abs(action.x - btn.x) <= 25 and abs(action.y - btn.y) <= 25:
                result = btn.press()
                # Update computer state from button state
                self._sync_state(name, btn)
                return result

        # Handle special regions
        if action.x < 1700 and action.y < 900:
            # Clicked on the chart area — could be a chart interaction
            lat, lon = self._screen_to_chart(action.x, action.y)
            return f"Chart click at {lat:.4f}N, {abs(lon):.4f}W"

        return f"No action at ({action.x}, {action.y})"

    def accept_mouse_sequence(self, actions: list[MouseAction]) -> list[str]:
        """Accept a sequence of mouse actions. Returns list of results."""
        return [self.accept_mouse(a) for a in actions]

    def _sync_state(self, button_name: str, button: NavButton) -> None:
        """Sync button state back to nav computer state."""
        state_map = {
            "radar_overlay": "radar_overlay",
            "predictor": "predictor_line",
            "depth_contours": "depth_contours",
            "waypoints": "waypoints_visible",
            "ais_targets": "ais_targets",
            "bearing_line": "bearing_line",
        }
        if button_name in state_map:
            setattr(self, state_map[button_name], button.state)
        elif button_name == "zoom_in":
            self.zoom_level = min(5, self.zoom_level + 1)
            self.chart_range = max(1, self.chart_range / 2)
        elif button_name == "zoom_out":
            self.zoom_level = max(1, self.zoom_level - 1)
            self.chart_range = min(100, self.chart_range * 2)

    def _screen_to_chart(self, x: int, y: int) -> tuple[float, float]:
        """Convert screen coordinates to chart lat/lon."""
        lat = self.chart_center[0] + (self.screen_height / 2 - y) / self.screen_height * self.chart_range / 60
        lon = self.chart_center[1] - (self.screen_width / 2 - x) / self.screen_width * self.chart_range / 60
        return (round(lat, 4), round(lon, 4))

    def get_screen_region(self, x: int, y: int, width: int, height: int) -> dict:
        """Read a screen region (simulated — returns chart data for the region)."""
        lat1, lon1 = self._screen_to_chart(x, y)
        lat2, lon2 = self._screen_to_chart(x + width, y + height)
        return {
            "region": {"lat1": min(lat1, lat2), "lat2": max(lat1, lat2),
                       "lon1": min(lon1, lon2), "lon2": max(lon1, lon2)},
            "zoom_level": self.zoom_level,
            "overlays": {
                "radar": self.radar_overlay,
                "predictor": self.predictor_line,
                "depth_contours": self.depth_contours,
                "ais": self.ais_targets,
            },
        }

    def describe_display(self) -> str:
        """Human-readable description of current display state."""
        overlays = []
        if self.radar_overlay:
            overlays.append("radar")
        if self.predictor_line:
            overlays.append("predictor")
        if self.depth_contours:
            overlays.append("depth contours")
        if self.ais_targets:
            overlays.append("AIS targets")
        if self.waypoints_visible:
            overlays.append("waypoints")

        overlay_str = ", ".join(overlays) if overlays else "none"
        return (
            f"Nav display: zoom {self.zoom_level} "
            f"({self.chart_range:.0f}nm range), "
            f"overlays: {overlay_str}"
        )

    def build_mouse_plan(self, target: str) -> list[MouseAction]:
        """Build a sequence of mouse actions to achieve a goal.

        The captain sees each action before it executes and can abort.
        """
        plans: dict[str, list[tuple]] = {
            "toggle_radar": [
                (self.buttons["radar_overlay"].x, self.buttons["radar_overlay"].y,
                 ClickType.SINGLE, "clicking radar overlay toggle"),
            ],
            "zoom_in": [
                (self.buttons["zoom_in"].x, self.buttons["zoom_in"].y,
                 ClickType.SINGLE, "clicking zoom in"),
            ],
            "zoom_out": [
                (self.buttons["zoom_out"].x, self.buttons["zoom_out"].y,
                 ClickType.SINGLE, "clicking zoom out"),
            ],
            "toggle_predictor": [
                (self.buttons["predictor"].x, self.buttons["predictor"].y,
                 ClickType.SINGLE, "clicking predictor line toggle"),
            ],
            "toggle_depth_contours": [
                (self.buttons["depth_contours"].x, self.buttons["depth_contours"].y,
                 ClickType.SINGLE, "clicking depth contours toggle"),
            ],
            "toggle_bearing_line": [
                (self.buttons["bearing_line"].x, self.buttons["bearing_line"].y,
                 ClickType.SINGLE, "clicking bearing line toggle"),
            ],
        }

        if target not in plans:
            return []

        return [
            MouseAction(x=x, y=y, click=click, description=desc,
                        pre_delay=0.3, post_delay=0.5)
            for x, y, click, desc in plans[target]
        ]


# ---------------------------------------------------------------------------
# Chart interpreter — reading depth and predictor data
# ---------------------------------------------------------------------------

class ChartInterpreter:
    """Interprets chart data and answers navigation queries.

    Understands:
    - Depth contour colors (blue=shallow, white=safe, etc.)
    - The 5-minute predictor line
    - Speed/heading extrapolation
    - "Are we going to remain deep enough?" queries

    Every interpretation becomes a ChartTile for future instant answers.
    """

    # Depth contour color meanings (standard NOAA chart colors)
    CONTOUR_COLORS = {
        "dark_blue": "shallow water (< 6 fathoms)",
        "light_blue": "transition zone (6-12 fathoms)",
        "cyan": "moderate depth (12-30 fathoms)",
        "white": "safe depth (> 30 fathoms)",
        "green": "tidal zone / drying area",
        "brown": "land",
        "pink": "restricted area",
    }

    def __init__(self, store: TileStore):
        self.store = store
        self._seed_chart_tiles()

    def _seed_chart_tiles(self) -> None:
        """Pre-load basic chart knowledge as tiles."""
        seeds = [
            ("what do blue contours mean", "Blue contours indicate shallow water, typically less than 6 fathoms"),
            ("what do white areas mean", "White areas indicate safe depth, typically greater than 30 fathoms"),
            ("what is the predictor line", "The predictor line shows where the boat will be in 5 minutes at current speed and heading"),
            ("what are depth contours", "Depth contours are lines connecting points of equal depth, shown in color-coded bands on the chart"),
        ]
        for pattern, answer in seeds:
            existing = self.store.find_by_pattern(pattern)
            if not existing:
                tile = ChartTile(
                    input_pattern=pattern,
                    output_action=answer,
                    confidence=1.0,
                    verifier=Verifier.MODEL,
                    source="system",
                )
                self.store.add(tile)

    def interpret_depth(self, chart_data: ChartData) -> str:
        """Interpret the current depth situation from chart data."""
        current = chart_data.current_depth
        if current is None:
            return "No depth data available"

        parts = [f"Current depth: {current:.1f} fathoms"]

        # Predict 5 minutes ahead
        pred = predict_position(chart_data, 5)
        pred_depth = chart_data.depth_at(pred["lat"], pred["lon"])
        if pred_depth is not None:
            parts.append(f"In 5 minutes (predictor): {pred_depth:.1f} fathoms")
            if pred_depth < current:
                parts.append(f"  ⚠ Shoaling — losing {current - pred_depth:.1f} fathoms")
            elif pred_depth > current:
                parts.append(f"  Deepening by {pred_depth - current:.1f} fathoms")

        return "\n".join(parts)

    def answer_query(self, question: str, chart_data: ChartData) -> str:
        """Answer a natural language chart/navigation query.

        Routes through tiles first (instant if compiled), then uses
        chart intelligence for the answer.
        """
        # Try tile store first
        existing = self.store.find_by_pattern(question.lower())
        if existing and existing[0].confidence >= 0.9:
            tile = existing[0]
            tile.record_use(True)
            return tile.output_action

        # Parse the question and generate answer
        answer = answer_depth_query(question, chart_data)

        # Create a tile from this interaction
        tile = ChartTile(
            input_pattern=question.lower(),
            output_action=answer,
            confidence=0.7,
            verifier=Verifier.MODEL,
            source="cocapn",
        )
        self.store.add(tile)
        return answer

    def check_depth_ahead(self, chart_data: ChartData, minutes: float = 10.0,
                          min_required: float = 30.0) -> dict:
        """Check if the boat will remain deep enough for the next N minutes.

        Returns dict with:
        - safe: bool
        - min_depth: float
        - min_depth_at: float (minutes from now)
        - details: str
        """
        result = min_depth_along_route(chart_data, minutes)
        min_depth = result["min_depth"]
        when = result["min_depth_at_minutes"]

        safe = min_depth >= min_required
        details = (
            f"Minimum depth in next {minutes:.0f} minutes: {min_depth:.1f} fathoms "
            f"(at {when:.1f} minutes ahead)"
        )
        if not safe:
            details += f" — ⚠ BELOW required {min_required:.0f} fathoms"

        return {
            "safe": safe,
            "min_depth": min_depth,
            "min_depth_at_minutes": when,
            "details": details,
        }

    def describe_contour_color(self, color: str) -> str:
        """Describe what a contour color means."""
        return self.CONTOUR_COLORS.get(color, f"Unknown contour color: {color}")


# ---------------------------------------------------------------------------
# Cocapn chatbot — the boat's AI assistant
# ---------------------------------------------------------------------------

class CocapnChatbot:
    """The Cocapn — a persistent AI assistant that lives on the boat.

    Routes captain input through the tile system (compiled → fallback),
    can query chart data, can output mouse actions to the nav computer,
    and records every interaction as a tile for future compilation.

    Usage:
        cocapn = CocapnChatbot()
        response = cocapn.chat("are we going to remain deep enough for the next 10 minutes?")
        print(response.text)  # "Minimum depth in next 10 minutes: 42.3 fathoms..."

        # Captain can review pending items
        cocapn.list_pending()  # Show items needing review
        cocapn.confirm(0)      # Confirm first pending item
        cocapn.correct(1, "correct answer")  # Correct second pending item
    """

    def __init__(self, store: TileStore | None = None,
                 nav: NavComputer | None = None,
                 chart_data: ChartData | None = None):
        self.store = store if store is not None else TileStore()
        self.nav = nav if nav is not None else NavComputer()
        self.chart_data = chart_data if chart_data is not None else ChartData()
        self.finder = RigidFinder(self.store)
        self.router = Router(self.store, self.finder, fallback_fn=self._fallback)
        self.interpreter = ChartInterpreter(self.store)
        self._conversation: list[dict] = []
        self._review_queue: list[dict] = []
        self._aborted = False

    def chat(self, text: str) -> dict:
        """Process captain input and return a response.

        Returns dict with:
        - text: str (the response)
        - decision: RouteDecision
        - tile_id: str | None (tile created or matched)
        - mouse_actions: list[MouseAction] (if nav interaction needed)
        - confidence: float
        """
        self._aborted = False
        self._conversation.append({"role": "captain", "text": text})

        # Check if this is a nav computer command
        nav_actions = self._parse_nav_command(text)
        if nav_actions is not None:
            return self._handle_nav_command(text, nav_actions)

        # Check if this is a chart/navigation query
        chart_result = self._try_chart_query(text)
        if chart_result is not None:
            return chart_result

        # Route through tile system
        decision, result = self.router.route(text)

        response = {
            "text": "",
            "decision": decision,
            "tile_id": None,
            "mouse_actions": [],
            "confidence": 0.0,
        }

        if decision == RouteDecision.COMPILED and result:
            response["text"] = result.get("action", "")
            response["tile_id"] = result.get("tile_id")
            response["confidence"] = 1.0
        elif decision == RouteDecision.NEGATIVE:
            response["text"] = f"Blocked: {result.get('reason', 'unknown')}"
            response["confidence"] = 1.0
        elif decision == RouteDecision.AMBIGUOUS:
            response["text"] = result.get("message", "Please confirm")
            response["confidence"] = result.get("confidence", 0.5)
            self._review_queue.append({"input": text, "result": result})
        elif decision == RouteDecision.FALLBACK and result:
            if isinstance(result, dict):
                response["text"] = result.get("action", str(result))
            else:
                response["text"] = str(result)
            response["confidence"] = 0.0

        self._conversation.append({"role": "cocapn", "text": response["text"]})
        return response

    def _parse_nav_command(self, text: str) -> list[MouseAction] | None:
        """Check if the input is a nav computer command and return mouse actions."""
        t = text.lower().strip()

        nav_commands = {
            r"toggle radar|turn on radar|turn off radar|radar (overlay|on|off)": "toggle_radar",
            r"zoom in|magnify|closer": "zoom_in",
            r"zoom out|wider|back out": "zoom_out",
            r"toggle predictor|predictor (line|on|off)|show predictor|hide predictor": "toggle_predictor",
            r"toggle (depth|contours)|depth (contours|on|off)|show depth|hide depth": "toggle_depth_contours",
            r"bearing (line|on|off)|toggle bearing": "toggle_bearing_line",
        }

        for pattern, target in nav_commands.items():
            if re.search(pattern, t):
                return self.nav.build_mouse_plan(target)

        return None

    def _handle_nav_command(self, text: str, actions: list[MouseAction]) -> dict:
        """Execute a nav computer command via mouse actions."""
        results = []
        for action in actions:
            if self._aborted:
                results.append("ABORTED by captain")
                break
            result = self.nav.accept_mouse(action)
            results.append(result)

        # Create a tile for this command
        tile = CommandTile(
            input_pattern=text.lower().strip(),
            output_action=f"nav:{results[0] if results else 'no action'}",
            confidence=0.9,
            verifier=Verifier.MODEL,
            source="cocapn",
            regex_pattern=r"" + "|".join(
                r.split("|")[0] for r in [
                    r"toggle radar", r"zoom in", r"zoom out",
                    r"toggle predictor", r"toggle depth", r"toggle bearing"
                ]
            ),
        )
        tile_id = self.store.add(tile)

        response_text = "; ".join(results)
        self._conversation.append({"role": "cocapn", "text": response_text})

        return {
            "text": response_text,
            "decision": RouteDecision.COMPILED,
            "tile_id": tile_id,
            "mouse_actions": actions,
            "confidence": 0.9,
        }

    def _try_chart_query(self, text: str) -> dict | None:
        """Try to handle as a chart/navigation query."""
        t = text.lower().strip()

        chart_patterns = [
            r"(how deep|what.depth|current depth|how shallow)",
            r"(remain|stay) deep enough",
            r"(shallowest|min depth|minimum depth)",
            r"depth (along|on) (our|the) (course|route|path)",
            r"predictor",
            r"(what|which) (do|does) .+ (contours?|colors?|lines?) (mean|show)",
            r"(going to|will we) (cross|hit|reach|pass)",
        ]

        is_chart = any(re.search(p, t) for p in chart_patterns)
        if not is_chart:
            return None

        answer = self.interpreter.answer_query(text, self.chart_data)

        # Find the tile we just created
        tiles = self.store.find_by_pattern(text.lower())
        tile_id = tiles[0].tile_id if tiles else None

        self._conversation.append({"role": "cocapn", "text": answer})

        return {
            "text": answer,
            "decision": RouteDecision.COMPILED,
            "tile_id": tile_id,
            "mouse_actions": [],
            "confidence": 0.7,
        }

    def _fallback(self, text: str) -> dict:
        """Fallback handler when no tile matches."""
        return {
            "action": f"I'm not sure about '{text}'. I'll log this for review.",
            "input": text,
        }

    def abort(self) -> None:
        """Abort the current mouse action sequence.

        The captain calls this when they see something wrong on the nav display.
        """
        self._aborted = True

    # --- Review mode ---

    def list_pending(self) -> list[dict]:
        """List all pending items needing captain review."""
        router_pending = [
            {"source": "router", "index": i, **p}
            for i, p in enumerate(self.router._pending)
        ]
        review_pending = [
            {"source": "review", "index": i, **r}
            for i, r in enumerate(self._review_queue)
        ]
        return router_pending + review_pending

    def confirm(self, index: int) -> str | None:
        """Confirm a pending item (captain says it's correct)."""
        if index < len(self.router._pending):
            tile_id = self.router.confirm_pending(index, correct=True)
            return tile_id
        return None

    def correct(self, index: int, correction: str) -> str | None:
        """Correct a pending item (captain provides the right answer)."""
        if index < len(self.router._pending):
            tile_id = self.router.confirm_pending(index, correct=False, correction=correction)

            # Also create a positive tile with the correction
            if tile_id:
                pending = None
                correct_tile = Tile(
                    tile_type=TileType.COMMAND,
                    input_pattern="",
                    output_action=correction,
                    confidence=0.9,
                    verifier=Verifier.CAPTAIN,
                    source="captain",
                )
                self.store.add(correct_tile)

            return tile_id
        return None

    def teach(self, pattern: str, action: str) -> str:
        """Captain teaches the Cocapn a new command during a review session.

        Creates a high-confidence tile directly from captain instruction.
        """
        tile = CommandTile(
            input_pattern=pattern.lower(),
            output_action=action,
            confidence=0.95,
            verifier=Verifier.CAPTAIN,
            source="captain",
        )
        tile_id = self.store.add(tile)

        # Try to compile immediately if we have enough confidence
        self.finder.try_compile(tile)

        return tile_id

    def update_chart_data(self, chart_data: ChartData) -> None:
        """Update the chart data (e.g., from a fresh screen capture)."""
        self.chart_data = chart_data

    @property
    def conversation_history(self) -> list[dict]:
        """Return the full conversation history."""
        return list(self._conversation)

    @property
    def stats(self) -> dict:
        """Return chatbot statistics."""
        return {
            "total_tiles": len(self.store),
            "compiled": self.finder.compiled_count,
            "pending_reviews": len(self.list_pending()),
            "conversation_length": len(self._conversation),
            "router": self.router.stats,
        }
