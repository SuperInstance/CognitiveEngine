# Cocapn — The Chatbot That Learns Your Boat

> Cocapn sits between you and the navigation computer, learning as it goes.

---

## What Is Cocapn?

Cocapn is the conversational interface to LucidDreamer. It's a chatbot that:

1. **Understands voice commands** and translates them into actions
2. **Learns from interactions** — every conversation creates tiles
3. **Remembers what it learns** — knowledge persists across sessions
4. **Controls the navigation computer** via mouse output (deliberate, visual, stoppable)
5. **Reads chart screens** via screen capture and learns what things mean

Think of Cocapn as a really smart deckhand who sits at the nav station, watches the screens, and learns what everything means over time. Eventually, they can do most of the routine stuff without asking.

---

## Mouse Output to Navigation Computer

Cocapn doesn't have direct API access to your ECDIS (Electronic Chart Display and Information System). Instead, it controls the nav computer through **mouse movements and clicks** — just like a human would.

This is deliberate:

- **Visual**: You can see exactly what Cocapn is doing on screen
- **Stoppable**: You can grab the mouse at any time
- **Deliberate**: Every action is visible and interruptible
- **Universal**: Works with any ECDIS software, no API needed

```
  ┌─────────────────────────────────────────────┐
  │          Cocapn Control Flow                 │
  │                                              │
  │  "toggle radar overlay"                      │
  │         │                                    │
  │         ▼                                    │
  │  ┌───────────┐    ┌──────────────┐           │
  │  │  Router   │───▶│  Tile Match  │           │
  │  └───────────┘    └──────┬───────┘           │
  │                          │                   │
  │                          ▼                   │
  │  ┌──────────────────────────────────────┐    │
  │  │  Mouse Action:                       │    │
  │  │  1. Move to (x:1200, y:45)           │    │
  │  │  2. Click [Layer Menu]               │    │
  │  │  3. Move to (x:1200, y:180)          │    │
  │  │  4. Click [Radar Overlay checkbox]   │    │
  │  └──────────────────────────────────────┘    │
  │                          │                   │
  │                          ▼                   │
  │  ┌──────────────────────────────────────┐    │
  │  │  Screenshot verification:             │    │
  │  │  "Radar overlay is now ON"            │    │
  │  └──────────────────────────────────────┘    │
  └─────────────────────────────────────────────┘
```

### Example: "Toggle Radar Overlay"

```python
# After compilation, this sequence is stored as a CommandTile
from luciddreamer.tiles import CommandTile

tile = CommandTile(
    input_pattern="toggle radar overlay",
    output_action="mouse_sequence:radar_toggle",
    regex_pattern=r"^(toggle|show|turn on|turn off) radar (overlay)?$",
    metadata={
        "mouse_actions": [
            {"type": "move", "x": 1200, "y": 45},
            {"type": "click", "button": "left"},
            {"type": "wait", "ms": 200},
            {"type": "move", "x": 1200, "y": 180},
            {"type": "click", "button": "left"},
        ],
        "verification": "check_screenshot:radar_overlay_enabled",
    },
    confidence=0.95,
)
```

The first time you say "toggle radar overlay", Cocapn watches you do it. After a few repetitions (and captain verification), it compiles into a deterministic mouse sequence.

---

## Learning from Screen Captures

Cocapn can **read the chart screen** and learn what things mean. This is how it builds chart intelligence without needing direct access to chart data.

### Example: "What do the blue contours mean?"

```
  Captain: "What do the blue contours mean?"
  
  Cocapn:
    1. [Captures screen]
    2. [Identifies blue contour regions]
    3. [Checks existing tiles — no match]
    4. [Asks model for interpretation]
    5. "Those blue contours typically indicate shallow water
        depth lines. In this area, they appear to be the
        5-fathom contour. Would you like me to remember this?"
  
  Captain: "Yes, those are the 5-fathom lines near Dutch."
  
  Cocapn:
    1. [Creates ChartTile]
    2. [Stores knowledge for next time]
    3. "Got it. I'll remember that blue contours in the Dutch
        Harbor approaches are 5-fathom lines."
```

