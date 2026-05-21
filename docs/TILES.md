# Tiles — The Building Blocks of Maritime Intelligence

> Every interaction creates a tile. Every tile is a sounding line into the model's competence.

---

## What Is a Tile?

A **tile** is a single piece of knowledge that the system has learned. Think of it like a 3x5 index card in a recipe box — one card, one thing, easy to find, easy to verify.

In code, every tile stores:
- **What triggered it** (the input — voice command, photo, chart region)
- **What to do** (the output — helm action, species classification, depth reading)
- **How confident** we are (0.0 to 1.0)
- **Who verified it** (captain, crew, model, buyer, simulator)

### Real-World Examples

#### Autopilot Voice Control

```python
from luciddreamer.tiles import CommandTile, Verifier

# The captain says "turn port 10 degrees" — this becomes a tile
tile = CommandTile(
    input_pattern="turn port 10 degrees",
    output_action="helm_port_10",
    confidence=0.85,
    verifier=Verifier.CAPTAIN,
    source="edge",
)
```

What this tile says: *"When someone says 'turn port 10 degrees', turn the helm 10 degrees to port. The captain verified this. We're 85% confident."*

#### Fish Sorting

```python
from luciddreamer.tiles import VisionTile, Verifier

# A deck hand sorts a halibut — this becomes a tile
tile = VisionTile(
    input_pattern="photo_2024-06-15_001.jpg",
    output_action="classify:pacific_halibut",
    species="Pacific Halibut",
    hold_number=3,
    weight_estimate=45.2,
    confidence=0.90,
    verifier=Verifier.DECK_CREW,
    source="edge",
)
```

What this tile says: *"This photo is a 45-pound Pacific Halibut, sorted to hold 3. Deck crew confirmed."*

#### Chart Intelligence

```python
from luciddreamer.tiles import ChartTile, Verifier

# Captain identifies a depth contour — this becomes a tile
tile = ChartTile(
    input_pattern="blue_contour_near_dutch",
    output_action="depth_alert:shallow_approach",
    region="Dutch Harbor approaches",
    depth_range=(3.0, 5.0),
    features=["5-fathom contour", "rock at 58-12.3N"],
    confidence=0.75,
    verifier=Verifier.CAPTAIN,
    source="cloud",
)
```

What this tile says: *"Blue contours near Dutch Harbor mean shallow water, 3-5 fathoms. There's a rock at that position. Captain confirmed but we want to verify more."*

---

## Tile Types

Every tile has a `TileType` that describes what kind of knowledge it holds:

```
┌─────────────────────────────────────────────────────────┐
│                    Tile Types                            │
│                                                         │
│  COMMAND     Voice/text → action mapping                 │
│  "turn port 10" → helm_port_10                          │
│                                                         │
│  RESPONSE    System response template                   │
│  "Aye, turning port 10 degrees"                         │
│                                                         │
│  VISION      Camera image → classification              │
│  [photo] → "Pacific Halibut, 45 lbs"                   │
│                                                         │
│  CHART       Chart region → interpretation              │
│  [ENC region] → "shallow approach, 5 fathom contour"   │
│                                                         │
│  CORRECTION  Human correction of a wrong tile           │
│  "That was a flounder, not a halibut"                   │
│                                                         │
│  NEGATIVE    What NOT to do (negative knowledge)        │
│  "Never turn more than 30° at once"                     │
│                                                         │
│  ABSTRACTION Generalized pattern from specific tiles    │
│  "turn [direction] [N] degrees" → helm_[dir]_[N]       │
└─────────────────────────────────────────────────────────┘
```

### When Each Type Is Used

| Type | Created When | Example |
|------|-------------|---------|
| **COMMAND** | Voice command processed | "turn port 10" |
| **RESPONSE** | System generates a reply | "Aye, coming to course 270" |
| **VISION** | Camera captures and classifies fish | Photo → "Sablefish, 12 lbs" |
| **CHART** | Chart region interpreted | ENC section → depth contour info |
| **CORRECTION** | Captain or crew corrects a mistake | "Not halibut, that's a flounder" |
| **NEGATIVE** | System learns what NOT to do | "Don't trim tabs in following seas" |
| **ABSTRACTION** | Multiple specific tiles generalize | "turn X degrees" pattern |

---

## Confidence Scoring

Every tile has a confidence score from 0.0 to 1.0. This score determines how the system behaves.

### The Five Confidence Levels

