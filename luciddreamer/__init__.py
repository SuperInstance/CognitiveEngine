"""
luciddreamer — Maritime intelligence system.

Distills cloud AI into compiled edge tiles. Every interaction creates a tile.
Every tile makes the system smarter. Over time, soft inference compiles to hard code.

Zero-shot by design. Zero context assumed. The tiles and weights ARE the memory.
"""

__version__ = "0.1.0"
__all__ = [
    # Tile types
    "Tile",
    "TileType",
    "Confidence",
    "Verifier",
    "CommandTile",
    "VisionTile",
    "ChartTile",
    "TileStore",
    # Compilation
    "RigidFinder",
    "CompiledCommand",
    # Bathymetry
    "BathymetricMap",
    "DepthSounding",
    # Routing
    "Router",
    "RouteDecision",
    # Training
    "TrainingDataGenerator",
    "LoRACheckpoint",
    "CheckpointManager",
    "CheckpointDiff",
    "TrainingExample",
    # Nav/Cocapn
    "NavComputer",
    "NavButton",
    "MouseAction",
    "ClickType",
    "ChartData",
    "ChartInterpreter",
    "CocapnChatbot",
    # Simulators
    "AutopilotSimulator",
    "FishSortSimulator",
    "ChartSimulator",
    "CaptainReviewSimulator",
    "FullTripSimulator",
    # Signal Chain
    "DialMixin",
    "SignalChainRoom",
    "EpsilonAccumulator",
    "RoomChain",
]

from .tiles import Tile, TileType, Confidence, Verifier, TileStore, CommandTile, VisionTile, ChartTile
from .compiler import RigidFinder, CompiledCommand
from .bathymetry import BathymetricMap, DepthSounding
from .router import Router, RouteDecision
from .training import (
    TrainingDataGenerator,
    LoRACheckpoint,
    CheckpointManager,
    CheckpointDiff,
    TrainingExample,
)
from .chart import ChartData
from .cocapn import NavComputer, NavButton, MouseAction, ClickType, ChartInterpreter, CocapnChatbot
from .simulators import (
    AutopilotSimulator,
    FishSortSimulator,
    ChartSimulator,
    CaptainReviewSimulator,
    FullTripSimulator,
)
from .signal_chain import SignalChainRoom, EpsilonAccumulator, RoomChain
