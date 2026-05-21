# Maritime Examples — Real-World Scenarios

> Six scenarios showing LucidDreamer in action, from day one to season end.

---

## Scenario 1: First Day with Autopilot Voice Control

**Boat:** F/V Northern Star  
**Person:** Captain Mike, 25 years fishing  
**Setup:** Raspberry Pi 4, USB headset mic, 7" display

---

Captain Mike just installed LucidDreamer. It's the first trip. The system knows nothing.

### Morning — Departure

```
  Mike: "Turn port 10 degrees."
  
  LucidDreamer:
    [FALLBACK] No compiled tile matches. Model inference...
    Action: helm_port_10
    Confidence: 0.0 (first time ever)
    → Pending review
  
  Mike: (grabs the helm, turns port 10 manually)
       "Yeah, that would've been right."
  
  System: Tile created: "turn port 10 degrees" → helm_port_10
          Confidence: 0.80 (captain confirmed)
```

```python
from luciddreamer.tiles import CommandTile, Verifier
from luciddreamer.router import Router

# What happened in code:
decision, result = router.route("turn port 10 degrees")
# decision = RouteDecision.FALLBACK (nothing compiled yet)

# Captain confirms
tile_id = router.confirm_pending(0, correct=True)
# Creates CommandTile at 0.80 confidence
```

### Mid-Morning — Building Coverage

```
  Mike: "Steady as she goes."
  LucidDreamer: [FALLBACK] → helm_steady → Pending
  
  Mike: "Turn starboard 5 degrees."
  LucidDreamer: [FALLBACK] → helm_starboard_5 → Pending
  
  Mike: "Reduce to 5 knots."
  LucidDreamer: [FALLBACK] → throttle_back → Pending
  
  ...30 minutes later...
  
  Mike: "Turn port 10 degrees."
  LucidDreamer: [COMPILED via fuzzy match, 80%]
    → helm_port_10 ✓
    "Second time for this one. Getting it."
```

### End of Watch — Captain Review

```
  LucidDreamer: "Captain, you have 14 pending items from this watch."
  
  Item 1: "turn port 10 degrees" → helm_port_10
  Mike: ✓ (correct)
  
  Item 2: "steady as she goes" → helm_steady  
  Mike: ✓ (correct)
  
  Item 3: "come left easy" → helm_port_10
  Mike: ✗ "That should be helm_port_5, not 10. 'Easy' means 5 degrees."
  System: Correction tile created. Confidence: 0.90
  
  ...continues through all 14 items...
```

```python
# End-of-watch review
print(f"Pending reviews: {router.pending_count}")  # 14

# Review each
for i in range(router.pending_count):
    # Show pending item to captain
    pending = router._pending[0]
    
    # Captain confirms or corrects
    if captain_approves:
        router.confirm_pending(0, correct=True)
    else:
        router.confirm_pending(0, correct=False, correction=correct_action)
```

### Day 1 Summary

```
  Tiles created:     14
  Compiled:           0 (not enough repetition yet)
  Confidence avg:   0.65 (AMBIGUOUS → TENTATIVE range)
  
  Coverage Map:
  turn        ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%
  steady      ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%
  reduce      ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0%
  
  █ = compiled (zero inference)  ░ = needs model
  
  Status: Everything hits the model. This is normal for day 1.
```

---

## Scenario 2: Fish Sorting with Vision Model

**Boat:** F/V Alaskan Dawn  
**Person:** Deck boss Sarah, crew of 4  
**Setup:** Industrial camera over sorting table, Intel NUC

---

### Trip 5 — Vision Model Getting Started

```
  [Camera captures fish on sorting table]
  
  LucidDreamer Vision:
    Classification: Pacific Halibut
    Confidence: 0.45 (UNKNOWN — first time seeing this species)
    
  Sarah: (looks at screen) "That's a halibut. Hold 3."
  [Presses confirm button]
  
  System: VisionTile created
    Species: Pacific Halibut
    Hold: 3
    Confidence: 0.70 → 0.80 (crew confirmed)
```

