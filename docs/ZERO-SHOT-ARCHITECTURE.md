# Zero-Shot Maritime Agent Architecture

*Assume nothing. Remember everything. Learn continuously.*

## The Core Principle: Zero Context by Default

When a captain yells from the deck, the system treats it as a standalone request. No conversation history. No assumed context. No "as we were discussing earlier." The command must work **zero-shot** — the system's compiled tiles and LoRA weights ARE the context.

```
CAPTAIN (deck):  "COCAPN, HARD TO PORT!"
                          │
                          ▼
              ┌──── Is there active dialog? ────┐
              │                                  │
            NO (default)                       YES
              │                                  │
              ▼                                  ▼
    ZERO-SHOT MODE                    CONTEXTUAL MODE
    (no history)                      (last N exchanges)
              │                                  │
              └──────────┬───────────────────────┘
                         │
                         ▼
              ┌──── Compiled tile match? ────┐
              │                               │
            YES                              NO
              │                               │
     INSTANT EXECUTE                ┌── LoRA zero-shot? ──┐
     (regex + lookup)               │                       │
     ZERO TOKENS                   YES                     NO
     <100ms                         │                       │
                              LoRA INFER              FALLBACK CLOUD
                              (local model)           (Starlink + big API)
                              ~500ms                  ~3-5 sec
```

## Why Zero-Shot First?

On a boat, context is unreliable:

- **Wind noise** — the mic might miss half the words
- **Deck crew talking** — background chatter isn't context for the captain
- **Hours between commands** — the captain isn't maintaining a conversation
- **Emergency commands** — "HARD TO PORT" has to work NOW, not after the system catches up
- **Multiple operators** — the mate gives a command, then the captain, then the deck boss

Every command must work as if it's the first thing the system has ever heard — except the system has **compiled millions of interactions into its weights and tiles**.

## The Three Memory Layers

```
┌─────────────────────────────────────────────────────────┐
│  LAYER 1: COMPILED TILES (instant, zero inference)       │
│                                                         │
│  Regex patterns + lookup tables + audio clips            │
│  Coverage: ~95% of all commands after a season           │
│  Speed: <100ms                                          │
│  Tokens: ZERO                                           │
│                                                         │
│  "turn port 10" → TURN_PORT(10) → "Roger turning 10°"   │
│  "steady"      → HOLD_HEADING  → "Roger, steady on 247" │
│                                                         │
│  This is the bathymetric floor. Solid. Compiled.          │
├─────────────────────────────────────────────────────────┤
│  LAYER 2: LoRA WEIGHTS (local model, zero-shot)          │
│                                                         │
│  Gemma 3 1B-IT + maritime LoRA adapter                   │
│  Coverage: ~4% of commands (novel phrasings)             │
│  Speed: ~500ms on edge hardware                          │
│  Tokens: ~100 (local inference, no cloud)                │
│                                                         │
│  "bring her around easy until the wind's abaft the beam" │
│  → LoRA interprets → TURN_PORT_SLOW(wind_relative > 135) │
│                                                         │
│  The LoRA IS the accumulated knowledge of all past tiles │
│  that didn't compile to regex but the model learned.     │
├─────────────────────────────────────────────────────────┤
│  LAYER 3: CLOUD FALLBACK (Starlink + big API)            │
│                                                         │
│  GPT-4 / Claude / Gemini via satellite                   │
│  Coverage: ~1% (truly novel or complex reasoning)        │
│  Speed: ~3-5 seconds (Starlink latency)                  │
│  Tokens: ~500 (cloud inference)                          │
│                                                         │
│  "The currents are setting us north and we're dragging    │
│   50 fathoms, should we shorten up or move the set?"     │
│  → Cloud reasons about current, depth, gear → answer     │
│                                                         │
│  Every cloud interaction creates training data.           │
│  The cloud's job is to teach, not to serve.               │
└─────────────────────────────────────────────────────────┘
```

