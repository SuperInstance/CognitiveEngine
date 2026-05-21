# Signal Chain Integration

## Overview

The signal chain is LucidDreamer's routing and confidence architecture. It controls how inputs flow through a hierarchy of **rooms**, each tuned by a **dial** that sets the balance between hard-compiled knowledge and soft model inference.

The design comes from two key ideas in the Oracle1 essays:

- **The Soft Room** — small signals accumulate. A single low-confidence observation isn't enough, but repeated observations build sediment. "The epsilon doesn't go to zero. It accumulates." Over time, sediment becomes rock.
- **The Snap** — when accumulated confidence crosses a threshold (97.5%), inference becomes hard-locked fact. The line comes tight. No more tokens, no more model calls — just compiled code executing deterministically.

The signal chain turns these ideas into a runnable system: tiles accumulate confidence via epsilon deltas, rooms gate access by dial position, and snaps cascade through parent-child chains.

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │            EpsilonAccumulator            │
                    │  accumulate("tile-id", 0.03) ──→ 0.72   │
                    │  accumulate("tile-id", 0.04) ──→ 0.76   │
                    │  accumulate("tile-id", 0.25) ──→ 0.98 ★ │
                    │         snap_threshold = 0.975           │
                    └────────────────────┬────────────────────┘
                                         │ snapped tiles
                                         ▼
 ┌──────────────┐    ┌──────────────────────┐    ┌──────────────┐
 │  SoftRoom    │    │  SignalChainRoom     │    │  HardRoom    │
 │  dial=0.9    │───▶│  dial=0.5            │───▶│  dial=0.1    │
 │              │    │                      │    │              │
 │  All tiles   │    │  Verified+ tiles     │    │  Compiled    │
 │  + fallback  │    │  + inherited snaps   │    │  only        │
 │              │    │                      │    │              │
 └──────────────┘    └──────────────────────┘    └──────────────┘
        │                     │                         │
        ▼                     ▼                         ▼
  SignalRouter          SignalRouter              SignalRouter
  (dial=0.9)            (dial=0.5)                (dial=0.1)
        │                     │                         │
        └─────────────────────┼─────────────────────────┘
                              ▼
                        RoomChain.route()
                    (walks rooms left→right)
```

**Flow:** Input enters through a `RoomChain` or individual `SignalChainRoom`. Each room checks compiled tiles first (free), then negative constraints, then dial-aware fuzzy matches, then fallback model (gated by dial). Snaps from parent rooms propagate to children so hard bindings cascade down.

## Core Concepts

### Dial

A float from `0.0` (hard) to `1.0` (soft) controlling how permissive a room is.

| Dial | Label | Behavior |
|------|-------|----------|
| 0.0  | Hard  | Only compiled tiles (confidence 1.0). No inference, no fallback. |
| 0.25 | Firm  | Verified tiles (confidence ≥ 0.9). |
| 0.5  | Mixed | Tentative tiles (confidence ≥ 0.7). |
| 0.75 | Soft  | Ambiguous tiles (confidence ≥ 0.5). |
| 1.0  | Soft  | Full model fallback permitted. |

```python
from luciddreamer.signal_chain import SignalChainRoom

room = SignalChainRoom(name="navigation", dial=0.5)

# Move harder — reject low-confidence matches
room.set_dial(0.1)

# Move softer — accept everything, allow fallback
room.set_dial(0.9)
```

### Room

A `SignalChainRoom` wraps a `TileStore`, adds a dial, an anchor dict, and parent/child chaining.

```python
from luciddreamer.signal_chain import SignalChainRoom
from luciddreamer.tiles import Tile, TileType, Verifier

room = SignalChainRoom(
    name="commands",
    dial=0.5,
    anchor={"vessel": "F/V Oracle"},
    fallback_fn=lambda text: {"action": "LLM_RESPONSE", "text": text},
)

# Add a tile
tile = Tile(
    tile_type=TileType.COMMAND,
    input_pattern="turn port",
    output_action="RUDDER_PORT_10",
    confidence=0.85,
    verifier=Verifier.CAPTAIN,
)
room.store.add(tile)