```python
from luciddreamer.tiles import Confidence

# The system maps numeric confidence to these levels:
# 
#  1.0        COMPILED     ████████████  Deterministic, zero inference
#  0.90-0.99  VERIFIED     ██████████░░  Execute + confirm
#  0.70-0.89  TENTATIVE    ████████░░░░  Execute tentatively, ask
#  0.50-0.69  AMBIGUOUS    ██████░░░░░░  Don't execute, ask captain
#  0.00-0.49  UNKNOWN      ░░░░░░░░░░░░  Batch for review
```

### How Confidence Evolves

```python
from luciddreamer.tiles import CommandTile

tile = CommandTile(
    input_pattern="steady as she goes",
    output_action="helm_steady",
    confidence=0.5,  # Starts AMBIGUOUS
)

# Day 1: Captain says "yes, that's right"
tile.record_use(correct=True)
print(f"After 1st use: {tile.confidence:.2f}")   # 0.52

# Day 3: Used again, correct
tile.record_use(correct=True)
print(f"After 2nd use: {tile.confidence:.2f}")   # 0.54

# Day 5: Used 10 more times, all correct
for _ in range(10):
    tile.record_use(correct=True)
print(f"After 12 uses: {tile.confidence:.2f}")   # 0.74 (TENTATIVE → VERIFIED)

# Day 7: WRONG response! Captain corrects it
tile.record_use(correct=False)
print(f"After correction: {tile.confidence:.2f}")  # 0.64 (dropped sharply)

# Recovery takes many more correct uses
for _ in range(17):
    tile.record_use(correct=True)
print(f"After recovery: {tile.confidence:.2f}")    # 0.98 (VERIFIED)
```

### The Asymmetry

```
  Correct:  +0.02  (slow rise)
  Wrong:    -0.10  (fast fall)
  
  It takes 5 correct uses to recover from 1 mistake.
  This is deliberate — safety matters at sea.
```

### Checking Confidence

```python
tile = CommandTile(
    input_pattern="hard to starboard",
    output_action="helm_starboard_full",
    confidence=0.92,
)

# Get the confidence class
print(tile.confidence_class)          # <Confidence.VERIFIED: 'verified'>

# Get the success rate (uses vs. correct uses)
print(f"Success rate: {tile.success_rate:.2%}")
```

---

## Verification Sources

Every tile records **who verified it**. This matters because different sources have different reliability:

```python
from luciddreamer.tiles import Verifier
```

| Verifier | Description | Trust Level | When Used |
|----------|-------------|-------------|-----------|
| `MODEL` | The AI model verified itself | Low | Auto-verification during inference |
| `CAPTAIN` | The captain confirmed | High | Captain review sessions |
| `DECK_CREW` | Deck crew confirmed | Medium | Fish sorting, species ID |
| `BUYER` | Buyer's count confirmed | High | End-of-trip reconciliation |
| `SIMULATION` | Verified in simulator | Medium | Pre-season testing |

### Setting the Verifier

```python
from luciddreamer.tiles import CommandTile, Verifier

# Model auto-verified (lowest trust)
tile = CommandTile(
    input_pattern="reduce speed",
    output_action="throttle_back",
    verifier=Verifier.MODEL,
)

# Captain verified (highest trust)
tile = CommandTile(
    input_pattern="reduce speed",
    output_action="throttle_back",
    verifier=Verifier.CAPTAIN,
)

# Verified in simulator (good for pre-season)
tile = CommandTile(
    input_pattern="reduce speed",
    output_action="throttle_back",
    verifier=Verifier.SIMULATION,
)
```

---

## The Negative Knowledge Pattern

Some of the most important tiles are **negative tiles** — they tell the system what NOT to do.

```python
from luciddreamer.tiles import Tile, TileType

# The captain learns: never trim tabs in a following sea
negative_tile = Tile(
    tile_type=TileType.NEGATIVE,
    input_pattern="trim tabs following sea",
    output_action="BLOCKED: Never adjust trim tabs in following seas — risk of broaching",
    confidence=0.95,
    source="captain",
)

store.add(negative_tile)
```

### How Negatives Work in the Router

```python
from luciddreamer.router import Router, RouteDecision

# When someone says "trim tabs" in a following sea...
decision, result = router.route("trim tabs up a bit, following sea")

print(decision)  # RouteDecision.NEGATIVE
print(result)
# {'action': 'BLOCKED', 'reason': 'Never adjust trim tabs in following seas...', ...}
```

The router checks negative tiles **before** falling back to the model. This prevents the model from ever executing a known-bad action.

### When to Create Negative Tiles

- After a close call or near-miss
- When the model suggests something dangerous
- Company safety policies (e.g., "never exceed 12 knots in harbor")
- Regulatory requirements (e.g., "don't discharge within 3 NM")