## Know Thyself: The Model Capability Map

The system maintains a **self-model** — it knows what it can and can't do:

```python
@dataclass
class ModelSelfProfile:
    """What the system knows about itself."""
    model_name: str = "gemma-3-1b-it"
    lora_adapter: str = "maritime-v3.2"
    
    # Tested capabilities (from simulator runs)
    zero_shot_accuracy: dict[str, float] = field(default_factory=dict)
    # {
    #   "turn_commands": 0.94,
    #   "speed_commands": 0.91,
    #   "depth_queries": 0.73,
    #   "species_id": 0.88,
    #   "emergency_commands": 0.97,
    # }
    
    # Known weaknesses
    weak_areas: list[str] = field(default_factory=list)
    # ["chum_vs_pink_differentiation", "current_interpolation", "slang_variants"]
    
    # LoRA training history
    lora_versions: list[dict] = field(default_factory=list)
    # [{"version": "v3.2", "date": "2026-05-19", "accuracy": 0.91, ...}]
    
    # Compilation coverage
    compiled_coverage: float = 0.0  # Fraction of command space compiled
    
    def can_handle_zero_shot(self, command_type: str) -> bool:
        """Can this model handle this command type without context?"""
        acc = self.zero_shot_accuracy.get(command_type, 0.0)
        return acc >= 0.85  # 85% threshold for zero-shot confidence
    
    def should_defer_to_cloud(self, command_type: str) -> bool:
        """Should this be sent to cloud instead of local?"""
        acc = self.zero_shot_accuracy.get(command_type, 0.0)
        return acc < 0.70  # Below 70% → defer to cloud for safety
    
    def generate_training_data(self) -> list[dict]:
        """Generate synthetic training data for weak areas."""
        # For each weak area, create example input/output pairs
        # These become LoRA training data for overnight fine-tuning
        ...
```

## The Training Loop: Self-Improving Weights

