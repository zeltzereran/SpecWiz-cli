"""Domain managers for SpecWiz.

High-level managers that orchestrate complex domain logic:
- ConfigManager: config loading and validation
- RulebookManager: load, validate, and diff rulebooks
- ContextManager: extract product context from repo/docs
"""

from specwiz.core.managers.config import CompositeConfigAdapter
from specwiz.core.managers.context import ContextManager
from specwiz.core.managers.rulebook import RulebookManager

__all__ = [
    "CompositeConfigAdapter",
    "RulebookManager",
    "ContextManager",
]
