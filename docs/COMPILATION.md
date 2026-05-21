# Compilation — How Soft Inference Becomes Hard Code

> The model thinks slowly. Compiled regex runs instantly. Compilation is the bridge.

---

## The Big Idea

When you first use LucidDreamer, every command goes through the AI model. The model thinks about it, generates a response, and hopefully gets it right. This works, but it's:

- **Slow** (hundreds of milliseconds)
- **Expensive** (costs tokens or compute)
- **Nondeterministic** (same input might give different outputs)

After enough repetitions, the system notices: *"Hey, every time the captain says 'turn port 10 degrees', the answer is always `helm_port_10`. Why am I still thinking about this?"*

**Compilation** converts these stable patterns into regex rules that run instantly, deterministically, and without the model.

---

## The Amnesia Cliff

There's a critical danger zone: **10% minimum coverage**.

```
  Coverage    What Happens
  ─────────   ─────────────────────────────────────────────
   0%         Total amnesia. Model can't route anything.
              Everything falls through to fallback.
              
   5%         Barely functional. Model spends most tokens
              on things it SHOULD know but can't recognize.
              
  10%         MINIMUM VIABLE. The model can start to
              distinguish known from unknown patterns.
              This is the "amnesia cliff."
              
  30%         Working system. Most common commands compiled.
              Model only fires for edge cases.
              
  80%+        Mature system. Model rarely needed.
              Compilation handles the vast majority.
```

Below 10% coverage, the compiled rules are too sparse to be useful. The system can't tell whether an input *should* match something or is genuinely new. It's like having a chart with only a few soundings — you can't tell if the blank areas are deep water or rocks.

### Checking Your Coverage

```python
from luciddreamer.compiler import RigidFinder
from luciddreamer.tiles import TileStore

store = TileStore()
finder = RigidFinder(store)

coverage = finder.coverage
print(f"Coverage: {coverage:.1%}")

if coverage < 0.10:
    print("⚠️  Below amnesia cliff! Add more tiles before relying on compilation.")
elif coverage < 0.30:
    print("📈 Building coverage. Keep training.")
else:
    print("✅ Good coverage. Most commands should compile.")
```

---

## The Compile Threshold: 97.5%

The compile threshold comes from experimental data in `dream.rs`. The key finding: **literal extraction accuracy reaches 97.5%** when the model has seen enough consistent examples.

```python
from luciddreamer.compiler import RigidFinder

# This is the threshold baked into the compiler:
print(f"Compile threshold: {RigidFinder.COMPILE_THRESHOLD}")
# Output: 0.975
```

### Why 97.5% and Not 100%?

At sea, you can't wait for perfection. 97.5% accuracy means:
- Roughly 1 error in 40 commands
- Combined with the captain review cycle, errors get caught
- The alternative (running everything through the model) has its own error rate

The threshold balances **speed** (compile early) against **safety** (compile only when confident).

### The Four Compile Requirements

A tile must pass ALL four checks before it compiles:

```
  ┌──────────────────────────────────────────────────────┐
  │                  COMPILE CHECKLIST                    │
  │                                                      │
  │  1. Confidence ≥ 0.975                               │
  │     "Has this been right often enough?"              │
  │                                                      │
  │  2. Used 3+ times                                    │
  │     "Is this a real pattern, not a fluke?"           │
  │                                                      │
  │  3. Error rate < 5%                                  │
  │     "Is it stable? No recent corrections?"           │
  │                                                      │
  │  4. Type = COMMAND                                   │
  │     "Is this compilable? (vision/chart need model)"  │
  │                                                      │
  │  All four must pass. One failure = not compiled.     │
  └──────────────────────────────────────────────────────┘
```

---

## Auto-Regex Generation

The compiler can generate regex patterns from your example text. This is what makes compilation automatic — you don't need to write regex by hand.

### How It Works

```python
from luciddreamer.compiler import RigidFinder

finder = RigidFinder(store)

# Input: "turn port 10 degrees"
# Output: "^turn port (?P<n>\d+) degrees?$"
pattern = finder._auto_pattern("turn port 10 degrees")
print(pattern)
```

### Pattern Generation Rules

The auto-pattern generator does three things:

1. **Escapes everything** — special regex characters are escaped
2. **Replaces numbers with capture groups** — `\d+` becomes `(?P<n>\d+)`
3. **Allows optional 's'** — "degree" matches "degrees"

```python
# Examples:
"turn port 10 degrees"  →  "^turn port (?P<n>\d+) degrees?$"
"reduce to 5 knots"     →  "^reduce to (?P<n>\d+) knots?$"
"head course 270"       →  "^head course (?P<n>\d+)$"
```

### Custom Regex

You can also set regex patterns manually:

```python
from luciddreamer.tiles import CommandTile

tile = CommandTile(
    input_pattern="come about",
    output_action="helm_tack",
    regex_pattern=r"^(come about|tack|hard about)$",  # Custom pattern
    confidence=0.98,
)
```

---

## Audio Tile Compilation

Voice commands can be compiled into **pre-generated audio responses**. Instead of generating TTS at runtime, the audio clip is saved alongside the compiled command.

```python
from luciddreamer.tiles import CommandTile
from luciddreamer.compiler import RigidFinder, CompiledCommand

# Record a command with audio response
tile = CommandTile(
    input_pattern="turn port 10 degrees",
    output_action="helm_port_10",
    audio_response="audio/turn_port_10.wav",   # Pre-generated TTS clip
    confidence=0.98,
    times_used=15,
)
store.add(tile)

# When this compiles, the audio clip is included
finder = RigidFinder(store)
cmd = finder.try_compile(tile)

# Now when the command fires, play the audio file directly
# No TTS generation needed — instant audio response
print(f"Audio clip: {cmd.audio_response}")
```

