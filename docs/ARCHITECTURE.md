# Architecture — How LucidDreamer Fits Together

> The system learns your boat until it doesn't need to think anymore.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LUCIDDREAMER SYSTEM                        │
│                                                                     │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│   │  Voice   │    │  Camera  │    │  Chart   │    │  Buyer   │    │
│   │ Commands │    │  (Fish)  │    │   ENC    │    │   Data   │    │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    │
│        │               │               │               │            │
│        └───────────────┴───────────────┴───────────────┘            │
│                                │                                    │
│                        ┌───────▼───────┐                            │
│                        │    Router      │                            │
│                        │  (Gatekeeper)  │                            │
│                        └───────┬───────┘                            │
│                                │                                    │
│                 ┌──────────────┼──────────────┐                     │
│                 │              │              │                      │
│          ┌──────▼──────┐ ┌────▼────┐ ┌───────▼───────┐             │
│          │  Compiled   │ │ Negative│ │    Fallback   │             │
│          │  (Regex)    │ │  Tiles  │ │    (Model)    │             │
│          │  0 tokens   │ │ BLOCKED │ │  Costs tokens │             │
│          └──────┬──────┘ └────┬────┘ └───────┬───────┘             │
│                 │              │              │                      │
│                 └──────────────┼──────────────┘                      │
│                                │                                    │
│                        ┌───────▼───────┐                            │
│                        │  Tile Store    │                            │
│                        │  (Memory)      │                            │
│                        └───────┬───────┘                            │
│                                │                                    │
│                 ┌──────────────┼──────────────┐                     │
│                 │              │              │                      │
│          ┌──────▼──────┐ ┌────▼──────┐ ┌─────▼──────┐              │
│          │  Compiler   │ │Bathymetry │ │   Export   │              │
│          │ (RigidFind) │ │   Map     │ │  / Import  │              │
│          └─────────────┘ └───────────┘ └────────────┘              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Cloud → Edge → Human Data Flow

The system operates across three environments. Data flows between them, but the edge runs independently.

```
  ┌─────────────────────────────────────┐
  │           CLOUD (Shore)             │
  │                                     │
  │  ┌───────────┐  ┌───────────────┐   │
  │  │ Big Model │  │ Captain       │   │
  │  │ (GPT-4 /  │  │ Review        │   │
  │  │  Claude)  │  │ Dashboard     │   │
  │  └─────┬─────┘  └───────┬───────┘   │
  │        │                │            │
  │        └────────┬───────┘            │
  │                 │                    │
  │         ┌───────▼────────┐           │
  │         │  Tile Compiler │           │
  │         │  + Abstraction │           │
  │         └───────┬────────┘           │
  │                 │ Export compiled     │
  └─────────────────┼────────────────────┘
                    │ tiles.json
                    │ (USB stick, sat link,
                    │  or cell when in range)
                    ▼
  ┌─────────────────────────────────────┐
  │          EDGE (Boat)                │
  │                                     │
  │  ┌───────────┐  ┌───────────────┐   │
  │  │ Gemma 3   │  │ Compiled      │   │
  │  │ 1B-IT     │  │ Regex Tiles   │   │
  │  │ (fallback)│  │ (fast path)   │   │
  │  └─────┬─────┘  └───────┬───────┘   │
  │        └────────┬────────┘           │
  │                 │                    │
  │         ┌───────▼────────┐           │
  │         │    Router      │           │
  │         └───────┬────────┘           │
  │                 │                    │
  │    ┌────────────┼────────────┐       │
  │    │            │            │       │
  │  ┌─▼──┐  ┌─────▼──┐  ┌─────▼──┐    │
  │  │Helm│  │Sorting │  │ Charts │    │
  │  │    │  │Camera  │  │        │    │
  │  └────┘  └────────┘  └────────┘    │
  │                                     │
  │  Logs new interactions ─────────────┼──▶ Pending
  │  (for later review)                 │    Review Queue
  └─────────────────────────────────────┘
                    │
                    │ When in port:
                    │ sync pending reviews
                    ▼
  ┌─────────────────────────────────────┐
  │         HUMAN (Captain / Crew)      │
  │                                     │
  │  ┌───────────┐  ┌───────────────┐   │
  │  │ Captain   │  │ Deck Crew     │   │
  │  │ Reviews   │  │ Confirms      │   │
  │  │ Pending   │  │ Species IDs   │   │
  │  └───────────┘  └───────────────┘   │
  │                                     │
  │  ┌───────────┐  ┌───────────────┐   │
  │  │ Buyer     │  │ Simulator     │   │
  │  │ Recon-    │  │ Test Runs     │   │
  │  │ ciliation │  │ Before Sea    │   │
  │  └───────────┘  └───────────────┘   │
  └─────────────────────────────────────┘
```

### Key Insight