```
┌─────────────────────────────────────────────────────────────┐
│                    CONTINUOUS TRAINING CYCLE                 │
│                                                             │
│  DAY (at sea):                                               │
│  ┌────────────┐    ┌────────────┐    ┌────────────────┐     │
│  │ Captain    │───▶│ Cocapn     │───▶│ Tile created   │     │
│  │ commands   │    │ processes  │    │ + training pair │     │
│  └────────────┘    └────────────┘    └───────┬────────┘     │
│                                              │              │
│                                              ▼              │
│                                     ┌────────────────┐      │
│                                     │ Tile Store     │      │
│                                     │ (grows daily)  │      │
│                                     └───────┬────────┘      │
│                                             │              │
│  NIGHT (overnight):                         │              │
│                                             ▼              │
│  ┌──────────────────────────────────────────────────┐      │
│  │ Local LoRA Fine-Tuning (Jetson/RPi + GPU)        │      │
│  │                                                   │      │
│  │ 1. Extract today's tiles as training pairs         │      │
│  │ 2. Mix with historical data (curriculum)           │      │
│  │ 3. Fine-tune LoRA adapter (1-3 epochs)             │      │
│  │ 4. Run simulators on new weights                   │      │
│  │ 5. Compare accuracy: new vs old                    │      │
│  │ 6. If better → promote to v3.N+1                   │      │
│  │ 7. If worse → rollback + log diff for analysis     │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  WEEKLY (port, Starlink up):                                │
│  ┌──────────────────────────────────────────────────┐      │
│  │ Cloud Batch Training                               │      │
│  │                                                   │      │
│  │ 1. Upload week's tiles + training pairs            │      │
│  │ 2. Cloud trains bigger model or new LoRA           │      │
│  │ 3. Download new LoRA adapter                       │      │
│  │ 4. Run full simulator suite                        │      │
│  │ 5. If better → deploy to edge                      │      │
│  │ 6. If worse → keep local, send diff to cloud       │      │
│  └──────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## LoRA Training Data Generation

The system generates its own training data from tiles:

```python
class TrainingDataGenerator:
    """Generate LoRA training data from accumulated tiles.
    
    Every verified tile becomes a training example:
    - Input: the captain's exact words
    - Output: the action the system took
    - Verification: captain confirmed it was correct
    
    The system also generates VARIATIONS:
    - Synonyms: "turn port 10" → also "come left 10", "turn left 10"
    - Abbreviations: "turn port 10 degrees" → "port 10"
    - Noise: simulate wind, engine noise, partial hearing
    
    And NEGATIVE examples:
    - "what's the weather?" → NOT a navigation command
    - "turn port" without a number → ASK for clarification
    """
    
    def from_tiles(self, store: TileStore) -> list[dict]:
        """Convert verified tiles to LoRA training examples."""
        examples = []
        for tile in store:
            if tile.confidence >= 0.9:  # Only verified tiles
                examples.append({
                    "instruction": tile.input_pattern,
                    "output": tile.output_action,
                    "confidence": tile.confidence,
                    "source": tile.verifier.value,
                })
        return examples
    
    def generate_variations(self, tile: Tile, count: int = 20) -> list[dict]:
        """Generate paraphrase variations of a tile.
        
        "turn port 10 degrees" generates:
        - "port 10"
        - "turn left 10"  
        - "come left 10 degrees"
        - "turn to port 10"
        - "10 degrees port"
        - "port ten"
        - "come around to port ten degrees"
        - etc.
        
        Each variation becomes a training example pointing to the same action.
        This is how the model learns zero-shot generalization.
        """
        variations = self._paraphrase(tile.input_pattern, count)
        return [
            {"instruction": v, "output": tile.output_action}
            for v in variations
        ]
    
    def generate_negatives(self, store: TileStore) -> list[dict]:
        """Generate negative examples (what NOT to do).
        
        From NEGATIVE tiles:
        - "what's for dinner?" → RESPONSE: "Not a navigation command"
        - "turn port" (no number) → RESPONSE: "How many degrees, skipper?"
        
        From corrected tiles:
        - Old wrong answer → mark as incorrect
        - New correct answer → mark as correct
        """
        ...
```

## Rollback and Checkpoint Analysis

Every LoRA training session creates a checkpoint. When accuracy drops:

```
Checkpoint v3.7 (2026-05-18): accuracy 0.91  ← previous best
Checkpoint v3.8 (2026-05-19): accuracy 0.87  ← WORSE! ROLLBACK

Analysis:
  - v3.8 added 47 new training examples from Tuesday's tiles
  - 12 were about "current interpolation" — a known weak area
  - The new examples CONFLICTED with existing knowledge:
    Old: "setting north" means current pushes you north
    New: captain said "setting north" but meant "heading north"
  - The model learned the wrong pattern from ambiguous tiles
  
Fix:
  1. Rollback to v3.7
  2. Flag the 12 ambiguous tiles for captain review
  3. Generate better training data from clarified tiles
  4. v3.9 trains with corrected data
  
The rollback IS the learning. The diff between checkpoints tells you
exactly what went wrong and how to fix it.
```

## Checkpoint Diff Analysis

```python
@dataclass
class CheckpointDiff:
    """Compare two LoRA checkpoints to understand what changed."""
    old_version: str
    new_version: str
    old_accuracy: float
    new_accuracy: float
    delta: float  # positive = improvement, negative = regression
    
    # What training data was added
    new_examples: list[dict] = field(default_factory=list)
    
    # Which command types improved/regressed
    accuracy_by_type: dict[str, float] = field(default_factory=dict)
    # {"turn_commands": +0.02, "depth_queries": -0.05, ...}
    
    # Which tiles were affected
    regressed_tiles: list[str] = field(default_factory=list)
    improved_tiles: list[str] = field(default_factory=list)
    
    @property
    def is_regression(self) -> bool:
        return self.delta < -0.01
    
    def diagnose(self) -> str:
        """Generate human-readable diagnosis of what went wrong."""
        if not self.is_regression:
            return f"Improvement: {self.delta:+.3f} accuracy"
        
        worst = sorted(self.accuracy_by_type.items(), key=lambda x: x[1])
        lines = [f"Regression: {self.delta:+.3f} accuracy"]
        lines.append(f"Worst areas:")
        for area, delta in worst[:3]:
            lines.append(f"  {area}: {delta:+.3f}")
        
        if self.new_examples:
            lines.append(f"New training examples: {len(self.new_examples)}")
            lines.append("Likely cause: conflicting or ambiguous training data")
        
        return "\n".join(lines)