```python
from luciddreamer.tiles import VisionTile, Verifier

# Camera captures → model classifies → crew confirms
tile = VisionTile(
    input_pattern="photo_trip05_001.jpg",
    output_action="classify:pacific_halibut",
    species="Pacific Halibut",
    hold_number=3,
    photo_path="/photos/trip05/001.jpg",
    weight_estimate=42.0,
    confidence=0.80,
    verifier=Verifier.DECK_CREW,
    source="edge",
    trip_id="trip_2024_005",
    vessel="F/V Alaskan Dawn",
)
store.add(tile)
```

### Trip 10 — Building Species Library

```
  Sorting 200 fish today:
  
  Pacific Halibut:    67 fish, 94% correct   ████████████░░
  Sablefish:          45 fish, 91% correct   ███████████░░░
  Pacific Cod:        33 fish, 88% correct   ██████████░░░░
  Yellowfin Sole:     28 fish, 85% correct   ██████████░░░░
  Arrowtooth Flounder: 15 fish, 73% correct  ████████░░░░░░
  Rex Sole:           12 fish, 67% correct   ███████░░░░░░░
```

### The Difficult Fish

```
  [Camera captures fish]
  
  LucidDreamer Vision:
    Classification: Pacific Halibut — 0.52 confidence (AMBIGUOUS)
    Alternative: Arrowtooth Flounder — 0.48 confidence
    
  System: "Not sure. Halibut or Arrowtooth?"
  
  Sarah: "Arrowtooth. Look at the teeth."
  [Presses Arrowtooth button]
  
  System: Correction tile created.
    Original: Pacific Halibut (wrong)
    Corrected: Arrowtooth Flounder (right)
    Confidence penalty: -0.10 on halibut tile
    New Arrowtooth tile: 0.90 (correction-weighted)
```

```python
# The correction
halibut_tile.record_use(correct=False)  # Confidence drops by 0.10

# Create correction tile
from luciddreamer.tiles import Tile, TileType

correction = Tile(
    tile_type=TileType.CORRECTION,
    input_pattern="photo_trip10_042.jpg",
    output_action="classify:arrowtooth_flounder",
    parent_tile_id=halibut_tile.tile_id,
    confidence=0.90,
    verifier=Verifier.DECK_CREW,
    metadata={"confused_with": "Pacific Halibut", "reason": "tooth structure"},
)
store.add(correction)
```

---

## Scenario 3: Chart Depth Query During Dragging

**Boat:** F/V Misty Blue  
**Situation:** Trawling in the Bering Sea, dragging in 25 fathoms  
**Concern:** Sea floor rising ahead

---

```
  Captain: "Are we going to remain deep enough for the next 10 minutes?"
  
  Cocapn:
    [Captures chart screen]
    [Projects course at current speed (3.5 knots) and heading (225°)]
    [Reads depth contours along projected path]
    
    "At current speed and heading, you'll cross from 25 fathoms 
     into 18 fathoms in about 4 minutes. After that, it shallows 
     to 14 fathoms at the 8-minute mark. Your gear clears at 12 
     fathoms, so you have about 7 minutes before you need to 
     worry."
  
  Captain: "When do I need to turn?"
  
  Cocapn:
    "At 6 minutes you'll be at about 16 fathoms with your gear 
     at about 8 fathoms off the bottom. That's your window to 
     turn. I'll remind you at 5 minutes."
  
  Captain: "Do it."
  
  Cocapn: [Creates 5-minute reminder tile]
         "Will remind you in 5 minutes. Shallow water ahead."
```

```python
from luciddreamer.tiles import ChartTile, CommandTile, Verifier

# Chart knowledge tile
chart_tile = ChartTile(
    input_pattern="depth_projection_current_route",
    output_action="depth_alert:shallow_approach",
    region="Bering Sea - current position",
    depth_range=(14.0, 25.0),
    features=["rising bottom", "14 fathom minimum on projected path"],
    confidence=0.70,  # TENTATIVE — predictive
    verifier=Verifier.MODEL,
    source="edge",
    metadata={
        "current_speed": 3.5,
        "current_heading": 225,
        "gear_clearance_fathoms": 12,
        "shallow_crossing_minutes": 8,
        "turn_window_minutes": 6,
    },
)
store.add(chart_tile)

# Reminder tile
reminder = CommandTile(
    input_pattern="shallow_water_reminder_5min",
    output_action="alert:shallow_water_ahead",
    requires_confirmation=False,
    confidence=0.95,
    verifier=Verifier.CAPTAIN,
    metadata={"trigger_time": "5_minutes", "depth_alert": True},
)
store.add(reminder)
```