The edge is **self-sufficient**. If you lose connectivity, the compiled tiles keep working. The model only needs to fire for novel inputs, and it logs those for later review when you're back in port.

---

## Tile Lifecycle

Every piece of knowledge goes through a lifecycle from uncertain observation to compiled certainty.

```
   CREATION           VERIFICATION           COMPILATION
      │                    │                      │
      ▼                    ▼                      ▼

 ┌─────────┐        ┌──────────┐          ┌──────────┐
 │  New    │───────▶│ Verified │─────────▶│ Compiled │
 │  Tile   │        │ by Human │          │ (Regex)  │
 │ conf=0.5│        │ conf=0.8+│          │ conf=1.0 │
 └─────────┘        └──────────┘          └──────────┘
      │                    │
      │                    │
      ▼                    ▼
 ┌─────────┐        ┌──────────┐
 │ Ambiguous│        │ Corrected│
 │ conf=0.5 │        │ Negative │
 │ (review) │        │ Knowledge│
 └──────────┘        └──────────┘

 Timeline:
 Day 1:   Tile created from voice command or model fallback
 Day 2-5: Tile verified by captain or crew (confidence rises)
 Day 5-20: Tile used successfully multiple times (confidence → 0.975+)
 Day 20+:  Tile compiled to regex (confidence = 1.0, zero inference)
```

### Creation

A tile is born when:
- The model processes a new input (fallback path)
- The captain gives a voice command
- The deck crew confirms a species ID
- A chart interpretation is recorded

### Verification

A tile gains trust through:
- **Model verification** — the model agrees with itself on re-runs
- **Captain verification** — the captain says "yes, that's right"
- **Deck crew verification** — crew confirms fish sorting
- **Buyer verification** — buyer's count matches our classification
- **Simulation verification** — works correctly in the simulator

Each verification source has different weight. Captain verification is strongest.

### Compilation

When a tile crosses the 97.5% confidence threshold with 3+ uses and low error rate, the `RigidFinder` compiler converts it into a `CompiledCommand` with a regex pattern. From that point on, matching inputs skip the model entirely.

---

## The Confidence Continuum

Confidence isn't binary — it's a continuum that determines system behavior:

```
 100%  ──────────────────────────────────────────────────
       │ COMPILED                                    │
 97.5% │ ─ ─ ─ Compile Threshold (from dream.rs) ─ ─│
       │ VERIFIED                                    │
  90%  │ ─ ─ ─ Execute + brief confirm ─ ─ ─ ─ ─ ─ │
       │                                             │
  70%  │ ─ ─ ─ TENTATIVE ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
       │        Execute tentatively, ask captain     │
  50%  │ ─ ─ ─ AMBIGUOUS ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
       │        Don't execute, ask captain           │
   0%  │ UNKNOWN                                    │
       │        Batch for review                     │
  0%   ──────────────────────────────────────────────────
```

### What Happens at Each Level

| Confidence | Class | Behavior | Example |
|---|---|---|---|
| 100% | COMPILED | Silent execution, zero inference | "turn port 10" → instant helm command |
| 90-99% | VERIFIED | Execute + brief confirmation | "steady as she goes" → execute + "Steadying" |
| 70-89% | TENTATIVE | Execute tentatively, ask | Unusual heading change → execute + "Confirm?" |
| 50-69% | AMBIGUOUS | Don't execute, ask captain | Ambiguous command → "Did you mean...?" |
| <50% | UNKNOWN | Batch for later review | Unrecognized → logged, no action |

### The Asymmetry of Learning

Correct uses nudge confidence **up slowly** (+0.02), while corrections push it **down fast** (-0.10). This 5:1 asymmetry means the system is cautious by default — it takes a lot of consistent good behavior to build trust, but one clear mistake erodes it quickly.

```python
# This is baked into Tile.record_use():
if correct:
    self.confidence = min(1.0, self.confidence + 0.02)   # Slow rise
else:
    self.confidence = max(0.0, self.confidence - 0.10)    # Fast fall
```

---

## Model Shrinkage Over Time

The biggest advantage of LucidDreamer: the model matters less over time.

```
 Trip 1 (Day 1):                     Trip 50 (End of Season):
 ┌──────────────────────┐           ┌──────────────────────┐
 │  ░░░░░░░░░░░░░░░░░░  │           │  ████████████████████ │
 │  ░░░░░░░░░░░░░░░░░░  │           │  ████████████████████ │
 │  ░░░░░░░░░░░░░░░░░░  │           │  ████████████████░░░  │
 │  ░░░░░░░░░░░░░░░░░░  │           │  ████████████████░░░  │
 │  ░░░░░░░░░░░░░░░░░░  │           │  ████████████████████ │
 │  ░░░░░░░░░░░░░░░░░░  │           │  ████████████████████ │
 │  ░░░░░░░░░░░░░░░░░░  │           │  ████████████████████ │
 │                      │           │                      │
 │  95% model inference │           │  5% model inference  │
 │  5% compiled tiles   │           │  95% compiled tiles  │
 └──────────────────────┘           └──────────────────────┘
```