---

## Abstraction: Generalizing from Specifics

An **abstraction tile** generalizes from multiple specific tiles into a single pattern.

```python
from luciddreamer.tiles import Tile, TileType

# You have these specific tiles:
# "turn port 10 degrees" → helm_port_10
# "turn port 15 degrees" → helm_port_15
# "turn port 20 degrees" → helm_port_20
# "turn starboard 5 degrees" → helm_starboard_5
# "turn starboard 10 degrees" → helm_starboard_10

# The abstraction captures the pattern:
abstraction = Tile(
    tile_type=TileType.ABSTRACTION,
    input_pattern="turn {direction} {degrees} degrees",
    output_action="helm_{direction}_{degrees}",
    confidence=0.90,
    metadata={
        "generalized_from": ["turn port 10", "turn port 15", "turn starboard 5", ...],
        "parameter_count": 2,
        "parameters": ["direction", "degrees"],
    },
)

store.add(abstraction)
```

### How Abstractions Help

Abstractions let the system handle **novel inputs** that it hasn't seen exactly, but fit a known pattern:

```
  Seen: "turn port 10 degrees" ✓
  Seen: "turn port 15 degrees" ✓
  Novel: "turn port 23 degrees" ← matches abstraction!
  
  Result: helm_port_23 (with appropriate confidence)
```

This dramatically expands coverage without needing to see every possible input.

---

## Tile Provenance and Lineage

Every tile records where it came from and what it relates to:

```python
from luciddreamer.tiles import CommandTile, TileType
import time

# Original tile
original = CommandTile(
    input_pattern="come left easy",
    output_action="helm_port_5",
    confidence=0.7,
    source="edge",
    trip_id="trip_2024_042",
    vessel="F/V Northern Star",
    created_at=time.time(),
)

# Correction tile — links back to original
correction = Tile(
    tile_type=TileType.CORRECTION,
    input_pattern="come left easy",
    output_action="helm_port_3",  # Corrected action
    parent_tile_id=original.tile_id,  # Links to what it corrects
    confidence=0.9,
    source="captain",
)

# Negative tile — blocks the original
negative = Tile(
    tile_type=TileType.NEGATIVE,
    input_pattern="come left easy in heavy weather",
    output_action="BLOCKED: Use larger turns in heavy weather",
    negative_of=original.tile_id,  # Links to what it negates
    confidence=0.95,
    source="captain",
)
```

### Provenance Fields

| Field | What It Records |
|-------|----------------|
| `source` | Where it came from: "cloud", "edge", "captain", "simulation" |
| `trip_id` | Which fishing trip created it |
| `vessel` | Which boat |
| `created_at` | Unix timestamp |
| `parent_tile_id` | If this generalizes or corrects another tile |
| `negative_of` | If this is negative knowledge about another tile |

This lineage lets you trace any tile back to its origin — who said it, when, on which boat, during which trip.

---

## The TileStore

The `TileStore` is your boat's memory. It indexes tiles for fast lookup:

```python
from luciddreamer.tiles import TileStore, CommandTile, TileType

store = TileStore()

# Add tiles
tile = CommandTile(input_pattern="steady as she goes", output_action="helm_steady")
tile_id = store.add(tile)

# Look up by ID
found = store.get(tile_id)

# Search by pattern
results = store.find_by_pattern("steady as she goes")

# Filter by type
commands = store.find_by_type(TileType.COMMAND)

# Get fully compiled tiles
compiled = store.find_compiled()

# Get tiles needing review
ambiguous = store.find_ambiguous()

# Count
print(f"Total tiles: {len(store)}")
```

### Finding Tiles

```python
# Exact match
results = store.find_by_pattern("turn port 10 degrees")

# Regex match (if tile has regex_pattern set)
tile = CommandTile(
    input_pattern="turn port 10 degrees",
    output_action="helm_port_10",
    regex_pattern=r"^turn port (?P<n>\d+) degrees?$",
)
store.add(tile)

# This will match via regex:
results = store.find_by_pattern("turn port 15 degrees")

# Results are sorted by confidence (highest first)
best = results[0]
print(f"Best match: {best.input_pattern} → {best.output_action} ({best.confidence:.0%})")
```

---

## Exporting and Importing Tiles

Tiles travel between cloud and edge via JSON export/import:

```python
# Export all tiles
json_data = store.export_json()

# Save to file
with open("tiles_trip_042.json", "w") as f:
    f.write(json_data)

# ... transfer via USB stick, sat link, etc. ...

# Import on another system
new_store = TileStore()
with open("tiles_trip_042.json") as f:
    count = new_store.import_json(f.read())
    print(f"Imported {count} tiles")
```

