# Contributing to LucidDreamer

## Development Setup

```bash
git clone https://github.com/SuperInstance/luciddreamer.git
cd luciddreamer
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -v
```

## Code Style

- Python 3.10+
- Type hints on all public APIs
- Docstrings on all classes and methods
- `py.typed` marker for PEP 561

## Adding a New Simulator

1. Add your simulator class to `luciddreamer/simulators.py`
2. Add CLI integration in `luciddreamer/cli.py`
3. Add tests in `tests/test_simulators.py`
4. Update docs in `docs/SIMULATORS.md`

## Adding a New Tile Type

1. Add the type to `TileType` enum in `tiles.py`
2. Create a typed dataclass (e.g., `FishTile`, `ChartTile`)
3. Add compilation support in `compiler.py` if applicable
4. Add routing support in `router.py`
5. Add simulator support
6. Update docs

## Maritime Domain Notes

- Depths are in **fathoms** (1 fathom = 6 feet = 1.8288 meters)
- Headings are in **degrees true** (0° = north, 90° = east)
- Speed is in **knots** (nautical miles per hour)
- Species names follow **Pacific salmon** naming: Chinook, Sockeye, Pink, Chum, Coho
- "Port" = left, "Starboard" = right (facing forward)
- "Dragging" = towing fishing gear behind the boat

## License

MIT — see LICENSE file.
