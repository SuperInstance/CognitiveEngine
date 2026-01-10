"""
Provider Abstraction Layer
A unified interface for multiple AI API providers
"""

from .models import (
    ProviderType,
    ChatMessage,
    GenerationRequest,
    GenerationResponse,
    ProviderConfig
)
from .base import BaseProvider

__version__ = "1.0.0"
__all__ = [
    "ProviderType",
    "ChatMessage",
    "GenerationRequest",
    "GenerationResponse",
    "ProviderConfig",
    "BaseProvider"
]