# Query at current dial
results = room.find_at_dial("turn port")
# → [Tile(command, 'turn port', conf=0.85)]
```

### Snap

A snap occurs when a tile's confidence reaches 1.0 (fully compiled). Snapped tiles are deterministic — zero model calls, zero tokens.

```python
from luciddreamer.tiles import Tile, TileType

# A snapped tile — confidence 1.0 means fully compiled
tile = Tile(
    tile_type=TileType.COMMAND,
    input_pattern="steady",
    output_action="HEADING_HOLD",
    confidence=1.0,
)

# Snaps are tiles with confidence >= 1.0
room.store.add(tile)
assert len(room.snaps) == 1

# Snaps propagate to children
child_room = room.add_child(SignalChainRoom(name="sub-systems"))
room.propagate_snaps()
# child_room now has the "steady" → HEADING_HOLD snap
```

### Epsilon Accumulation

Small confidence deltas compound over time. Instead of one big model call setting confidence, repeated observations gradually build it up until snap.

```python
from luciddreamer.epsilon_accumulator import EpsilonAccumulator

acc = EpsilonAccumulator(snap_threshold=0.975, decay=0.995)

# Small observations accumulate
r1 = acc.accumulate("tile-abc", 0.3)   # → 0.3000
r2 = acc.accumulate("tile-abc", 0.3)   # → 0.5985  (0.3 * 0.995 + 0.3)
r3 = acc.accumulate("tile-abc", 0.3)   # → 0.8955
r4 = acc.accumulate("tile-abc", 0.1)   # → 0.9910 ★ SNAP

assert r4.snapped  # True — crossed 0.975