On Trip 1, almost everything hits the model. By Trip 50, the model only fires for genuinely novel situations. This means:

- **Token costs drop** over the season
- **Latency drops** — compiled regex is instant
- **Reliability increases** — no model hallucination on known commands
- **Edge deployment becomes viable** — you need a smaller fallback model

### The Amnesia Cliff

There's a critical minimum: **10% coverage**. Below this threshold, the model can't reliably distinguish known from unknown inputs. It's like navigating with a chart that's 90% blank — you can't tell if you're in safe water or about to hit a rock.

The system warns you when coverage drops below this threshold:

```python
from luciddreamer.bathymetry import BathymetricMap

bathy = BathymetricMap()
bathy.build_from_store(store)

if bathy.overall_coverage < 0.10:
    print("⚠️  WARNING: Below amnesia cliff (10% coverage)")
    print("   The model cannot reliably route inputs.")
    print("   Run more training data or simulator sessions.")
```

---

## Integration with SuperInstance Ecosystem

LucidDreamer doesn't exist in isolation. It's part of the SuperInstance ecosystem — a family of tools that work together:

```
 ┌────────────────────────────────────────────────────────────┐
 │                    SuperInstance Ecosystem                 │
 │                                                            │
 │  ┌──────────────────┐      ┌──────────────────────┐       │
 │  │ luciddreamer     │      │ eisenstein-embed      │       │
 │  │ (Maritime Intel) │◀────▶│ (Embedding Search)    │       │
 │  │                  │      │ Semantic tile matching │       │
 │  │ - Tiles          │      │ "find me tiles like    │       │
 │  │ - Compiler       │      │  this one"            │       │
 │  │ - Bathymetry     │      └──────────────────────┘       │
 │  │ - Router         │                                      │
 │  └────────┬─────────┘      ┌──────────────────────┐       │
 │           │                │ tensor-spline         │       │
 │           │                │ (Time Series)         │       │
 │           │                │ Bathymetry over time  │       │
 │           │                │ Coverage trend lines  │       │
 │           │                └──────────────────────┘       │
 │           │                                               │
 │           │                ┌──────────────────────┐       │
 │           │                │ Cocapn                │       │
 │           │                │ (Chatbot + Nav)       │       │
 │           │                │ Screen capture → tiles│       │
 │           │                │ Mouse output to ECDIS │       │
 │           │                └──────────────────────┘       │
 │           │                                               │
 │  ┌────────▼─────────┐     ┌──────────────────────┐       │
 │  │   dream.rs        │     │ SuperInstance Core    │       │
 │  │   (Experiments)   │     │ (Common Runtime)      │       │
 │  │   Compile thresh  │     │ Config, logging,      │       │
 │  │   97.5% accuracy  │     │ health checks         │       │
 │  └──────────────────┘     └──────────────────────┘       │
 │                                                            │
 └────────────────────────────────────────────────────────────┘
```

### How They Connect

| Tool | Role | Connection |
|------|------|-----------|
| **eisenstein-embed** | Semantic search | Finds similar tiles when exact match fails; powers fuzzy tile matching |
| **tensor-spline** | Time series | Tracks coverage trends; predicts when compilation will trigger |
| **Cocapn** | Chatbot interface | Uses LucidDreamer's router; creates tiles from chart interactions |
| **dream.rs** | Research | Experimentally determined the 97.5% compile threshold |
| **SuperInstance Core** | Runtime | Shared config, logging, health monitoring |

### Embedding-Based Tile Matching

When the compiled regex and fuzzy match both miss, `eisenstein-embed` provides semantic search:

```python
# Conceptual integration
from eisenstein_embed import EmbeddingIndex

# Index all tile input_patterns
index = EmbeddingIndex()
for tile in store:
    index.add(tile.input_pattern, metadata=tile.to_dict())

# Find similar tiles
results = index.search("come left a bit", top_k=3)
# → [("turn port 10 degrees", 0.87), ("turn port 15 degrees", 0.82), ...]
```

This provides the "fuzzy" matching layer between compiled regex and full model inference.

---

## Hardware Recommendations

### Minimal Setup (Getting Started)

```
┌──────────────────────────────────┐
│        Raspberry Pi 4 (4GB)      │
│  ┌────────┐  ┌────────┐         │
│  │ USB    │  │ USB    │         │
│  │ Mic    │  │ Cam    │         │
│  └────────┘  └────────┘         │
│  ┌────────┐  ┌────────┐         │
│  │ 7"     │  │ GPS    │         │
│  │ Display│  │ Puck   │         │
│  └────────┘  └────────┘         │
│                                  │
│  Cost: ~$300-500                 │
│  Runs: Compiled tiles + small    │
│        model (Gemma 3 1B Q4)    │
└──────────────────────────────────┘
```

