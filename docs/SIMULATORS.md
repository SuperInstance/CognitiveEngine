# Simulators — Test Everything Before Going to Sea

> You don't want to debug voice commands in 8-foot seas. Test on the dock.

---

## Why Simulators Matter

At sea, things go wrong fast. A misunderstood voice command could mean a hard turn at the wrong moment. A fish misclassification could mean losing a buyer's trust. A chart misread could mean running aground.

Simulators let you:

- **Test safely** — no risk to vessel or crew
- **Build tile coverage** — generate synthetic traffic to compile tiles faster
- **Train crew** — deckhands can practice without wasting fish
- **Validate before deployment** — catch bugs on the dock, not at sea
- **Run scenarios** — what if the radar fails? What if it's foggy?

---

## Autopilot Command Simulator

The autopilot simulator feeds synthetic voice commands to the router and tracks how it handles them.

```python
from luciddreamer.tiles import TileStore, CommandTile, Verifier
from luciddreamer.compiler import RigidFinder
from luciddreamer.router import Router, RouteDecision

# Setup
store = TileStore()
finder = RigidFinder(store)

# Simulated model fallback (in real life, this would be Gemma 3)
def mock_fallback(text):
    """Simulate a model that mostly gets it right."""
    responses = {
        "turn port": "helm_port_10",
        "turn starboard": "helm_starboard_10",
        "steady": "helm_steady",
        "reduce speed": "throttle_back",
        "increase speed": "throttle_up",
    }
    for key, action in responses.items():
        if key in text.lower():
            return {"action": action, "raw": text}
    return {"action": "unknown", "raw": text}

router = Router(store=store, finder=finder, fallback_fn=mock_fallback)

# ── Run the Simulation ──────────────────────────────────

# Simulate a day of voice commands
simulated_commands = [
    # Morning departure
    ("turn port 10 degrees", True),
    ("steady as she goes", True),
    ("increase speed", True),
    ("reduce to 5 knots", True),
    
    # Fishing operations
    ("steady as she goes", True),
    ("turn starboard 5 degrees", True),
    ("turn port 10 degrees", True),
    ("steady as she goes", True),
    
    # Transit
    ("increase speed", True),
    ("turn port 15 degrees", True),
    ("steady as she goes", True),
    
    # Approach
    ("reduce speed", True),
    ("turn starboard 10 degrees", True),
    ("steady as she goes", True),
    ("reduce to 3 knots", True),
    
    # One mistake (model got it wrong)
    ("come left easy", False),
]

print("Running autopilot simulation...")
print("=" * 50)

compiled_hits = 0
fallback_hits = 0
correct = 0
total = len(simulated_commands)

for i, (command, expected_correct) in enumerate(simulated_commands):
    decision, result = router.route(command)
    
    if decision == RouteDecision.COMPILED:
        compiled_hits += 1
    elif decision == RouteDecision.FALLBACK:
        fallback_hits += 1
        # Simulate captain review
        router.confirm_pending(0, correct=expected_correct)
    
    if expected_correct:
        correct += 1
    
    status = "✓" if expected_correct else "✗ (correction)"
    print(f"  {i+1:2d}. [{decision.value:10s}] {command:30s} {status}")

print()
print(f"Results:")
print(f"  Compiled: {compiled_hits}/{total} ({compiled_hits/total:.0%})")
print(f"  Fallback: {fallback_hits}/{total} ({fallback_hits/total:.0%})")
print(f"  Correct:  {correct}/{total} ({correct/total:.0%})")
print(f"  Tiles in store: {len(store)}")

# Try compiling
compiled = finder.compile_all()
print(f"  Compiled commands: {len(compiled)}")
```

### Running It Multiple Times (Simulating a Season)

