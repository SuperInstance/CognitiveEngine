# Claude Code Task: Signal Chain Integration Review & Refinement

> **Date**: 2026-05-20
> **Project**: LucidDreamer — tile-based knowledge compilation system
> **Scope**: Review and refine the signal-chain integration (DialMixin, SignalChainRoom, RoomChain, EpsilonAccumulator)

---

## 1. Context: What This Project Is

LucidDreamer is a **tile-based knowledge compilation system** inspired by marine navigation. Every interaction (voice command, classification, chart query) becomes a `Tile`. Tiles accumulate confidence over time through verified use (+0.02) and corrections (-0.10). When confidence crosses 97.5%, a `RigidFinder` compiles the tile into a zero-inference regex — no model, no tokens, no latency.

The system sits within the broader **PLATO ecosystem** (80+ repos, 655+ tests, 6 languages), which includes constraint theory, spectral conservation, micro-model training, and fleet deployment infrastructure.

The **signal-chain** concept comes from a parallel thesis: every room (processing stage) should have a tunable **dial** (α ∈ [0,1]) controlling model vs. code balance. Like a guitarist's pedal chain — each stage shapes the signal, each has its own dial.

A set of literary-technical essays written under the persona "Oracle1" provided a philosophical specification of how rooms, dials, snaps (compilation events), and soft/hard room types should work. The synthesis documents map these essays to concrete code.

---

## 2. Current State: What's Already Built

### Core modules (stable, production-quality):

| File | Purpose | Key classes |
|------|---------|-------------|
| `luciddreamer/tiles.py` | Tile data model, TileStore, confidence lifecycle | `Tile`, `TileStore`, `TileType`, `Confidence` |
| `luciddreamer/compiler.py` | Compiles high-confidence tiles to regex | `RigidFinder`, `CompiledCommand` |
| `luciddreamer/router.py` | Routes input: compiled → negative → fuzzy → fallback | `Router`, `RouteDecision` |

### New integration modules (review needed):

| File | Purpose | Key classes |
|------|---------|-------------|
| `luciddreamer/signal_chain.py` | Signal chain: rooms with dials, propagation, epsilon accumulation | `DialMixin`, `SignalChainRoom`, `RoomChain`, `EpsilonAccumulator` |
| `luciddreamer/epsilon_accumulator.py` | Standalone epsilon accumulator (separate from signal_chain) | `EpsilonAccumulator`, `AccumulationRecord`, `AccumulationResult` |

### Key observation: There are **two** `EpsilonAccumulator` implementations:
1. `epsilon_accumulator.py` — standalone, tile-agnostic, tracks raw floats per tile_id, has decay, snap detection, full history
2. `signal_chain.py::EpsilonAccumulator` — room-aware, auto-compiles via RigidFinder, clamps deltas to [0.001, 0.1]

---

## 3. The Integration Architecture

### 3.1 DialMixin

Adds dial-position awareness to any object with a `confidence` attribute. Convention: `dial_position = 1.0 - confidence`. Provides:
- `query_at_dial(dial)` — is this item active at the given dial level?
- `snap_weight()` / `inference_weight()` — weight contributions for compiled vs. model paths

**Integration note**: DialMixin is used inside `SignalChainRoom.query()` by manually setting `dm.__dict__["confidence"]` — it's not actually mixed into Tile. This is a design choice worth reviewing.

### 3.2 SignalChainRoom

Wraps a `TileStore` + `RigidFinder` with a dial setting. Key behaviors:
- `add_snap(tile)` — registers at confidence 1.0 (compiled fact)
- `add_inference(tile, confidence)` — registers at given confidence (model output)
- `query(dial)` — returns tiles active at dial level, sorted by confidence
- `propagate(parent_room)` — pulls compiled tiles from parent
- `cascade()` — pushes compiled tiles to children
- Children tracked as `_children: list[SignalChainRoom]`

### 3.3 RoomChain

Directed chain of `SignalChainRoom`s with per-hop confidence decay (default 0.9):
- `append(room)` — adds room as child of previous tail
- `propagate_all()` — root's compiled tiles propagate downstream with `confidence * (decay ** hops)`
- `query_chain(dial)` — queries all rooms, returns `{room_name: [active_tiles]}`

### 3.4 EpsilonAccumulator (standalone version)