```python
from luciddreamer.tiles import ChartTile, Verifier

# The tile that gets created from this interaction
tile = ChartTile(
    input_pattern="blue_contour_dutch_approaches",
    output_action="depth_info:5_fathom_contour",
    region="Dutch Harbor approaches",
    depth_range=(4.5, 5.5),
    features=["5-fathom contour", "shallow water indicator"],
    confidence=0.85,
    verifier=Verifier.CAPTAIN,
    source="edge",
    metadata={
        "screen_region": "center_left_quadrant",
        "color": "blue",
        "learned_from": "screen_capture",
    },
)
store.add(tile)
```

### Example: "Are we going to remain deep enough for the next 10 minutes?"

This is a **predictive chart query** — Cocapn looks at the current position, reads the chart ahead, and projects depth along the projected course.

```
  Captain: "Are we going to remain deep enough for the next 10 minutes?"
  
  Cocapn:
    1. [Captures current chart screen]
    2. [Reads current position from GPS/NMEA]
    3. [Projects course line 10 minutes ahead]
    4. [Interprets depth contours along projected path]
    5. "At current speed and heading, you'll cross the 5-fathom
        contour in about 7 minutes. After that, it deepens again
        to about 12 fathoms. You're fine for now, but I'll flag
        when you're 2 minutes from shallow."
  
  Captain: "Good. Remind me at 5 minutes."
  
  Cocapn:
    1. [Creates alert tile]
    2. [Sets timer based on current speed/heading]
    3. "Will do. Shallow water warning in 5 minutes."
```

```python
from luciddreamer.tiles import ChartTile

# The predictive tile
tile = ChartTile(
    input_pattern="depth_check_ahead_10min",
    output_action="predictive_depth_alert",
    region="current_route_projection",
    depth_range=(5.0, 12.0),
    features=["5-fathom crossing at ~7 min", "deep water after"],
    confidence=0.70,  # TENTATIVE — predictive, needs verification
    metadata={
        "prediction_minutes": 10,
        "shallow_crossing_time": 7,
        "shallow_depth": 5.0,
        "deep_depth": 12.0,
        "current_speed": 8.5,  # knots
        "current_heading": 245,
    },
)
store.add(tile)
```

### The 5-Minute Predictor Line

The **5-minute predictor** is a visual line on the chart showing where you'll be in 5 minutes at current speed and heading. Cocapn uses this (or calculates its own) to answer depth-ahead questions.

```
  ┌─────────────────────────────────────────────────┐
  │                    CHART DISPLAY                  │
  │                                                  │
  │         ▓▓▓▓▓▓▓                                 │
  │       ▓▓ 5fm ▓▓     ──── 5-minute predictor     │
  │      ▓▓ contour▓▓         (your projected path) │
  │         ▓▓▓▓▓▓▓       ╱                         │
  │                      ╱                           │
  │                    ╱  ← You're here              │
  │                  ★                               │
  │                                                  │
  │         ████  Deep water (> 20 fm)               │
  │         ▓▓▓▓  Shallow (5 fm contour)             │
  └─────────────────────────────────────────────────┘
```

---

## How Cocapn Tiles Chart Knowledge

Every chart interaction creates tiles that build up over time:

```
  Interaction                     Tile Created
  ─────────────────────────────   ──────────────────────────────
  "What's that blue area?"        ChartTile: blue = shallow
  "How deep there?"               ChartTile: depth query pattern
  "Mark that rock"                ChartTile: hazard annotation
  "What's our clearance?"         ChartTile: under keel check
  "Any wrecks on this route?"     ChartTile: wreck database query
  
  After 20 interactions:
  ┌──────────────────────────────────────────────┐
  │  Chart Coverage:                              │
  │  depth_queries    ████████████████░░░░  80%   │
  │  contour_reading  ██████████░░░░░░░░░░  50%   │
  │  hazard_checks    ████████░░░░░░░░░░░░  40%   │
  │  route_queries    ████░░░░░░░░░░░░░░░░  20%   │
  └──────────────────────────────────────────────┘
```