```python
# Simulate 50 trips
for trip in range(50):
    for command, expected_correct in simulated_commands:
        decision, result = router.route(command)
        if decision == RouteDecision.FALLBACK:
            router.confirm_pending(0, correct=expected_correct)

# Check coverage
finder.compile_all()
print(f"After 50 simulated trips:")
print(f"  Compiled: {finder.compiled_count}")
print(f"  Coverage: {finder.coverage:.1%}")
```

---

## Fish Sorting Simulator

Simulate the fish sorting pipeline with fake fish photos and known species.

```python
import random
from luciddreamer.tiles import TileStore, VisionTile, Verifier

store = TileStore()

# Species we expect to catch
species_list = [
    ("Pacific Halibut", 3, (20, 200)),    # (name, hold_number, weight_range lbs)
    ("Sablefish", 1, (3, 15)),
    ("Pacific Cod", 2, (5, 40)),
    ("Yellowfin Sole", 4, (1, 5)),
    ("Rock Sole", 4, (1, 4)),
    ("Rex Sole", 5, (0.5, 3)),
    ("Arrowtooth Flounder", 6, (2, 15)),
]

# Simulate sorting 200 fish
print("Running fish sorting simulation...")
print("=" * 50)

total = 200
correct = 0

for i in range(total):
    # Pick a random fish
    species, hold, (min_w, max_w) = random.choice(species_list)
    weight = round(random.uniform(min_w, max_w), 1)
    
    # Simulate photo path
    photo = f"sim_photos/fish_{i:04d}.jpg"
    
    # Check if we have a tile for this species
    existing = store.find_by_pattern(f"species:{species}")
    
    if existing:
        tile = existing[0]
        # Model classifies (with increasing accuracy)
        tile.record_use(correct=(random.random() < tile.confidence))
        if tile.confidence > 0.9:
            correct += 1
    else:
        # New species — create tile
        tile = VisionTile(
            input_pattern=f"species:{species}",
            output_action=f"classify:{species.lower().replace(' ', '_')}",
            species=species,
            hold_number=hold,
            photo_path=photo,
            weight_estimate=weight,
            confidence=0.4,
            verifier=Verifier.MODEL,
            source="simulation",
        )
        store.add(tile)

print(f"Sorted {total} fish")
print(f"High-confidence correct: {correct}/{total} ({correct/total:.0%})")
print(f"Species tiles: {len(store)}")

# Show per-species confidence
print("\nPer-species confidence:")
for species, _, _ in species_list:
    tiles = store.find_by_pattern(f"species:{species}")
    if tiles:
        t = tiles[0]
        print(f"  {t.confidence_class.value:12s} {t.confidence:.2f}  "
              f"{species} ({t.times_used} uses)")
```

---

## Chart Reading Simulator

Simulate chart queries and test the system's ability to interpret depth and features.

```python
from luciddreamer.tiles import TileStore, ChartTile, Verifier
from luciddreamer.bathymetry import BathymetricMap

store = TileStore()

# Simulate chart regions with known depths
chart_regions = [
    ("Dutch Harbor approaches", (3.0, 8.0), ["5-fathom contour", "rock pinnacle"]),
    ("Akutan Pass", (10.0, 30.0), ["narrow channel", "current"]),
    ("Bering Sea flats", (20.0, 50.0), ["flat bottom", "trawl ground"]),
    ("Unimak Pass", (15.0, 100.0), ["deep channel", "heavy traffic"]),
    ("Makushin Bay", (2.0, 6.0), ["shallow", "kelp beds"]),
]

# Simulate 100 chart queries
queries = [
    "how deep is it here",
    "are we going to remain deep enough",
    "what's the bottom like ahead",
    "any hazards on this route",
    "show me depth contours",
]

print("Running chart reading simulation...")

for i in range(100):
    region_name, depth_range, features = random.choice(chart_regions)
    query = random.choice(queries)
    
    # Check for existing chart tile
    existing = store.find_by_pattern(f"{query}:{region_name}")
    
    if existing:
        tile = existing[0]
        tile.record_use(correct=True)
    else:
        tile = ChartTile(
            input_pattern=f"{query}:{region_name}",
            output_action=f"chart_info:{region_name}",
            region=region_name,
            depth_range=depth_range,
            features=features,
            confidence=0.5,
            verifier=Verifier.SIMULATION,
            source="simulation",
        )
        store.add(tile)

# Show coverage
bathy = BathymetricMap()
bathy.build_from_store(store)
print(bathy.render())
```

