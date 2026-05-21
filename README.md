# LucidDreamer — Maritime Intelligence System

[![PyPI version](https://img.shields.io/pypi/v/luciddreamer.svg)](https://pypi.org/project/luciddreamer/) [![Python](https://img.shields.io/pypi/pyversions/luciddreamer.svg)](https://pypi.org/project/luciddreamer/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen.svg)](./tests)

*A thinking boat that learns its captain, tiles its knowledge, and compiles its intelligence.*

## What This Is

LucidDreamer is a modular AI system that starts with cloud intelligence and distills it down to edge-ready compiled code. It learns your voice, your commands, your fish, your waters. Every interaction creates a tile. Every tile makes the system smarter. Over time, the system compiles what it knows into deterministic code that needs no inference — zero tokens, zero latency, zero cloud.

## The Big Idea

Most AI systems stay soft forever — they always need inference, always cost tokens, always depend on the cloud. LucidDreamer is different. It treats the soft model as a **teacher**, not a **worker**. The cloud API's job is to explore the space of possible commands, responses, and decisions. Then it **compiles** what it learns into hard code. The edge device just runs the compiled code.

Think of it like learning to drive. At first, every action requires conscious thought (inference). Over time, the actions become automatic (compiled). You don't "infer" how to turn the steering wheel — you just do it. LucidDreamer does the same thing for boat operations.

## What Can It Do?

### Autopilot Voice Control
Tell the autopilot what to do in natural language. The system learns your dialect, your command style, and your preferred responses. Starts with cloud API, ends up compiled on a Raspberry Pi.

### Fish Sorting Vision
Camera watches the deck, classifies every fish, counts per species per hold. When uncertain, alerts the deck crew. Every fish gets a photo and an identity. Captain reviews low-confidence calls during transit. Buyer's count is the final anchor.

### Chart Intelligence
Reads the navigation display (via screen capture or NMEA data), understands depth contours, predictor lines, radar overlays. The captain can ask "are we going to remain deep enough for the next 10 minutes?" and the system extrapolates from speed, heading, and bathymetric data.

### Cocapn Standalone Chatbot
A chatbot that lives on the boat. Learns from every interaction. Tiles its knowledge. Can output mouse movements to the navigation computer (deliberate, visual, captain can stop if wrong). Understands the 5-minute predictor line, radar overlay, color-coded contours, and whatever else the captain teaches it.

## Architecture

```
CLOUD (Starlink)          EDGE (Boat)              HUMAN (Captain)
┌──────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ Heavy Model  │    │ Compiled Tiles   │    │ Voice + Review   │
│ (GPT-4 etc)  │───▶│ (regex+lookup)   │◀──▶│                  │
│              │    │ Gemma 1B fallback│    │ Ground Truth     │
│ Distills to  │    │ Audio tiles      │    │ Oracle           │
│ tiles        │    │ Vision classifier│    │                  │
└──────────────┘    │ Chart reader     │    └──────────────────┘
                    │ Cocapn chatbot   │
                    └──────────────────┘
```

## Installation

```bash
pip install luciddreamer
```

## Quick Start

See [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) for the full walkthrough.

## Documentation

- [Getting Started Guide](docs/GETTING-STARTED.md) — From zero to thinking boat
- [Architecture](docs/ARCHITECTURE.md) — How the pieces fit together
- [Tile System](docs/TILES.md) — How knowledge is stored and retrieved
- [Compilation](docs/COMPILATION.md) — How soft inference becomes hard code
- [Simulators](docs/SIMULATORS.md) — Test everything before going to sea
- [Cocapn Integration](docs/COCAPN.md) — The standalone chatbot
- [Chart Intelligence](docs/CHARTS.md) — Reading navigation displays
- [Maritime Examples](docs/MARITIME-EXAMPLES.md) — Real-world scenarios

## Modules

| Module | Description |
|--------|-------------|
| `luciddreamer.tiles` | Tile types, storage, and retrieval |
| `luciddreamer.compiler` | Rigid structure finder and compiler |
| `luciddreamer.bathymetry` | Confidence mapping and coverage tracking |
| `luciddreamer.router` | Route to compiled tiles vs fallback inference |
| `luciddreamer.audio` | Audio tile management (pre-generated responses) |
| `luciddreamer.chart` | Chart interpretation and depth prediction |
| `luciddreamer.vision` | Fish sorting vision pipeline |
| `luciddreamer.cocapn` | Standalone chatbot integration |
| `luciddreamer.simulators` | Test simulators for all subsystems |

## Ecosystem Integration

LucidDreamer integrates with the SuperInstance ecosystem:

- **eisenstein-embed** — Bitvector matching for fast tile lookup
- **tensor-spline** — Compress tile data for edge storage
- **device-router** — Route inference to right device
- **training-throttle** — Manage cloud API usage
- **plato-core** — Tile provenance and lifecycle
- **flux-lucid** — Dream reconstruction and constraint compilation

## License

MIT

## Related

- [AIR](https://github.com/SuperInstance/AIR) — Asynchronous Infinite Radio, nightly synthesis
- [flux-lucid](https://github.com/SuperInstance/flux-lucid) — Constraint compilation backbone
- [cocapn-oneiros](https://github.com/SuperInstance/cocapn-oneiros) — Latent room generation
- [luciddreamer-agent](https://github.com/SuperInstance/luciddreamer-agent) — Dream journal agent
- [luciddreamer-os](https://github.com/SuperInstance/luciddreamer-os) — Web UI dashboard