```

## The PLATO Connection

Zero-shot works because PLATO tiles ARE the context — just not at inference time:

```
At TRAINING time:
  PLATO tiles → training data → LoRA weights → the model "knows"
  
At COMPILE time:
  PLATO tiles → regex patterns → compiled code → instant response
  
At INFERERENCE time:
  Captain speaks → compiled match? → YES → instant (zero-shot via tiles)
                             → NO → LoRA zero-shot (knowledge baked into weights)
                                   → CLOUD fallback → creates new tiles for next cycle

The PLATO is the teacher. The compiled tiles are the exam answers
you've memorized. The LoRA is the understanding you've internalized.
The cloud is the tutor you call when you're stuck.
```

## System Prompts as Tiles

System prompts are also versioned and tiled:

```python
SYSTEM_PROMPT_V3_2 = """
You are Cocapn, the maritime intelligence assistant aboard the F/V [vessel].
You understand nautical commands, fish species, navigation, and weather.

CRITICAL RULES:
1. Every command must work standalone — no conversation context assumed
2. Emergency commands ("HARD TO PORT", "MAN OVERBOARD") are ALWAYS highest priority
3. If unsure, ASK — never guess on safety-critical commands
4. Respond in the captain's preferred style (learned from tiles)
5. Depth is in fathoms, speed in knots, heading in degrees true

YOUR CAPABILITIES (tested accuracy):
- Turn commands: 94%
- Speed commands: 91%  
- Depth queries: 73% (defer complex ones to cloud)
- Emergency: 97%
- Species ID: 88%

KNOWN WEAKNESSES:
- Chum vs Pink differentiation (defer to crew)
- Current interpolation (defer to cloud)
- Captain's slang variations (improving daily)
"""
```

## The Full Self-Improvement Loop

```
Day 1:   Compiled tiles: 0%    LoRA: base Gemma 1B    Cloud: 80% of commands
Day 5:   Compiled tiles: 40%   LoRA: v1.0 (local)     Cloud: 30% of commands  
Day 20:  Compiled tiles: 75%   LoRA: v2.3 (local+cloud) Cloud: 10%
Day 50:  Compiled tiles: 90%   LoRA: v3.7 (mostly local) Cloud: 3%
Day 100: Compiled tiles: 95%   LoRA: v5.1 (stable)     Cloud: 1%

Season 2: Compiled tiles: 98%  LoRA: v8.0              Cloud: <1%
          The system runs on a microcontroller.
          The Gemma 1B is for "I've never heard that before."
          The cloud is for "the captain asked a philosophy question."
```

## Token Economics Over Time

```
Trip 1:   ~500 tokens/day (heavy cloud usage)
Trip 5:   ~100 tokens/day (mostly compiled + local LoRA)
Trip 20:  ~20 tokens/day (compiled for most, LoRA for rest)
Trip 50:  ~5 tokens/day (edge cases only)
Trip 100: ~1 token/day (truly novel situations)

At scale (50 boats × 100 days × 1 token):
  Season 1: 50 × 100 × 500 = 2.5M tokens (cloud API cost)
  Season 2: 50 × 100 × 1 = 5K tokens (practically free)
```