---

## Captain Review Session Simulator

Simulate the captain reviewing pending items at the end of a watch.

```python
from luciddreamer.tiles import TileStore, Tile, TileType, Verifier
from luciddreamer.compiler import RigidFinder
from luciddreamer.router import Router

store = TileStore()
finder = RigidFinder(store)

def model_fallback(text):
    return {"action": "simulated_action", "raw": text}

router = Router(store=store, finder=finder, fallback_fn=model_fallback)

# Generate some pending reviews
test_inputs = [
    "turn port 10 degrees",
    "steady as she goes",
    "reduce to trolling speed",
    "come about",
    "hard to starboard",
    "what's our depth",
    "any traffic ahead",
]

for inp in test_inputs:
    router.route(inp)

print(f"Pending reviews: {router.pending_count}")
print("=" * 50)

# Simulate captain review
print("\nCaptain Review Session")
print("-" * 50)

for i in range(router.pending_count):
    pending = router._pending[i] if i < len(router._pending) else None
    if not pending:
        break
    
    # Simulate: captain confirms 80% of the time
    is_correct = random.random() < 0.8
    
    if is_correct:
        tile_id = router.confirm_pending(0, correct=True)
        print(f"  ✓ Confirmed: {pending['input']}")
    else:
        tile_id = router.confirm_pending(0, correct=False, 
                                          correction="corrected_action")
        print(f"  ✗ Corrected: {pending['input']}")

print(f"\nAfter review:")
print(f"  Total tiles: {len(store)}")
print(f"  Pending: {router.pending_count}")

# Check what compiled
compiled = finder.compile_all()
print(f"  Compiled: {len(compiled)}")
```

---

## Full Trip Simulation

Run a complete simulated trip from departure to arrival.