# Check current state
acc.get_confidence("tile-abc")  # 0.9910
acc.snapped_count               # 1
```

The `decay` parameter (default 0.995) means old evidence fades slightly — tiles need ongoing reinforcement to stay snapped. Set `decay=1.0` for permanent accumulation.

## API Reference

### `SignalChainRoom`

```python
from luciddreamer.signal_chain import SignalChainRoom
```

**Constructor:**

```python
SignalChainRoom(
    name: str,
    dial: float = 0.5,
    anchor: dict = {},              # arbitrary metadata
    store: TileStore = TileStore(),
    fallback_fn: Callable | None = None,
    fallback_threshold: float = 0.3,  # minimum dial to allow fallback
    parent: SignalChainRoom | None = None,
    children: list[SignalChainRoom] = [],
)
```

**Properties:**

| Property | Type | Description |
|----------|------|-------------|
| `snaps` | `list[Tile]` | Tiles with confidence ≥ 1.0 |
| `inferences` | `list[Tile]` | Tiles below compile threshold |
| `stats` | `dict` | Name, dial, tile counts, coverage |

**Methods:**

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `set_dial` | `(value: float) → None` | — | Clamp dial to [0.0, 1.0] |
| `find_at_dial` | `(pattern: str) → list[Tile]` | Matched tiles | Dial-filtered pattern search including inherited snaps |
| `route` | `(text: str) → (RouteDecision, dict\|None)` | Decision tuple | Full routing: compiled → negative → fuzzy → fallback |
| `propagate_snaps` | `() → None` | — | Copy snaps to all children recursively |
| `add_child` | `(room) → SignalChainRoom` | The child | Wire room as child |

**Routing priority (inside `route()`):**

1. Compiled commands via `RigidFinder` — always, regardless of dial
2. Negative constraints — always checked
3. Dial-aware fuzzy match — filtered by `confidence_threshold`
4. Fallback model — only if `dial >= fallback_threshold`

### `EpsilonAccumulator`

```python
from luciddreamer.epsilon_accumulator import EpsilonAccumulator
```

**Constructor:**

```python
EpsilonAccumulator(
    snap_threshold: float = 0.975,  # confidence for snap
    decay: float = 0.995,           # per-step decay on existing confidence
)
```

**Methods:**

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `accumulate` | `(tile_id: str, delta: float) → AccumulationResult` | Result with `snapped` flag | Add a confidence delta |
| `get_confidence` | `(tile_id: str) → float` | Current confidence | 0.0 if unknown |
| `history` | `(tile_id: str\|None = None) → list[AccumulationRecord]` | Records | All or filtered history |
| `reset` | `(tile_id: str) → None` | — | Reset to zero (for rollback) |
| `snapshot` | `() → dict[str, float]` | All confidences | Copy of current state |

**Properties:** `snap_threshold`, `decay`, `tile_count`, `snapped_count`

### `SignalRouter`

```python
from luciddreamer.signal_router import SignalRouter
```

Bridge between `SignalChainRoom` and `Router`. Thread-safe.

**Constructor:**

```python
SignalRouter(
    room: SignalChainRoom,
    fallback_model: Callable | None = None,
)
```

**Methods:**

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `route` | `(query: str, dial: float\|None = None) → (RouteDecision, dict\|None)` | Decision tuple | Route with optional dial override |
| `set_dial` | `(position: float) → None` | — | Update room's dial |

**Properties:** `dial` (float), `available_tiles` (list[Tile]), `room` (SignalChainRoom), `stats` (dict)

### `RoomChain`

```python
from luciddreamer.signal_chain import RoomChain
```

A linear chain of rooms with convenience methods.

**Constructor:**

```python
RoomChain(rooms: list[SignalChainRoom] | None = None)
```

**Methods:**

| Method | Signature | Returns | Description |
|--------|-----------|---------|-------------|
| `add` | `(room) → RoomChain` | self (fluent) | Append room to chain |
| `propagate_snaps` | `() → None` | — | Cascade snaps through all rooms |
| `set_dial` | `(value: float) → None` | — | Set dial on every room |
| `route` | `(text: str, start: int = 0) → (RouteDecision, dict\|None)` | Decision tuple | Walk rooms left→right until match |

### `Tile` and `TileStore`

```python
from luciddreamer.tiles import Tile, TileStore, TileType, Confidence, Verifier, DialMixin
```

**Tile** is the fundamental unit — a single compiled knowledge entry.

```python
Tile(
    tile_type: TileType,       # COMMAND, RESPONSE, VISION, CHART, etc.
    input_pattern: str,        # what to match
    output_action: str,        # what to do
    confidence: float = 0.0,   # 0.0–1.0
    verifier: Verifier = Verifier.MODEL,
    dial_override: float | None = None,  # pin to specific dial position
)
```

**Key Tile methods:** `record_use(correct: bool)`, `to_dict()`, `from_dict(data)`

**Key Tile properties:** `tile_id`, `success_rate`, `confidence_class`, `dial_position`, `matches_dial(dial)`

**TileStore** is thread-safe in-memory storage with pattern and type indexing.

**Key TileStore methods:** `add(tile)`, `get(tile_id)`, `find_by_pattern(pattern)`, `find_by_type(type)`, `find_compiled()`, `remove(tile_id)`, `export_json()`, `import_json(data)`

## Integration Guide

### Wiring signal chain into an existing Router

If you have a `Router` already, the signal chain layers on top without modifying existing code:

```python
from luciddreamer.router import Router
from luciddreamer.signal_chain import SignalChainRoom, RoomChain
from luciddreamer.signal_router import SignalRouter

# Your existing setup
store = TileStore()
finder = RigidFinder(store)
router = Router(store, finder, fallback_fn=my_llm_call)

# Wrap in a signal chain room
room = SignalChainRoom(
    name="main",
    dial=0.5,
    store=store,
    fallback_fn=my_llm_call,
)

# Use SignalRouter for dial-aware routing
sr = SignalRouter(room)

# Drop-in replacement: route the same way
decision, payload = sr.route("turn starboard 15")
# RouteDecision.COMPILED, RouteDecision.AMBIGUOUS, etc.

# Now you can tune behavior at runtime
sr.set_dial(0.2)   # go hard — compiled only
sr.set_dial(0.8)   # go soft — accept everything
```

### Adding epsilon accumulation to tile lifecycle

```python
from luciddreamer.epsilon_accumulator import EpsilonAccumulator

acc = EpsilonAccumulator(snap_threshold=0.975)

def on_model_response(input_text: str, output_action: str, correct: bool):
    """Called when captain confirms/corrects a model response."""
    tile_id = compute_tile_id(input_text, output_action)

    delta = 0.05 if correct else -0.1
    result = acc.accumulate(tile_id, delta)

    if result.snapped:
        # Promote to compiled tile
        tile = Tile(
            tile_type=TileType.COMMAND,
            input_pattern=input_text,
            output_action=output_action,
            confidence=1.0,
        )
        store.add(tile)
