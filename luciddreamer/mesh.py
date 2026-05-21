"""Mesh integration for the SuperInstance ecosystem.

Registers luciddreamer capabilities with the plato-core MeshRegistry
when both packages are installed together.
"""

__all__ = ["register"]


try:
    from plato_core.mesh import MeshRegistry
    
    def register(registry: MeshRegistry) -> None:
        """Register luciddreamer capabilities with the mesh."""
        registry.register_capability(
            package="luciddreamer",
            version="0.1.0",
            capabilities=[
                "tile_storage",         # Persistent tile storage
                "rigid_compilation",    # Compile tiles to deterministic code
                "bathymetric_mapping",  # Coverage tracking and visualization
                "command_routing",      # Route to compiled vs fallback
                "maritime_simulators",  # Test simulators for all subsystems
                "cocapn_chatbot",       # Standalone boat AI assistant
                "chart_intelligence",   # Navigation display interpretation
            ],
            tile_types=[
                "command", "response", "vision", "chart",
                "correction", "negative", "abstraction",
            ],
            entry_point="luciddreamer.mesh:register",
        )

except ImportError:
    # plato-core not installed — luciddreamer works standalone
    def register(registry=None) -> None:
        """No-op when plato-core is not available."""
        pass