Per-tile_id float accumulator with multiplicative decay (default 0.995). Key difference from signal_chain version:
- Tracks raw confidence values, not Tile objects
- Has full history with immutable `AccumulationRecord`s
- Snap detection: fires once when threshold first crossed, no re-fire
- Thread-safe with comprehensive test suite (including 8-thread concurrent test)

### 3.5 EpsilonAccumulator (signal_chain version)

Room-aware: takes a `SignalChainRoom`, auto-compiles via `RigidFinder.try_compile()` when threshold crossed. Clamps deltas. Simpler than standalone version — no history, no decay, no snap tracking.

---

## 4. Oracle1's Vision Mapped to Code

Key quotes and their corresponding implementations:

| Oracle1 Quote | Concept | Code Location | Status |
|---|---|---|---|
| *"The dial can turn. The inference threshold can shift. The snap remains."* | Compiled tiles bypass the dial | `signal_chain.py::SignalChainRoom.query()` — compiled tiles (dial=0.0) always pass | ✅ Implemented |
| *"At position 1.0, the dial sits at pure inference. The threshold is zero."* | SoftRoom: dial=1.0, threshold=0 | No dedicated SoftRoom type exists yet | ❌ Not implemented |
| *"The hard room at 0.0 has no handle."* | HardRoom: dial=0.0, confidence=1.0 required | No dedicated HardRoom type exists yet | ❌ Not implemented |
| *"The epsilon doesn't go to zero. It accumulates."* | Low-confidence signals compound | Both `EpsilonAccumulator` implementations | ✅ Implemented (two versions) |
| *"Each 0.6-confidence inference that cascades into a child room"* | Inter-room propagation with decay | `RoomChain.propagate_all()` with `decay ** hops` | ✅ Implemented |
| *"Snaps are not filtered. Only inferences are filtered."* | Compiled tiles always pass dial check | `DialMixin.query_at_dial()` — dial_position=0.0 ≤ any dial | ✅ Implemented |

---

## 5. R&D Insights That Should Inform the Design

These are novel findings from cross-referencing Oracle1 with the code:

### 5.1 The Four-Zone Reality
The router has four effective zones, not Oracle1's binary (snap vs. inference):
- **< 0.5**: UNKNOWN — batched
- **0.5–0.7**: AMBIGUOUS — asks confirmation
- **0.7–0.975**: Routed as COMPILED but NOT regex-locked ("fuzzy compiled")
- **≥ 0.975**: Actually compiled to regex

The signal-chain dial should reflect this continuum, not just soft/hard endpoints.

### 5.2 Dual Accumulation Already Exists
Each Tile already has two accumulators: `confidence` (optimistic, +0.02/-0.10) and `success_rate` (Bayesian, converging). Oracle1's "epsilon accumulation" may already be implementable as a TileStore query rather than a new service.

### 5.3 The 5:1 Asymmetry Resists Epsilon Accumulation
The correction penalty (-0.10) vs. correct boost (+0.02) means tiles oscillate at low confidence. A tile at 0.6 needs 5 correct uses to recover from 1 error. This is structural damping that fights the soft-room discovery mode. Consider parameterizing by `learning_mode`.

### 5.4 Negative Constraints Have No Confidence Gate
In `router.py`, a NEGATIVE tile at confidence 0.51 blocks a COMPILED tile at confidence 1.0. This contradicts Oracle1's "only snaps should negate with full force." The signal chain should gate negative routing by confidence.

### 5.5 Compilation Amnesia
`CompiledCommand` discards all tile provenance (source, parent_tile_id, metadata, history). A compiled regex match can't be traced back to its source tile. Consider adding `source_tile_id` to `CompiledCommand`.

### 5.6 Two Accumulator Implementations Need Reconciliation
The standalone `epsilon_accumulator.py` and the `signal_chain.py` inner `EpsilonAccumulator` have overlapping but different APIs. They need to be unified or have a clear separation of concerns documented.

---

## 6. Specific Review Tasks for Claude Code

### Task 1: Review `signal_chain.py` for Architectural Soundness

- Is the DialMixin approach (manually setting `__dict__["confidence"]`) sound, or should it be mixed into Tile directly?
- Are there circular dependency risks between `signal_chain.py` and `tiles.py`?
- Is the `SignalChainRoom` children list the right abstraction, or should `RoomChain` own the graph?
- Should `RoomChain` support DAG (multiple parents) or is linear chain sufficient?