```

### Building a multi-room chain

```python
from luciddreamer.signal_chain import SignalChainRoom, RoomChain

# Build rooms with decreasing softness
chain = RoomChain([
    SignalChainRoom(name="soft-catch",   dial=0.9),  # accepts almost everything
    SignalChainRoom(name="navigation",   dial=0.5),  # moderate
    SignalChainRoom(name="hard-safety",  dial=0.1),  # compiled only
])

# Propagate hard bindings down
chain.propagate_snaps()

# Route — walks rooms left→right
decision, payload = chain.route("steady as she goes")
```

## Oracle1 Connection

The code maps directly to concepts from the Oracle1 essays:

| Essay concept | Code |
|---|---|
| "The epsilon doesn't go to zero. It accumulates." | `EpsilonAccumulator.accumulate()` — small deltas compound via `decayed + delta` |
| "Sediment becomes rock." | Snap: confidence ≥ 0.975 → `snapped=True`, tile promoted to compiled |
| "The line comes tight." | `Tile.confidence == 1.0` → deterministic execution, zero tokens |
| "The dial controls model vs code." | `SignalChainRoom.dial` — 0.0 hard, 1.0 soft |
| "A room is where snaps and inferences live together." | `SignalChainRoom` wraps `TileStore` + dial + parent/child chain |
| "Tune the chain like a synth." | `RoomChain.set_dial()` adjusts all rooms at once |

Key threshold: **97.5%** — the snap threshold in `EpsilonAccumulator` matches `RigidFinder.COMPILE_THRESHOLD`. This is the crossing point where inference becomes compilation.

## Examples

### Full navigation chain with accumulation

```python
from luciddreamer.signal_chain import SignalChainRoom, RoomChain
from luciddreamer.epsilon_accumulator import EpsilonAccumulator
from luciddreamer.tiles import Tile, TileType, Verifier

# Set up accumulator and room
acc = EpsilonAccumulator(snap_threshold=0.975, decay=0.995)
room = SignalChainRoom(name="nav", dial=0.5)

# Simulate repeated observations of "come to 270"
pattern = "come to 270"
action = "HEADING_270"

for _ in range(20):
    result = acc.accumulate("come-to-270", 0.08)
    if result.snapped:
        tile = Tile(
            tile_type=TileType.COMMAND,
            input_pattern=pattern,
            output_action=action,
            confidence=1.0,
            verifier=Verifier.SIMULATION,
        )
        room.store.add(tile)
        print(f"SNAPPED at {result.new_confidence:.4f}")
        break

# Now "come to 270" routes as compiled — zero tokens
decision, payload = room.route("come to 270")
assert decision.value == "compiled"
```

### Dial-aware routing with fallback gating

```python
from luciddreamer.signal_chain import SignalChainRoom

def fake_llm(text):
    return {"action": "LLM_SUGGESTION", "for": text}

room = SignalChainRoom(
    name="test",
    dial=0.2,  # hard — fallback blocked
    fallback_fn=fake_llm,
    fallback_threshold=0.3,
)

# No compiled tiles exist → fallback, but dial too low
decision, payload = room.route("unknown command")
assert payload["action"] == "UNKNOWN"  # fallback blocked by dial

# Soften the dial
room.set_dial(0.5)
decision, payload = room.route("unknown command")
assert payload["action"] == "LLM_SUGGESTION"  # fallback now allowed
```

### Snap propagation through a chain

```python
from luciddreamer.signal_chain import SignalChainRoom, RoomChain
from luciddreamer.tiles import Tile, TileType

# Parent has compiled knowledge
parent = SignalChainRoom(name="parent", dial=0.3)
parent.store.add(Tile(
    tile_type=TileType.COMMAND,
    input_pattern="full stop",
    output_action="ALL_STOP",
    confidence=1.0,
))

child = SignalChainRoom(name="child", dial=0.7)
chain = RoomChain([parent, child])
chain.propagate_snaps()

# Child inherited the snap — queries work even at child's softer dial
results = child.find_at_dial("full stop")
assert len(results) == 1
assert results[0].output_action == "ALL_STOP"
```