```python
import random
from luciddreamer.tiles import TileStore, CommandTile, VisionTile, ChartTile, Verifier
from luciddreamer.compiler import RigidFinder
from luciddreamer.router import Router, RouteDecision
from luciddreamer.bathymetry import BathymetricMap

# ── Setup ──────────────────────────────────────────────

store = TileStore()
finder = RigidFinder(store)

def fallback(text):
    return {"action": "fallback", "raw": text}

router = Router(store=store, finder=finder, fallback_fn=fallback)

# ── Trip Phases ────────────────────────────────────────

phases = {
    "departure": [
        "turn port 10 degrees", "increase speed", "steady as she goes",
        "turn starboard 15 degrees", "increase to 10 knots",
    ],
    "transit": [
        "steady as she goes", "turn port 5 degrees", "reduce to 8 knots",
        "steady as she goes", "turn starboard 10 degrees",
        "what's our ETA", "any traffic ahead",
    ],
    "fishing": [
        "reduce to 2 knots", "turn port 10 degrees", "steady as she goes",
        "reduce speed", "turn starboard 5 degrees",
    ],
    "sorting": [  # These create VisionTiles
        "Pacific Halibut", "Sablefish", "Pacific Cod", "Yellowfin Sole",
        "Arrowtooth Flounder", "Pacific Halibut", "Rock Sole",
    ],
    "chart_queries": [
        "how deep is it here", "any hazards ahead", "depth contours",
        "bottom type", "clearance under keel",
    ],
    "return": [
        "increase speed", "turn port 15 degrees", "steady as she goes",
        "reduce to 5 knots", "turn starboard 10 degrees",
        "reduce speed", "steady as she goes",
    ],
}

# ── Run Simulation ────────────────────────────────────

trip_stats = {}

for phase, commands in phases.items():
    print(f"\n── {phase.upper()} ──")
    phase_compiled = 0
    phase_fallback = 0
    
    for cmd in commands:
        if phase == "sorting":
            # Fish sorting
            tile = VisionTile(
                input_pattern=f"species:{cmd}",
                output_action=f"classify:{cmd.lower().replace(' ', '_')}",
                species=cmd,
                confidence=0.6,
                verifier=Verifier.SIMULATION,
                source="simulation",
            )
            store.add(tile)
            print(f"  Sorted: {cmd}")
        elif phase == "chart_queries":
            # Chart queries
            tile = ChartTile(
                input_pattern=cmd,
                output_action=f"chart:{cmd.replace(' ', '_')}",
                confidence=0.5,
                source="simulation",
            )
            store.add(tile)
            print(f"  Chart: {cmd}")
        else:
            # Navigation commands
            decision, result = router.route(cmd)
            if decision == RouteDecision.COMPILED:
                phase_compiled += 1
            else:
                phase_fallback += 1
                router.confirm_pending(0, correct=True)
            
            print(f"  [{decision.value:10s}] {cmd}")
    
    trip_stats[phase] = {
        "compiled": phase_compiled,
        "fallback": phase_fallback,
    }

# ── Results ───────────────────────────────────────────

print("\n" + "=" * 60)
print("TRIP SIMULATION RESULTS")
print("=" * 60)

finder.compile_all()

for phase, stats in trip_stats.items():
    total = stats["compiled"] + stats["fallback"]
    if total > 0:
        pct = stats["compiled"] / total * 100
        print(f"  {phase:15s}: {stats['compiled']}/{total} compiled ({pct:.0f}%)")

print(f"\n  Total tiles: {len(store)}")
print(f"  Compiled commands: {finder.compiled_count}")
print(f"  Overall coverage: {finder.coverage:.1%}")

# Bathymetric map
bathy = BathymetricMap()
bathy.build_from_store(store)
print(f"\n{bathy.render()}")
```

---

## Interpreting Simulator Results

### Good Results

```
  Compiled: 15/25 (60%)
  Fallback: 10/25 (40%)
  Coverage: 65.2%
  
  Bathymetric Coverage Map
  ============================================================
  
    turn            ████████████████████░░░░░░░░░░░░░░░░░░░░  50.0%
    steady          ████████████████████████████████████████░░  95.0%
    reduce          ████████████████░░░░░░░░░░░░░░░░░░░░░░░░  40.0%
    increase        ████████████████░░░░░░░░░░░░░░░░░░░░░░░░  40.0%
    
    █ = compiled (zero inference)  ░ = needs model
```

This shows a system that's learning well. "Steady" is nearly compiled. "Turn" is halfway there.

### Needs Attention

```
  Compiled: 2/25 (8%)
  Fallback: 23/25 (92%)
  Coverage: 8.3%
  
  ⚠️  Below amnesia cliff (10%)!
```

This system needs more training data. Run more simulations or have the captain review more pending items.

### After Many Simulated Trips

```
  Compiled: 23/25 (92%)
  Fallback: 2/25 (8%)
  Coverage: 91.5%
```

This system is mature. Most commands compile. The model only fires for rare edge cases.

---

## Tips for Effective Simulation

1. **Use realistic command patterns** — base them on what the captain actually says
2. **Include mistakes** — not every model response should be correct
3. **Run multiple trips** — compilation needs repetition
4. **Check the bathymetric map** — visualize where coverage is thin
5. **Simulate edge cases** — unusual commands, fast speech, background noise
6. **Review pending items** — simulate the captain review cycle too
7. **Test degradation** — what happens if the model is unavailable?

---

## Next Steps

- [GETTING-STARTED.md](GETTING-STARTED.md) — Get started with real data
- [MARITIME-EXAMPLES.md](MARITIME-EXAMPLES.md) — Real-world scenarios
- [COMPILATION.md](COMPILATION.md) — How compilation works