### Production Setup (Full Season)

```
┌──────────────────────────────────┐
│      Intel NUC i5, 16GB RAM      │
│  ┌────────┐  ┌────────────┐     │
│  │ Headset│  │ Industrial │     │
│  │ Mic    │  │ Camera     │     │
│  └────────┘  └────────────┘     │
│  ┌────────────┐  ┌──────────┐   │
│  │ 10" Sun-   │  │ NMEA     │   │
│  │ readable   │  │ 2000     │   │
│  │ Display    │  │ Bridge   │   │
│  └────────────┘  └──────────┘   │
│  ┌────────────┐                  │
│  │ Starlink   │  (for sync in    │
│  │ Mini       │   port only)     │
│  └────────────┘                  │
│                                  │
│  Cost: ~$1,500-2,500             │
│  Runs: Full model + vision +     │
│        compiled tiles            │
└──────────────────────────────────┘
```

### GPU-Accelerated Setup (Vision-Heavy)

For boats doing heavy fish sorting with vision:

```
┌──────────────────────────────────┐
│   Intel NUC + NVIDIA T1000       │
│   (or any small form factor GPU) │
│                                  │
│   Enables:                       │
│   - Real-time fish classification│
│   - Faster model inference       │
│   - Multiple camera feeds        │
│                                  │
│   Cost: ~$2,500-4,000            │
└──────────────────────────────────┘
```

---

## The Promotion Ladder

The system doesn't just learn — it promotes. As knowledge compiles, the inference engines don't retire. They move up in abstraction, like a military career:

```
  Rank          What runs             Mental budget spent on
  ──────────    ──────────────        ──────────────────────
  Recruit       Cloud LLM everything  Nothing left over
  Corporal      Local model 80%       Recognizing patterns
                Cloud for novel       Flagging unknowns
  Sergeant      Tiles handle routine  Connecting patterns
                Model reviews         across domains
  Lieutenant    Hard code routine     Strategy — what rooms
                Tiles review          to explore next
  Captain       System runs itself    Values — should we
                Reviews with human    even do this?
```

At every level, freed-up capacity goes to the next meta layer:

- **Recruit → Corporal**: Cloud model generates initial tiles. Local model takes over the easy ones. Cloud still handles novel inputs.
- **Corporal → Sergeant**: Local model now selects tiles instead of generating from scratch. Same tokens spent reviewing transcripts, not generating "Roger, turning port 10". The model sees the transcript and thinks: *"We keep sorting Chinook wrong near that shelf break — the depth contour data might help."*
- **Sergeant → Lieutenant**: Tiles are compiled to hard code. The local model's job shifts to cross-domain pattern recognition — connecting fish logs with bathymetry with buyer reconciliation data.
- **Lieutenant → Captain**: The system proposes new abstractions. *"We have 300 compiled tiles for heading changes. I notice 40 of them cluster around tide changes. Should we create a TIDE_AWARE heading tile?"* The human makes the call.

### The Model Never Retires

This is the key insight. The local model that used to spend 500 tokens generating a response now spends those same 500 tokens on staff work:

- Reviewing the last 20 interactions for anomalies
- Cross-referencing bathymetry with fish sorting logs
- Pre-generating tomorrow's likely commands from heading + tide tables
- Detecting drift: *"We've corrected the same fish 5 times this trip — is the vision model degrading?"*

The 5:1 learning asymmetry (correct +0.02, correction -0.10) is exactly how you want a soldier to learn — slow to trust, fast to adapt when proven wrong.

### Domain-Independent

The promotion ladder isn't maritime-specific:

| Domain | Recruit | Sergeant | Captain |
|--------|---------|----------|---------|
| Maritime | Cloud handles every command | Compiled tiles steer the boat | System proposes tide-aware routing |
| Retail | Cloud IDs every shelf item | Compiled tiles track SKUs | System notices seasonal shrinkage patterns |
| Website | Cloud answers every visitor | Compiled tiles handle FAQ | System proposes new conversion paths |
| Healthcare | Cloud triages every symptom | Compiled tiles handle common presentations | System flags population-level trends |

Every domain has the same three anchors: **ground truth source**, **tile lifecycle**, **competition between compiled and fresh inference**.

---

## Next Steps

- [GETTING-STARTED.md](GETTING-STARTED.md) — Hands-on walkthrough
- [TILES.md](TILES.md) — Deep dive on tiles
- [COMPILATION.md](COMPILATION.md) — How soft becomes hard
- [COCAPN.md](COCAPN.md) — The chatbot interface
