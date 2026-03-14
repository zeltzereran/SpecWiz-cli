"""Adapters for SpecWiz.

Implementations of the adapter interfaces for concrete services:
- StorageAdapter: local file system
- LLMAdapter: Anthropic Claude
- ConfigAdapter: environment variables + config files
- EventBusAdapter: blinker-based event bus
"""

from specwiz.adapters.events import BlinkerEventBusAdapter
from specwiz.adapters.llm import AnthropicAdapter
from specwiz.adapters.storage import LocalStorageAdapter

__all__ = [
    "LocalStorageAdapter",
    "AnthropicAdapter",
    "BlinkerEventBusAdapter",
]