---

## Simulation of Alternative Wordings

Cocapn can **simulate alternative phrasings** to expand tile coverage without needing the captain to say every variation. This is done during downtime (transit, at anchor) when the model has spare cycles.

### How It Works

```python
# The captain said: "turn port 10 degrees"
# Cocapn simulates alternatives:
alternatives = [
    "come left 10 degrees",
    "port 10",
    "turn left ten degrees",
    "port ten",
    "hard to port 10",
    "left hand turn 10 degrees",
    "helm port 10",
]

# Each alternative is checked against existing tiles
# If no match, create a TENTATIVE tile linking to the original
for alt in alternatives:
    existing = store.find_by_pattern(alt)
    if not existing:
        tile = CommandTile(
            input_pattern=alt,
            output_action="helm_port_10",
            parent_tile_id=original_tile_id,  # Links to "turn port 10 degrees"
            confidence=0.50,  # TENTATIVE — needs verification
            source="simulation",
            metadata={"simulated_from": "turn port 10 degrees"},
        )
        store.add(tile)
```

### Simulation Strategy

```
  ┌────────────────────────────────────────────────────┐
  │            Simulation Pipeline                      │
  │                                                    │
  │  1. Take a compiled tile                            │
  │  2. Generate alternative phrasings (model-powered)  │
  │  3. Check each against existing tiles               │
  │  4. New variations → TENTATIVE tiles (0.5 conf)    │
  │  5. Next time captain uses one → auto-verified      │
  │  6. After enough uses → compiled                    │
  │                                                    │
  │  Result: broader coverage without more captain time │
  └────────────────────────────────────────────────────┘
```

### When to Simulate

Good times to run simulations:
- During transit (plenty of compute available)
- At anchor (system is idle)
- Before a trip (prepare for expected commands)
- During captain review (suggest alternatives for approval)

---

## Complete Example Session

Here's a full Cocapn session from start to finish:

```python
from luciddreamer.tiles import TileStore, CommandTile, ChartTile, Verifier
from luciddreamer.compiler import RigidFinder
from luciddreamer.router import Router, RouteDecision

# Setup
store = TileStore()
finder = RigidFinder(store)

def gemma_fallback(text):
    """Local Gemma 3 model for fallback."""
    return {"action": "unknown", "raw": text}

router = Router(store=store, finder=finder, fallback_fn=gemma_fallback)

# ── Session Start ──────────────────────────────────────────────

# Captain says something
decision, result = router.route("toggle radar overlay")
print(f"[{decision.value}] {result}")
# First time: FALLBACK — model has to figure it out

# Captain watches Cocapn attempt, confirms it worked
router.confirm_pending(0, correct=True)

# Later, captain says it again
decision, result = router.route("toggle radar overlay")
print(f"[{decision.value}] {result}")
# This time: COMPILED (if enough repetitions) or fuzzy match

# Captain asks about chart
decision, result = router.route("what do the blue contours mean")
print(f"[{decision.value}] Chart query")
# FALLBACK — Cocapn captures screen, interprets, responds

# Captain confirms the interpretation
tile = ChartTile(
    input_pattern="blue_contours_mean_shallow",
    output_action="explain:shallow_water_contours",
    region="current_view",
    confidence=0.85,
    verifier=Verifier.CAPTAIN,
)
store.add(tile)

# Next time someone asks about blue contours — instant answer
decision, result = router.route("what are those blue lines")
print(f"[{decision.value}] Learned from previous interaction")

# End of session: compile what we can
compiled = finder.compile_all()
print(f"Session complete. Compiled {len(compiled)} new commands.")
print(f"Pending review: {router.pending_count}")
```

---

## Next Steps

- [GETTING-STARTED.md](GETTING-STARTED.md) — Set up Cocapn for the first time
- [TILES.md](TILES.md) — How tiles store Cocapn's knowledge
- [MARITIME-EXAMPLES.md](MARITIME-EXAMPLES.md) — More real-world Cocapn scenarios