---

## Scenario 4: Captain Review Session on Transit

**Boat:** F/V Fortune  
**Situation:** 8-hour transit, captain has time to review  
**Pending:** 47 items from last trip

---

```
  LucidDreamer: "Captain, you have 47 items to review from trip 22.
                 Estimated time: 15-20 minutes.
                 Start review? [Yes / Later]"
  
  Captain: "Go ahead."
  
  ── Item 1 of 47 ──────────────────────────────────────
  Input: "turn port 10 degrees"
  Action: helm_port_10
  Times seen: 12
  Current confidence: 0.92
  
  [✓ Correct]  [✗ Wrong]  [⏭ Skip]  [🗑 Delete]
  
  Captain: ✓
  
  ── Item 2 of 47 ──────────────────────────────────────
  Input: "come right a bit"  
  Action: helm_starboard_5
  Times seen: 3
  Current confidence: 0.64
  
  Captain: "That should be starboard 10, not 5. 'A bit' means 10 on my boat."
  [✗ Wrong → correction: helm_starboard_10]
  
  ── Item 3 of 47 ──────────────────────────────────────
  Input: "reduce to trolling speed"
  Action: throttle_trolling
  Times seen: 8
  Current confidence: 0.88
  
  Captain: ✓
  
  ...continues...
  
  ── Summary ───────────────────────────────────────────
  Reviewed: 47 items
  Confirmed: 38 (81%)
  Corrected: 7 (15%)
  Deleted: 2 (4%)
  
  New compilations: 12 tiles now above 0.975 threshold
  Compilation triggered for: turn, steady, reduce, increase
  
  Coverage change: 34% → 51% (+17%)
```

```python
# Simulating the review session
confirmed = 0
corrected = 0
deleted = 0

while router.pending_count > 0:
    # Show pending item (in production, this goes to a UI)
    pending = router._pending[0]
    
    # Captain decides
    action = get_captain_decision(pending)  # UI function
    
    if action == "confirm":
        router.confirm_pending(0, correct=True)
        confirmed += 1
    elif action == "correct":
        correction = get_correction()  # UI function
        router.confirm_pending(0, correct=False, correction=correction)
        corrected += 1
    elif action == "delete":
        router._pending.pop(0)
        deleted += 1

# Compile everything that's now ready
compiled = finder.compile_all()
print(f"Review complete: {confirmed}✓ {corrected}✗ {deleted}🗑")
print(f"New compilations: {len(compiled)}")
```

---

## Scenario 5: Buyer Reconciliation

**Boat:** F/V Prospector  
**Situation:** Back in port, reconciling catch with buyer  

---

```
  Buyer's Report:
    Pacific Halibut: 2,340 lbs
    Sablefish:       1,120 lbs  
    Pacific Cod:       890 lbs
    Yellowfin Sole:    445 lbs
  
  LucidDreamer's Count:
    Pacific Halibut: 2,380 lbs  (△ +40 lbs, 1.7%)
    Sablefish:       1,090 lbs  (△ -30 lbs, 2.7%)
    Pacific Cod:       910 lbs  (△ +20 lbs, 2.2%)
    Yellowfin Sole:    460 lbs  (△ +15 lbs, 3.4%)
  
  System: "Within 5% tolerance on all species. 
           Largest discrepancy: Yellowfin Sole (+3.4%).
           Accept buyer's numbers? [Yes / Investigate]"
```