---

## When NOT to Compile

Not everything should be compiled. Compilation removes the model from the loop, which is great for speed but removes the safety net of inference.

### Safety-Critical Commands

**Compile:**
- "turn port 10 degrees" — routine, well-practiced
- "steady as she goes" — standard command
- "reduce to 5 knots" — common operation

**Do NOT compile (keep model in the loop):**
- "emergency stop" — must always be verified
- "man overboard" — too critical for regex
- "abandon ship" — must always confirm
- "close quarters" — context-dependent

```python
# Mark safety-critical commands as requiring confirmation
tile = CommandTile(
    input_pattern="emergency stop",
    output_action="emergency_stop",
    requires_confirmation=True,  # Always ask, even when compiled
    confidence=0.99,
)
```

### Advisory vs. Execution

| Type | Compile? | Why |
|------|----------|-----|
| Advisory ("you're approaching shallow water") | Yes | Speed matters for alerts |
| Execution ("turn port 10") | Yes, if confidence ≥ 97.5% | Routine, well-practiced |
| Safety-critical ("man overboard") | No | Must always have human in loop |
| Creative/novel ("find me a good anchorage") | No | Model needs flexibility |

---

## The Rigid Structure Finder Algorithm

The `RigidFinder` is the compiler's brain. Here's how it works:

```
  ┌─────────────────────────────────────────────────────────┐
  │              Rigid Structure Finder                      │
  │                                                         │
  │  For each tile in the store:                            │
  │                                                         │
  │  1. Is it a COMMAND tile?                               │
  │     No → skip (vision/chart tiles need model)           │
  │                                                         │
  │  2. Confidence ≥ 0.975?                                │
  │     No → skip (not enough evidence)                     │
  │                                                         │
  │  3. Used 3+ times?                                      │
  │     No → skip (could be a fluke)                        │
  │                                                         │
  │  4. Error rate < 5%?                                    │
  │     No → skip (unstable behavior)                       │
  │                                                         │
  │  5. Has regex_pattern?                                  │
  │     Yes → use it                                        │
  │     No → auto-generate from input_pattern               │
  │                                                         │
  │  6. Create CompiledCommand with:                        │
  │     - regex pattern                                     │
  │     - action                                            │
  │     - audio response (if any)                           │
  │     - confirmation flag                                 │
  │                                                         │
  │  7. Add to compiled command list                        │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
```

### Using the Compiler

```python
from luciddreamer.compiler import RigidFinder
from luciddreamer.tiles import TileStore, CommandTile

store = TileStore()
finder = RigidFinder(store)

# Add a mature tile (ready to compile)
tile = CommandTile(
    input_pattern="turn port 10 degrees",
    output_action="helm_port_10",
    confidence=0.98,
    times_used=20,
    times_correct=20,
    times_corrected=0,
)
store.add(tile)

# Try to compile this specific tile
cmd = finder.try_compile(tile)
if cmd:
    print(f"Compiled: {cmd}")
else:
    print("Not ready to compile")

# Or compile ALL eligible tiles at once
all_compiled = finder.compile_all()
print(f"Compiled {len(all_compiled)} commands")

# Now match inputs against compiled commands
result = finder.match("turn port 10 degrees")
print(result)
# {'action': 'helm_port_10', 'n': '10'}

result = finder.match("something I've never heard")
print(result)
# None → falls through to model
```

---

## Monitoring Compilation Coverage Over Time

Track how your system matures over a season:

```python
from luciddreamer.compiler import RigidFinder
from luciddreamer.bathymetry import BathymetricMap

# After each trip, check coverage
finder = RigidFinder(store)
finder.compile_all()

print(f"Compiled: {finder.compiled_count} commands")
print(f"Total: {len(store)} tiles")
print(f"Coverage: {finder.coverage:.1%}")

# Visualize with the bathymetric map
bathy = BathymetricMap()
bathy.build_from_store(store)
print(bathy.render())
```

### Expected Coverage Timeline

```
  Trip   Coverage   Notes
  ─────  ────────   ──────────────────────────────────
    1       2%      Everything is new. Model does everything.
    5      15%      Most common commands start compiling.
   10      35%      Standard maneuvers are compiled.
   20      55%      The model handles edge cases only.
   30      70%      Most routing hits compiled tiles.
   50      85%      Model fires rarely. System is fast.
  100      92%      Near-complete coverage for this vessel.
```

### Weekly Report

```python
import json
from datetime import datetime

def weekly_report(store, finder):
    """Generate a weekly compilation report."""
    finder.compile_all()
    
    report = {
        "date": datetime.now().isoformat(),
        "total_tiles": len(store),
        "compiled_tiles": finder.compiled_count,
        "coverage": finder.coverage,
        "pending_review": sum(1 for t in store if 0.5 <= t.confidence < 0.9),
        "by_type": {},
    }
    
    from luciddreamer.tiles import TileType
    for tt in TileType:
        tiles = store.find_by_type(tt)
        report["by_type"][tt.value] = len(tiles)
    
    return report

# Run and save
report = weekly_report(store, finder)
with open("reports/weekly_compilation.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"Weekly Report: {report['compiled_tiles']}/{report['total_tiles']} "
      f"compiled ({report['coverage']:.0%})")
```

---

## Next Steps

- [GETTING-STARTED.md](GETTING-STARTED.md) — See compilation in action
- [ARCHITECTURE.md](ARCHITECTURE.md) — Where compilation fits in the system
- [SIMULATORS.md](SIMULATORS.md) — Test compilation before going to sea
