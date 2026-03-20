"""Shared engine initialization helper for SpecWiz CLI commands."""

import sys
from pathlib import Path
from typing import Any, Dict

from rich.console import Console

from specwiz.adapters import (
    AnthropicAdapter,
    BlinkerEventBusAdapter,
    GeminiAdapter,
    LocalStorageAdapter,
    OllamaAdapter,
)
from specwiz.core import SpecWizPipelineEngine
from specwiz.core.interfaces.engine import ExecutionContext

# Models that belong to each provider
_GEMINI_MODELS = frozenset(
    [
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.0-pro",
        "gemini-2.5-pro",
    ]
)

_OLLAMA_MODELS = frozenset(
    [
        "qwen2.5:7b",
        "qwen2.5:14b",
        "qwen2.5:32b",
        "llama2:7b",
        "mistral:7b",
        "neural-chat:7b",
    ]
)


def _resolve_provider(model: str) -> str:
    """Return 'gemini', 'anthropic', or 'ollama' based on the model name."""
    if model.startswith("gemini") or model in _GEMINI_MODELS:
        return "gemini"
    if ":" in model or model in _OLLAMA_MODELS:
        # Ollama models typically use format "model:tag" (e.g., qwen2.5:7b)
        return "ollama"
    return "anthropic"


def _build_llm_adapter(console: Console):
    """Read model from specwiz.yaml (via config manager) and return the right adapter."""
    from specwiz.core.managers.config import CompositeConfigAdapter

    cfg = CompositeConfigAdapter()
    model = cfg.get("llm_model") or "qwen2.5:7b"
    provider = cfg.get("llm_provider") or _resolve_provider(model)

    # Allow provider override from config, but still auto-detect from model name
    if provider == "gemini" or model.startswith("gemini"):
        try:
            return GeminiAdapter(model=model)
        except ValueError as e:
            console.print(f"[red]LLM initialization error: {e}[/red]")
            sys.exit(1)
    elif provider == "ollama" or ":" in model:
        try:
            return OllamaAdapter(model=model)
        except RuntimeError as e:
            console.print(f"[red]LLM initialization error: {e}[/red]")
            sys.exit(1)
    else:
        try:
            return AnthropicAdapter(model=model)
        except ValueError as e:
            console.print(f"[red]LLM initialization error: {e}[/red]")
            sys.exit(1)


async def run_stage(
    stage_name: str,
    product_path: Path,
    inputs: Dict[str, Any],
    console: Console,
) -> str:
    """Initialize the engine, execute a single named stage, and return the LLM output."""
    storage = LocalStorageAdapter(base_path=product_path / "artifacts")
    event_bus = BlinkerEventBusAdapter()
    llm = _build_llm_adapter(console)

    engine = SpecWizPipelineEngine(storage=storage, llm=llm, event_bus=event_bus)
    await engine.initialize()

    context = ExecutionContext(
        project_root=str(product_path),
        project_name=product_path.name,
        stage_name=stage_name,
        stage_number=0,
        inputs=inputs,
    )

    result = await engine.execute_stage(stage_name, context)
    return result.content