```python
from luciddreamer.tiles import Tile, TileType, Verifier

# Buyer's reconciliation creates verification tiles
buyer_counts = {
    "Pacific Halibut": 2340,
    "Sablefish": 1120,
    "Pacific Cod": 890,
    "Yellowfin Sole": 445,
}

our_counts = {
    "Pacific Halibut": 2380,
    "Sablefish": 1090,
    "Pacific Cod": 910,
    "Yellowfin Sole": 460,
}

for species in buyer_counts:
    discrepancy = abs(buyer_counts[species] - our_counts[species])
    pct = discrepancy / our_counts[species] * 100
    
    # Create reconciliation tile
    tile = Tile(
        tile_type=TileType.VISION,
        input_pattern=f"reconciliation:{species}",
        output_action=f"buyer_count:{buyer_counts[species]}",
        confidence=0.95 if pct < 5 else 0.50,  # Flag large discrepancies
        verifier=Verifier.BUYER,
        source="buyer",
        trip_id="trip_2024_031",
        metadata={
            "our_count": our_counts[species],
            "buyer_count": buyer_counts[species],
            "discrepancy_lbs": discrepancy,
            "discrepancy_pct": round(pct, 1),
        },
    )
    store.add(tile)
    
    if pct < 5:
        # Boost confidence on all vision tiles for this species
        for t in store.find_by_pattern(f"species:{species}"):
            t.record_use(correct=True)  # Buyer agrees → more confidence
```

---

## Scenario 6: Season-End Compilation

**Boat:** F/V Northern Star  
**Situation:** End of season, 52 trips, heading to shipyard  

---

```
  ── Season Summary ────────────────────────────────────
  
  Trips: 52
  Total tiles: 847
  Compiled commands: 623 (73.6%)
  Vision tiles: 156 (species classifications)
  Chart tiles: 42 (chart interpretations)
  Corrections: 26
  
  Bathymetric Coverage Map
  ============================================================
  
    turn            ██████████████████████████████████████░░░  88.0%
    steady          ██████████████████████████████████████████ 100.0%
    reduce          ████████████████████████████████░░░░░░░░░  78.0%
    increase        ██████████████████████████████░░░░░░░░░░░  72.0%
    come            ██████████████████████████░░░░░░░░░░░░░░░  63.0%
    hard            ████████████████████░░░░░░░░░░░░░░░░░░░░░  50.0%
    chart           ██████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░  35.0%
    
    █ = compiled (zero inference)  ░ = needs model
  
  Overall coverage: 73.6%
  
  Model token usage:
    Trip 1:  ~45,000 tokens/day
    Trip 52: ~3,000 tokens/day (93% reduction!)
```

### Export for Next Season

```python
# Export everything for next season
import json

# All tiles
export = store.export_json()
with open("season_2024_tiles.json", "w") as f:
    f.write(export)

# Compiled commands only (for fast edge deployment)
compiled_export = json.dumps([cmd.__dict__ for cmd in finder._compiled], indent=2)
with open("season_2024_compiled.json", "w") as f:
    f.write(compiled_export)

# Season report
report = {
    "season": 2024,
    "vessel": "F/V Northern Star",
    "trips": 52,
    "total_tiles": len(store),
    "compiled_tiles": finder.compiled_count,
    "coverage": finder.coverage,
    "species_tracked": len(set(t.species for t in store if hasattr(t, 'species') and t.species)),
    "corrections": sum(1 for t in store if t.times_corrected > 0),
}
with open("season_2024_report.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"Exported {len(store)} tiles for next season")
print(f"Coverage: {report['coverage']:.1%}")
print(f"Next season starts at {report['coverage']:.0%} instead of 0%")
```

### What Next Season Looks Like

```
  Trip 1, Season 2:
  
  Coverage: 73.6% (carried over from last season)
  Model usage: ~3,000 tokens/day (from the start)
  
  Captain: "Turn port 10 degrees."
  LucidDreamer: [COMPILED] → helm_port_10 (instant, zero inference)
  
  Captain: "Show me the 5-fathom contour."
  LucidDreamer: [COMPILED] → chart_overlay:5fathom (instant)
  
  Only genuinely new situations hit the model.
  The boat remembers everything it learned last year.
```

---

## Next Steps

- [GETTING-STARTED.md](GETTING-STARTED.md) — Start your own season
- [TILES.md](TILES.md) — Deep dive on the tile system
- [COCAPN.md](COCAPN.md) — The chatbot interface
- [SIMULATORS.md](SIMULATORS.md) — Practice before you fish