### Export Format

Each tile serializes to a flat JSON object:

```json
{
  "tile_id": "a3f7b2c9d4e5f6a1",
  "tile_type": "command",
  "input_pattern": "turn port 10 degrees",
  "output_action": "helm_port_10",
  "confidence": 0.92,
  "confidence_class": "verified",
  "verifier": "captain",
  "created_at": 1718467200.0,
  "source": "edge",
  "trip_id": "trip_2024_042",
  "vessel": "F/V Northern Star",
  "times_used": 47,
  "times_correct": 46,
  "times_corrected": 1,
  "parent_tile_id": null,
  "negative_of": null,
  "metadata": {}
}
```

---

## Complete API Reference

### Tile (Base Class)

```python
from luciddreamer.tiles import Tile, TileType, Verifier

tile = Tile(
    tile_type=TileType.COMMAND,
    input_pattern="turn port 10 degrees",
    output_action="helm_port_10",
    confidence=0.85,
    verifier=Verifier.CAPTAIN,
    created_at=1718467200.0,     # Optional: Unix timestamp
    source="edge",               # Optional: "cloud"|"edge"|"captain"|"simulation"
    trip_id="trip_2024_042",     # Optional: trip identifier
    vessel="F/V Northern Star",  # Optional: vessel name
    parent_tile_id=None,         # Optional: parent tile ID
    negative_of=None,            # Optional: negated tile ID
    metadata={},                 # Optional: extra data dict
)
```

**Properties:**

| Property | Returns | Description |
|----------|---------|-------------|
| `tile_id` | `str` | SHA-256 hash of content (first 16 chars) |
| `success_rate` | `float` | `times_correct / times_used` or `confidence` if unused |
| `confidence_class` | `Confidence` | Enum: COMPILED, VERIFIED, TENTATIVE, AMBIGUOUS, UNKNOWN |

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `record_use` | `(correct: bool) → None` | Record usage; adjusts confidence +0.02/-0.10 |
| `to_dict` | `() → dict` | Serialize to plain dict |
| `from_dict` | `(data: dict) → Tile` | Deserialize from dict (classmethod) |

### CommandTile

```python
from luciddreamer.tiles import CommandTile

tile = CommandTile(
    input_pattern="turn port 10 degrees",
    output_action="helm_port_10",
    regex_pattern=r"^turn port (?P<n>\d+) degrees?$",  # Optional
    parameters={"direction": "port", "degrees": 10},     # Optional
    audio_response="turn_port_10.wav",                    # Optional
    requires_confirmation=False,                           # Optional
)
```

### VisionTile

```python
from luciddreamer.tiles import VisionTile

tile = VisionTile(
    input_pattern="photo_2024_001.jpg",
    output_action="classify:pacific_halibut",
    species="Pacific Halibut",           # Optional
    hold_number=3,                       # Optional
    photo_path="/photos/2024_001.jpg",   # Optional
    weight_estimate=45.2,                # Optional
)
```

### ChartTile

```python
from luciddreamer.tiles import ChartTile

tile = ChartTile(
    input_pattern="blue_contour_dutch",
    output_action="depth_alert:shallow",
    region="Dutch Harbor approaches",       # Optional
    depth_range=(3.0, 5.0),                 # Optional: (min, max) fathoms
    features=["5-fathom contour", "rock"],  # Optional
)
```

### TileStore

```python
from luciddreamer.tiles import TileStore

store = TileStore()

# Core operations
tile_id = store.add(tile)                    # Add tile, return ID
tile = store.get(tile_id)                    # Get by ID
removed = store.remove(tile_id)              # Remove by ID, return bool

# Search
tiles = store.find_by_pattern("turn port")   # Match by input_pattern/regex
tiles = store.find_by_type(TileType.COMMAND)  # Filter by type
tiles = store.find_compiled()                 # Confidence >= 1.0
tiles = store.find_ambiguous()                # 0.5 <= confidence < 0.9

# Iteration
count = len(store)                            # Number of tiles
for tile in store:                            # Iterate all tiles
    print(tile.input_pattern)

# Export/Import
json_str = store.export_json()                # Serialize all tiles
count = store.import_json(json_str)           # Import tiles, return count
```

---

## Next Steps

- [GETTING-STARTED.md](GETTING-STARTED.md) — Build your first tiles
- [COMPILATION.md](COMPILATION.md) — How tiles become compiled code
- [MARITIME-EXAMPLES.md](MARITIME-EXAMPLES.md) — Real-world tile examples
