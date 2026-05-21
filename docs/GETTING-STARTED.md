# Getting Started with LucidDreamer

> From zero to a thinking boat — a complete walkthrough for mariners.

LucidDreamer is a maritime intelligence system that learns your boat. It starts as a blank slate and, over the course of a fishing season, compiles your voice commands, fish sorting decisions, and chart knowledge into fast, deterministic code that runs without an internet connection.

Think of it like training a green deckhand: at first they need constant supervision, but by the end of the season they know the routine cold.

---

## Table of Contents

1. [What You Need](#what-you-need)
2. [Installation](#installation)
3. [Your First Tile](#your-first-tile)
4. [Building Up Tile Coverage](#building-up-tile-coverage)
5. [The Captain Review Cycle](#the-captain-review-cycle)
6. [Compiling Your First Command](#compiling-your-first-command)
7. [The Bathymetric Map](#the-bathymetric-map)
8. [Deploying to Edge](#deploying-to-edge-gemma-3-1b-it)
9. [Fish Sorting Setup](#fish-sorting-setup)
10. [Chart Intelligence Setup](#chart-intelligence-setup)
11. [Troubleshooting](#troubleshooting)

---

## What You Need

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **Boat computer** | Raspberry Pi 4 (4GB) | Intel NUC i5, 16GB RAM |
| **Microphone** | Any USB mic | Noise-cancelling headset mic |
| **Camera** | USB webcam (2MP) | Industrial USB3 camera (5MP+) |
| **Display** | 7" HDMI display | 10" sunlight-readable display |
| **GPS/NMEA** | USB GPS puck | NMEA 2000 network bridge |
| **Internet** | Needed for setup only | Starlink for cloud sync |

### Software

- **Python 3.10+** (the boat computer needs it)
- **pip** (Python package manager)
- **Gemma 3 1B-IT** (for edge inference — we'll get to this)
- **Optional:** CUDA-capable GPU for faster vision processing

### Knowledge

You should know:
- How to open a terminal (command line)
- Basic boat operations (you're a mariner — you've got this)
- No AI or programming experience required

---

## Installation

### Step 1: Install LucidDreamer

```bash
pip install luciddreamer
```

That's it. All the core modules come along:

```
luciddreamer/
├── tiles.py        # The tile system (knowledge storage)
├── compiler.py     # Compiles tiles to fast regex
├── bathymetry.py   # Coverage visualization
└── router.py       # Routes inputs to compiled or model
```

### Step 2: Verify the Installation

```python
from luciddreamer.tiles import Tile, TileStore, TileType
from luciddreamer.compiler import RigidFinder
from luciddreamer.router import Router
from luciddreamer.bathymetry import BathymetricMap

print("LucidDreamer ready to go.")
```

If you see `LucidDreamer ready to go.` with no errors, you're set.

---

## Your First Tile

A **tile** is a single piece of knowledge. Every command you give the system becomes a tile. Let's create one.

```python
from luciddreamer.tiles import CommandTile, TileStore

# Create a tile store (this is your boat's memory)
store = TileStore()

# Record your first voice command: "turn port 10 degrees"
tile = CommandTile(
    input_pattern="turn port 10 degrees",
    output_action="helm_port_10",
    confidence=0.5,           # Starting low — we don't trust it yet
    source="captain",         # You said it
    vessel="F/V Northern Star",
)

tile_id = store.add(tile)
print(f"Created tile: {tile_id}")
print(f"Confidence: {tile.confidence} ({tile.confidence_class.value})")
```

Output:
```
Created tile: a3f7b2c9d4e5f6a1
Confidence: 0.5 (ambiguous)
```

At 50% confidence, this tile is in the **AMBIGUOUS** zone — the system won't execute it automatically. That's by design. You wouldn't hand the helm to someone you just met either.

### What Just Happened?

1. You said "turn port 10 degrees"
2. The system recorded it as a `CommandTile`
3. It got a unique ID based on its content
4. Confidence started at 0.5 (ambiguous)
5. It's stored in the `TileStore` — your boat's memory

---

## Building Up Tile Coverage

One tile isn't enough. The system needs to see the same pattern multiple times before it trusts it. Let's add more variations:

```python
from luciddreamer.tiles import CommandTile, Verifier

# The captain says similar things over a few trips
commands = [
    ("turn port 10 degrees", "helm_port_10"),
    ("turn port 10 degrees", "helm_port_10"),     # Same command, trip 2
    ("turn port 15 degrees", "helm_port_15"),
    ("turn starboard 5 degrees", "helm_starboard_5"),
    ("turn port 10 degrees", "helm_port_10"),     # Trip 3, same command
]

for text, action in commands:
    # Check if we already have this pattern
    existing = store.find_by_pattern(text)
    if existing:
        # Record that it was used correctly again
        existing[0].record_use(correct=True)
        existing[0].verifier = Verifier.CAPTAIN
        print(f"  Reinforced: {text} → {existing[0].confidence:.2f}")
    else:
        # New pattern
        tile = CommandTile(
            input_pattern=text,
            output_action=action,
            confidence=0.6,
            source="captain",
            vessel="F/V Northern Star",
        )
        store.add(tile)
        print(f"  New tile: {text} → {action}")
```

Output:
```
  New tile: turn port 10 degrees → helm_port_10
  Reinforced: turn port 10 degrees → 0.62
  New tile: turn port 15 degrees → helm_port_15
  New tile: turn starboard 5 degrees → helm_starboard_5
  Reinforced: turn port 10 degrees → 0.64
  Reinforced: turn port 10 degrees → 0.66
```

Each correct use bumps confidence by +0.02. After enough repetitions, the tile crosses the compile threshold and becomes **deterministic** — no model needed.

### The Confidence Ladder

```
100%  COMPILED    ████████████████████  Silent execution (no model)
 95%  VERIFIED    ███████████████████░  Execute + brief confirmation
 70%  TENTATIVE   ██████████████░░░░░░  Execute tentatively, ask
 50%  AMBIGUOUS   ██████████░░░░░░░░░░  Don't execute, ask captain
  0%  UNKNOWN     ░░░░░░░░░░░░░░░░░░░░  Batch for later review
```

---

## The Captain Review Cycle

Not everything the system hears is correct. The **captain review cycle** is how you correct mistakes and build trust.

```python
from luciddreamer.router import Router

# Set up the router with a fallback function
def model_fallback(text):
    """This would be your local Gemma model in production."""
    # Simulating model inference
    return {"action": "helm_port_10", "raw_response": "turning port 10 degrees"}

router = Router(store=store, finder=RigidFinder(store), fallback_fn=model_fallback)

# Captain says something new
decision, result = router.route("come port easy")
print(f"Decision: {decision.value}")
print(f"Result: {result}")

# This is a FALLBACK — the model had to think about it
# It's now pending for captain review
print(f"Pending reviews: {router.pending_count}")
```

### Reviewing Pending Items

At the end of a watch, you review what the model did:

```python
# Review item 0 — model got it right
tile_id = router.confirm_pending(0, correct=True)
print(f"Confirmed! Created tile: {tile_id}")

# If the model got it WRONG:
# tile_id = router.confirm_pending(0, correct=False, correction="helm_port_5")
```

When you confirm a correct response, it becomes a new tile at 0.8 confidence. When you correct it, it becomes a **correction tile** at 0.9 confidence — corrections are weighted heavily because the captain explicitly intervened.

---

## Compiling Your First Command

After enough uses and positive verifications, a tile can be **compiled** — converted from something the model has to think about into a simple regex pattern that runs instantly.

```python
from luciddreamer.compiler import RigidFinder

finder = RigidFinder(store)

# Try to compile all eligible tiles
compiled = finder.compile_all()
print(f"Compiled {len(compiled)} commands")

for cmd in compiled:
    print(f"  {cmd.pattern} → {cmd.action}")
```

### What Makes a Tile Compilable?

The compiler checks four things:

1. **Confidence ≥ 97.5%** — the `COMPILE_THRESHOLD` from dream.rs experiments
2. **Used 3+ times** — not a one-off
3. **Error rate < 5%** — stable behavior
4. **No recent corrections** — no instability in the last 10 uses

### Auto-Generated Regex

The compiler can generate regex patterns from your examples:

```python
from luciddreamer.compiler import RigidFinder

finder = RigidFinder(store)

# "turn port 10 degrees" becomes:
# ^turn port (?P<n>\d+) degrees?$
pattern = finder._auto_pattern("turn port 10 degrees")
print(pattern)
# Output: ^turn port (?P<n>\d+) degrees?$
```

Now "turn port 5 degrees", "turn port 20 degrees", etc. all match without the model.

---

## The Bathymetric Map

The **bathymetric map** shows you how well the system knows your boat — visualized like an ocean depth chart.

```python
from luciddreamer.bathymetry import BathymetricMap

bathy = BathymetricMap()
bathy.build_from_store(store)

# See your coverage
print(bathy.render())
```

Example output after a few trips:

```
Bathymetric Coverage Map
============================================================

  turn            ██████████████████░░░░░░░░░░░░░░░░░░░░░░░  45.0%
  come            ████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  10.0%
  steady          ████████████████████████████████████████░░  95.0%
  hard            ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.0%

  █ = compiled (zero inference)  ░ = needs model
```

**Shallow water (█)** = the system knows this cold. Compiled, zero inference.
**Deep water (░)** = still exploring. The model has to think.

The goal over a season: fill in the chart until most commands run without the model.

---

## Deploying to Edge (Gemma 3 1B-IT)

LucidDreamer is designed to run **offline on your boat**. Here's how to set up the edge model.

### Why a Small Model?

You're at sea. Internet is expensive or nonexistent. The edge model (Gemma 3 1B-IT) is small enough to run on a Raspberry Pi but smart enough to handle the cases your compiled tiles don't cover.

### The Deployment Pipeline

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Cloud     │  sync   │    Boat      │  route   │   Action    │
│  Training   │───────▶ │   Computer   │────────▶ │   (helm,    │
│  & Review   │  tiles  │  (Edge)      │          │   sort,     │
└─────────────┘         └──────────────┘          │   chart)    │
    Big GPU                 Small GPU              └─────────────┘
    Full model              Gemma 3 1B
```

### Setting Up Gemma 3

```python
# On your boat computer
from luciddreamer.router import Router
from luciddreamer.compiler import RigidFinder
from luciddreamer.tiles import TileStore

# Load your compiled tiles (exported from cloud)
store = TileStore()
with open("tiles_export.json") as f:
    count = store.import_json(f.read())
    print(f"Loaded {count} tiles")

# Compile everything that's ready
finder = RigidFinder(store)
compiled = finder.compile_all()
print(f"Compiled {len(compiled)} commands")

# Set up Gemma 3 as fallback
def gemma_fallback(text):
    """In production, this calls your local Gemma model."""
    # Placeholder — replace with actual ollama/transformers call
    import subprocess
    result = subprocess.run(
        ["ollama", "run", "gemma3:1b", text],
        capture_output=True, text=True
    )
    return {"action": "parse_model_output", "raw": result.stdout}

router = Router(store=store, finder=finder, fallback_fn=gemma_fallback)
```

### How Routing Works on Edge

```
Input: "turn port 10 degrees"
  │
  ├─ Check compiled tiles? ──→ MATCH! ──→ Execute instantly (free)
  │
  ├─ Check negative tiles? ──→ BLOCKED ──→ "Don't do that"
  │
  ├─ Fuzzy match existing? ──→ 70%+ match ──→ Execute + confirm
  │
  └─ Fallback to Gemma? ──→ Model thinks ──→ Log for later review
```

Most inputs hit the compiled path. The model only fires for new situations.

---

## Fish Sorting Setup

Fish sorting uses **vision tiles** — the camera sees a fish and the system classifies it.

### Step 1: Connect a Camera

```python
from luciddreamer.tiles import VisionTile, TileStore

store = TileStore()

# Record your first fish classification
tile = VisionTile(
    input_pattern="photo_2024_sort_001.jpg",
    output_action="classify:halibut",
    species="Pacific Halibut",
    hold_number=3,
    photo_path="/photos/sort/photo_2024_sort_001.jpg",
    weight_estimate=45.2,
    confidence=0.5,
    source="deck_crew",
    verifier=Verifier.DECK_CREW,
    vessel="F/V Northern Star",
)

store.add(tile)
```

### Step 2: Train Through Use

```python
# Deck crew confirms or corrects each classification
tile.record_use(correct=True)    # "Yep, that's a halibut"
tile.record_use(correct=True)    # Another correct call
tile.record_use(correct=False)   # "That was actually a flounder!"

print(f"Confidence after corrections: {tile.confidence:.2f}")
# Confidence drops sharply on corrections (-0.1) and rises slowly (+0.02)
```

### Step 3: Build Species Coverage

Over the season, you build a library:

```python
species = ["Pacific Halibut", "Sablefish", "Pacific Cod", "Yellowfin Sole",
           "Rock Sole", "Rex Sole", "Arrowtooth Flounder"]

for sp in species:
    tile = VisionTile(
        input_pattern=f"species:{sp}",
        output_action=f"classify:{sp.lower().replace(' ', '_')}",
        species=sp,
        confidence=0.0,  # Starts unknown
        source="cloud",
    )
    store.add(tile)

print(f"Tracking {len(store)} tiles across {len(species)} species")
```

---

## Chart Intelligence Setup

Chart tiles let the system understand electronic navigation charts (ENCs).

```python
from luciddreamer.tiles import ChartTile

# Record chart knowledge
tile = ChartTile(
    input_pattern="blue_contour_5_fathom",
    output_action="depth_contour:5_fathoms",
    region="Dutch Harbor approaches",
    depth_range=(4.5, 5.5),
    features=["5-fathom contour", "rock pinnacle at 58-12.3N 166-30.2W"],
    confidence=0.7,
    source="captain",
    vessel="F/V Northern Star",
)

store.add(tile)
```

### Asking Chart Questions

```python
# Route a chart question
decision, result = router.route("are we going to remain deep enough for the next 10 minutes?")
print(f"Decision: {decision.value}")
# On first ask: FALLBACK (model has to think)
# After 10 similar asks: COMPILED (instant response)
```

---

## Troubleshooting

### "No module named 'luciddreamer'"

```bash
pip install luciddreamer
```

If that doesn't work, make sure you're using Python 3.10+:

```bash
python --version
```

### Tiles Not Compiling

Check the four requirements:
1. Confidence ≥ 0.975 (use `tile.confidence`)
2. Used 3+ times (use `tile.times_used`)
3. Error rate < 5% (use `tile.times_corrected / tile.times_used`)
4. The tile must be a `COMMAND` type

```python
for tile in store:
    print(f"{tile.input_pattern}: conf={tile.confidence:.3f}, "
          f"uses={tile.times_used}, corrections={tile.times_corrected}")
```

### Coverage Stuck at Low Numbers

This is normal early in the season. You need repeated, verified uses to build confidence. Try:

1. Running the simulator to generate synthetic traffic
2. Having the captain review more pending items
3. Being consistent with your command phrasing

### Model Using Too Many Tokens

That means your compiled coverage is low. Check the bathymetric map:

```python
bathy = BathymetricMap()
bathy.build_from_store(store)
print(bathy.render())
```

Focus on the deepest (most ░) regions — those are where the model is spending your tokens.

### Edge Deployment Too Slow

If Gemma 3 is too slow on your hardware:
1. Make sure you have enough compiled tiles (check coverage)
2. Use quantized model weights (GGUF Q4)
3. Consider a more powerful boat computer

```bash
# Check model size
ollama list
# Pull the quantized version
ollama pull gemma3:1b
```

---

## Next Steps

- Read [ARCHITECTURE.md](ARCHITECTURE.md) to understand how the pieces fit together
- Read [TILES.md](TILES.md) for a deep dive on the tile system
- Read [SIMULATORS.md](SIMULATORS.md) to test everything before going to sea
- Read [MARITIME-EXAMPLES.md](MARITIME-EXAMPLES.md) for real-world scenarios

Welcome aboard. ⚓