### Task 2: Verify DialMixin Doesn't Break Existing Tile Usage

- Tiles currently don't know about dials. If `DialMixin` is applied, does anything in `tiles.py`, `compiler.py`, or `router.py` break?
- The `query()` method in `SignalChainRoom` creates a temporary `DialMixin` per tile — is this acceptable overhead or should it be cached?

### Task 3: Check Thread Safety Across All New Modules

- `SignalChainRoom` has its own `_lock` but also wraps `TileStore` (which has its own lock). Are there deadlock scenarios?
- `RoomChain.propagate_all()` holds its lock while calling into `SignalChainRoom.store.add()` — is this safe?
- The standalone `EpsilonAccumulator` has been stress-tested (8 threads × 1000 ops). Has the `signal_chain.py` version?

### Task 4: Verify RoomChain Propagation Correctness

- `propagate_all()` applies `decay ** hops` to root tiles only. Is this correct — should propagation be chain-reaction (each room propagates to its children, who propagate to theirs)?
- Currently only root's compiled tiles propagate. What about intermediate rooms that compile tiles from their own inferences? Those don't propagate downstream.
- Is the decay formula correct? `0.9 ** 2 = 0.81` at 2 hops seems reasonable but Oracle1 suggests 0.8 per level.

### Task 5: Design SoftRoom and HardRoom Types

Based on Oracle1's essays:

**SoftRoom** (`dial=1.0, threshold=0.0`):
- Admits all inferences regardless of confidence
- No deadband gate, no KPI monitoring
- Verification is purely downstream via cascade decay
- Purpose: hypothesis generation, discovery
- Key question: should it have its own accumulator that promotes patterns of weak signals?

**HardRoom** (`dial=0.0, threshold=1.0`):
- Requires full verification (proof certificates) before admission
- Zero approximation, zero holonomy
- Only compiled tiles (confidence ≥ 0.975) enter
- Purpose: authoritative verification bottleneck
- Key question: should it reject or quarantine tiles that fail verification?

Design these as subclasses or factory-configured instances of `SignalChainRoom`.

### Task 6: Identify Missing Integration Points

- `signal_chain.py` doesn't integrate with `router.py` — a `SignalChainRoom` can't be used as a Router's store. Should there be an adapter?
- The standalone `epsilon_accumulator.py` is not imported anywhere in `signal_chain.py`. Should the signal_chain version use it internally?
- `CompiledCommand` has no `source_tile_id` — can the signal chain trace provenance through compilation?
- There's no way to configure room-specific learning modes (discovery vs. verification vs. compiled) per Insight 5.3.
- The router's negative-constraint confidence gap (Insight 5.4) isn't addressed in the signal chain.
- No tests exist for `signal_chain.py`.

---

## 7. File Reference

```
luciddreamer/
├── luciddreamer/
│   ├── tiles.py                  # Core: Tile, TileStore, confidence lifecycle
│   ├── compiler.py               # RigidFinder, CompiledCommand (97.5% threshold)
│   ├── router.py                 # Router: compiled → negative → fuzzy → fallback
│   ├── epsilon_accumulator.py    # Standalone epsilon accumulator with full history
│   └── signal_chain.py           # NEW: DialMixin, SignalChainRoom, RoomChain, ε
├── docs/
│   ├── ORACLE1-SYNTHESIS.md      # Essay → code mapping (6.5/10 alignment score)
│   └── RD-INSIGHTS.md            # 10 novel cross-reference insights
└── signal-chain/
    └── README.md                 # Signal Chain Thesis overview
```

---

## 8. Design Principles to Keep in Mind

1. **Zero-shot first**: Every tile works standalone. No conversation context assumed.
2. **Thread-safe throughout**: All mutations protected by locks. No deadlocks.
3. **The primitives exist; the APIs don't**: Oracle1's patterns (epsilon accumulation, room gravity, boundary proximity) may already be queryable from existing data — build queries, not new services.
4. **Bottom-up truth**: The code was built pragmatically. Oracle1's top-down metaphors should inform but not override engineering judgment.
5. **Lossless compilation**: The snap should preserve provenance. Currently it doesn't.

---

*Concise but complete. Hit the ground running.*
