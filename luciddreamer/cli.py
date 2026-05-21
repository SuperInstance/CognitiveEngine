"""LucidDreamer CLI — test and manage your maritime intelligence system.

Usage:
    luciddreamer simulate autopilot [--count 50] [--difficulty 0.3] [--seed 42]
    luciddreamer simulate fish [--count 100] [--error-rate 0.05] [--seed 42]
    luciddreamer simulate chart [--count 20] [--seed 42]
    luciddreamer simulate trip [--seed 42]
    luciddreamer tiles list [--type COMMAND]
    luciddreamer tiles compile
    luciddreamer bathymetry
    luciddreamer beta-test
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .tiles import TileStore, TileType
from .compiler import RigidFinder
from .bathymetry import BathymetricMap
from .simulators import (
    AutopilotSimulator,
    FishSortSimulator,
    ChartSimulator,
    CaptainReviewSimulator,
    FullTripSimulator,
)


def _print_json(obj, indent=2):
    """Print a JSON-serializable object, filtering non-serializable keys."""
    if isinstance(obj, dict):
        clean = {k: v for k, v in obj.items()
                 if not isinstance(v, (TileStore, RigidFinder))}
        # Also strip raw tile lists for readability
        if "tiles" in clean and isinstance(clean["tiles"], list) and len(clean["tiles"]) > 5:
            clean["tiles"] = f"<{len(clean['tiles'])} tiles>"
        print(json.dumps(clean, indent=indent, default=str))
    else:
        print(json.dumps(obj, indent=indent, default=str))


# ---- simulate subcommands ----

def cmd_simulate_autopilot(args):
    sim = AutopilotSimulator(
        count=args.count, difficulty=args.difficulty,
        seed=args.seed, vessel=args.vessel,
    )
    result = sim.run()
    print(f"\n=== Autopilot Simulation ({result['total']} commands) ===\n")
    print(f"  By category:")
    for cat, n in sorted(result["by_category"].items()):
        print(f"    {cat:15s} {n:4d}")
    print(f"\n  Average confidence: {result['avg_confidence']:.3f}")
    print(f"  Tiles generated:    {len(result['tiles'])}")
    # Show a few samples
    print(f"\n  Sample commands:")
    for cmd in sim.generate_commands(5):
        print(f"    \"{cmd['text'][:50]}\"  →  {cmd['expected_action']}")
    return result


def cmd_simulate_fish(args):
    sim = FishSortSimulator(
        count=args.count, error_rate=args.error_rate,
        seed=args.seed, vessel=args.vessel,
    )
    result = sim.run()
    print(f"\n=== Fish Sort Simulation ({result['total']} events) ===\n")
    print(f"  Species distribution:")
    for sp, n in sorted(result["species_distribution"].items(), key=lambda x: -x[1]):
        print(f"    {sp:20s} {n:4d}")
    print(f"\n  Total weight:        {result['total_weight']} lbs")
    print(f"  Misclassifications:  {result['misclassifications']} ({result['misclassification_rate']:.1%})")
    print(f"\n  Buyer reconciliation:")
    for r in result["reconciliation"]:
        flag = " ⚠" if r["discrepancy"] != 0 else ""
        print(f"    {r['species']:20s} vessel={r['vessel_count']:3d}  buyer={r['buyer_count']:3d}{flag}")
    return result


def cmd_simulate_chart(args):
    sim = ChartSimulator(count=args.count, seed=args.seed, vessel=args.vessel)
    result = sim.run()
    print(f"\n=== Chart Simulation ({result['total']} queries) ===\n")
    print(f"  By type:")
    for t, n in sorted(result["by_type"].items()):
        print(f"    {t:15s} {n:4d}")
    # Show sample queries
    print(f"\n  Sample queries:")
    for q in result["tiles"][:5]:
        print(f"    \"{q.input_pattern[:50]}\"  ({q.metadata.get('query_type', 'unknown')})")
    return result


def cmd_simulate_trip(args):
    sim = FullTripSimulator(seed=args.seed, vessel=args.vessel)
    result = sim.run()
    print(f"\n{'='*60}")
    print(f"  FULL TRIP SIMULATION — {result['trip_id']}")
    print(f"  Vessel: {result['vessel']}")
    print(f"{'='*60}\n")

    p = result["phases"]
    print(f"  Phase 1 — Steam Out:")
    print(f"    Autopilot commands: {p['steam_out']['autopilot']}")
    print(f"    Chart queries:      {p['steam_out']['chart']}")

    print(f"\n  Phase 2 — Fishing:")
    print(f"    Fish events:        {p['fishing']['fish_events']}")
    print(f"    Misclassifications: {p['fishing']['misclassifications']}")
    print(f"    Total weight:       {p['fishing']['total_weight']} lbs")

    print(f"\n  Phase 3 — Captain Review:")
    print(f"    Sessions:           {p['review']['sessions']}")
    print(f"    Tiles reviewed:     {p['review']['tiles_reviewed']}")
    print(f"    Final coverage:     {p['review']['final_coverage']:.1%}")

    print(f"\n  Phase 4 — Steam Back:")
    print(f"    Autopilot commands: {p['steam_back']['autopilot']}")
    print(f"    Chart queries:      {p['steam_back']['chart']}")

    print(f"\n  {'─'*50}")
    print(f"  Total tiles:            {result['total_tiles']}")
    print(f"  Compiled commands:      {result['compilation_stats']['compiled_commands']}")
    print(f"  Coverage:               {result['compilation_stats']['coverage']:.1%}")
    print(f"  Bathymetric coverage:   {result['bathymetric_coverage']:.1%}")
    print(f"\n  Coverage by tile type:")
    for tt, n in result["coverage_by_type"].items():
        if n > 0:
            print(f"    {tt:15s} {n:4d}")
    print(f"\n{result['bathymetry']}")
    return result


# ---- tiles subcommands ----

def cmd_tiles_list(args):
    """List tiles from a simulation."""
    store = _build_store_from_sim(args)
    tile_type = None
    if args.type:
        try:
            tile_type = TileType(args.type.lower())
        except ValueError:
            print(f"Unknown tile type: {args.type}")
            print(f"Valid types: {', '.join(t.value for t in TileType)}")
            return

    if tile_type:
        tiles = store.find_by_type(tile_type)
    else:
        tiles = list(store)

    print(f"\n{len(tiles)} tiles{' (' + args.type + ')' if args.type else ''}:\n")
    for t in tiles[:50]:  # cap display
        conf_bar = "█" * int(t.confidence * 20) + "░" * (20 - int(t.confidence * 20))
        print(f"  [{t.tile_type.value:10s}] {t.input_pattern[:40]:40s} {conf_bar} {t.confidence:.2f}")
    if len(tiles) > 50:
        print(f"  ... and {len(tiles) - 50} more")


def cmd_tiles_compile(args):
    """Compile tiles and show results."""
    store = _build_store_from_sim(args)
    finder = RigidFinder(store)
    compiled = finder.compile_all()

    print(f"\nCompilation Results:")
    print(f"  Total tiles:    {len(store)}")
    print(f"  Compiled:       {len(compiled)}")
    print(f"  Coverage:       {finder.coverage:.1%}")
    print()
    for cmd in compiled:
        print(f"  {cmd.pattern!r:45s} → {cmd.action}")


# ---- bathymetry ----

def cmd_bathymetry(args):
    """Render the bathymetric coverage map."""
    store = _build_store_from_sim(args)
    bathy = BathymetricMap()
    bathy.build_from_store(store)
    print(bathy.render())
    print(f"\nOverall coverage: {bathy.overall_coverage:.1%}")


# ---- beta-test ----

def cmd_beta_test(args):
    """Run all simulators and check scores."""
    print(f"\n{'='*60}")
    print(f"  LUCIDDREAMER BETA TEST")
    print(f"{'='*60}\n")

    seed = args.seed or 42
    scores = {}
    all_pass = True

    # 1. Autopilot
    print("▶ Autopilot Simulator...")
    ap = AutopilotSimulator(count=50, seed=seed)
    ap_result = ap.run()
    assert ap_result["total"] == 50, "Autopilot count mismatch"
    assert len(ap_result["by_category"]) > 0, "No categories generated"
    scores["autopilot"] = ap_result["avg_confidence"]
    print(f"  ✓ {ap_result['total']} commands, avg confidence {ap_result['avg_confidence']:.3f}")

    # 2. Fish Sort
    print("▶ Fish Sort Simulator...")
    fs = FishSortSimulator(count=100, seed=seed)
    fs_result = fs.run()
    assert fs_result["total"] == 100, "Fish count mismatch"
    assert len(fs_result["species_distribution"]) > 0, "No species"
    scores["fish_sort"] = 1.0 - fs_result["misclassification_rate"]
    print(f"  ✓ {fs_result['total']} events, {fs_result['misclassification_rate']:.1%} misclassified")

    # 3. Chart
    print("▶ Chart Simulator...")
    ch = ChartSimulator(count=20, seed=seed)
    ch_result = ch.run()
    assert ch_result["total"] == 20, "Chart count mismatch"
    scores["chart"] = ch_result["total"] / 20
    print(f"  ✓ {ch_result['total']} queries generated")

    # 4. Captain Review
    print("▶ Captain Review Simulator...")
    rv = CaptainReviewSimulator(seed=seed)
    rv_result = rv.run()
    assert rv_result["total_tiles"] > 0, "No tiles reviewed"
    scores["review"] = rv_result["final_coverage"]
    print(f"  ✓ {rv_result['total_sessions']} sessions, coverage {rv_result['final_coverage']:.1%}")

    # 5. Full Trip
    print("▶ Full Trip Simulator...")
    trip = FullTripSimulator(seed=seed)
    trip_result = trip.run()
    assert trip_result["total_tiles"] > 0, "No tiles in trip"
    assert "phases" in trip_result, "Missing phases"
    scores["full_trip"] = trip_result["compilation_stats"]["coverage"]
    print(f"  ✓ Trip {trip_result['trip_id']}: {trip_result['total_tiles']} tiles, "
          f"{trip_result['compilation_stats']['coverage']:.1%} compiled")

    # Summary
    overall = sum(scores.values()) / len(scores)
    print(f"\n{'─'*60}")
    print(f"  SCORES:")
    for name, score in scores.items():
        status = "✓" if score > 0.5 else "✗"
        print(f"    {status} {name:15s} {score:.3f}")
    print(f"\n  Overall: {overall:.3f}  {'PASS ✓' if overall > 0.5 else 'FAIL ✗'}")
    print(f"{'='*60}\n")

    return {"scores": scores, "overall": overall, "pass": overall > 0.5}


# ---- helpers ----

def _build_store_from_sim(args) -> TileStore:
    """Run simulations to populate a TileStore for tiles/bathymetry commands."""
    seed = getattr(args, 'seed', 42) or 42
    vessel = getattr(args, 'vessel', 'F/V Horizon')
    store = TileStore()

    ap = AutopilotSimulator(count=30, seed=seed, vessel=vessel)
    for cmd in ap.generate_commands(30):
        cmd["tile"].trip_id = "CLI"
        store.add(cmd["tile"])

    fs = FishSortSimulator(count=50, seed=seed + 1, vessel=vessel)
    for e in fs.generate_events(50):
        e["tile"].trip_id = "CLI"
        store.add(e["tile"])

    ch = ChartSimulator(count=15, seed=seed + 2, vessel=vessel)
    for q in ch.generate_queries(15):
        q["tile"].trip_id = "CLI"
        store.add(q["tile"])

    return store


# ---- main ----

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luciddreamer",
        description="LucidDreamer — maritime intelligence tile system",
    )
    sub = parser.add_subparsers(dest="command")

    # simulate
    sim = sub.add_parser("simulate", help="Run simulators")
    sim_sub = sim.add_subparsers(dest="sim_command")

    # simulate autopilot
    ap = sim_sub.add_parser("autopilot", help="Simulate autopilot commands")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--difficulty", type=float, default=0.3)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--vessel", type=str, default="F/V Horizon")

    # simulate fish
    fi = sim_sub.add_parser("fish", help="Simulate fish sorting")
    fi.add_argument("--count", type=int, default=100)
    fi.add_argument("--error-rate", type=float, default=0.05)
    fi.add_argument("--seed", type=int, default=None)
    fi.add_argument("--vessel", type=str, default="F/V Horizon")

    # simulate chart
    cs = sim_sub.add_parser("chart", help="Simulate chart queries")
    cs.add_argument("--count", type=int, default=20)
    cs.add_argument("--seed", type=int, default=None)
    cs.add_argument("--vessel", type=str, default="F/V Horizon")

    # simulate trip
    tr = sim_sub.add_parser("trip", help="Full trip simulation")
    tr.add_argument("--seed", type=int, default=None)
    tr.add_argument("--vessel", type=str, default="F/V Horizon")

    # tiles
    tiles = sub.add_parser("tiles", help="Tile management")
    tiles_sub = tiles.add_subparsers(dest="tiles_command")
    tl = tiles_sub.add_parser("list", help="List tiles")
    tl.add_argument("--type", type=str, default=None, help="Tile type filter")
    tl.add_argument("--seed", type=int, default=42)
    tl.add_argument("--vessel", type=str, default="F/V Horizon")
    tc = tiles_sub.add_parser("compile", help="Compile tiles")
    tc.add_argument("--seed", type=int, default=42)
    tc.add_argument("--vessel", type=str, default="F/V Horizon")

    # bathymetry
    bt = sub.add_parser("bathymetry", help="Render bathymetric coverage map")
    bt.add_argument("--seed", type=int, default=42)
    bt.add_argument("--vessel", type=str, default="F/V Horizon")

    # beta-test
    beta = sub.add_parser("beta-test", help="Run all simulators and check scores")
    beta.add_argument("--seed", type=int, default=42)

    return parser


def main(argv: Optional[list[str]] = None):
    parser = build_parser()
    args = parser.parse_args(argv)

    dispatch = {
        ("simulate", "autopilot"): cmd_simulate_autopilot,
        ("simulate", "fish"): cmd_simulate_fish,
        ("simulate", "chart"): cmd_simulate_chart,
        ("simulate", "trip"): cmd_simulate_trip,
        ("tiles", "list"): cmd_tiles_list,
        ("tiles", "compile"): cmd_tiles_compile,
        ("bathymetry", None): cmd_bathymetry,
        ("beta-test", None): cmd_beta_test,
    }

    key = (args.command, getattr(args, "sim_command", None) or getattr(args, "tiles_command", None))
    fn = dispatch.get(key)
    if fn is None:
        parser.print_help()
        sys.exit(1)

    return fn(args)


if __name__ == "__main__":
    main()
