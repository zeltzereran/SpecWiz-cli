"""SpecWiz CLI application."""

import sys
from pathlib import Path

import typer
from rich.console import Console

from specwiz.cli.commands.create import create_app
from specwiz.cli.commands.generate import generate_app
from specwiz.cli.commands.rulebook import rulebook_app

# Create CLI app
app = typer.Typer(
    name="specwiz",
    help="Documentation generation platform with versioned rulebooks",
    no_args_is_help=True,
)

# Create console for output
console = Console()

# Add command groups
app.add_typer(
    create_app, name="create", help="Create knowledge base, product context, and rulebooks"
)
app.add_typer(
    generate_app, name="generate", help="Generate documents (PRD, user guide, release notes)"
)
app.add_typer(rulebook_app, name="rulebook", help="Manage documentation rulebooks")


@app.command()
def init(
    product: str = typer.Option(
        None, "--product", help="Product name (optional; if omitted, only global config is set)"
    ),
    base_path: str = typer.Option(
        ".specwiz", "--base-path", help="Base directory for product storage"
    ),
    model: str = typer.Option(
        "qwen2.5:7b",
        "--model",
        help=(
            "LLM model: Gemini (gemini-*) needs GOOGLE_API_KEY, "
            "Anthropic (claude-*) needs ANTHROPIC_API_KEY, "
            "Ollama (model:tag) needs local Ollama server"
        ),
    ),
) -> None:
    """Initialize SpecWiz: set global LLM config and optionally create a product.

    - Without --product: sets global model/provider in specwiz.yaml
    - With --product: creates per-product directories
    """
    import os

    from rich.panel import Panel

    from specwiz.cli._engine import _resolve_provider

    # Validate that the required API key for the chosen model is present
    provider = _resolve_provider(model)
    if provider == "gemini" and not os.getenv("GOOGLE_API_KEY"):
        console.print(f"[red]Error: model '{model}' requires GOOGLE_API_KEY to be set.[/red]")
        sys.exit(1)
    if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        console.print(f"[red]Error: model '{model}' requires ANTHROPIC_API_KEY to be set.[/red]")
        sys.exit(1)

    try:
        cwd = Path.cwd()
        config_file = cwd / "specwiz.yaml"

        # Always write global config (create or update)
        is_update = config_file.exists()
        config_file.write_text(
            f"# SpecWiz Configuration\n"
            f"base_path: {base_path}\n"
            f"llm_provider: {provider}\n"
            f"llm_model: {model}\n",
            encoding="utf-8",
        )
        config_msg = (
            "[green]✓ Global config updated[/green]\n"
            if is_update
            else "[green]✓ Global config created[/green]\n"
        )

        # If no product specified, just set global config
        if not product:
            console.print(
                Panel(
                    config_msg
                    + f"Model:   [bold]{model}[/bold] ({provider})\n"
                    + f"Config:  {config_file.relative_to(cwd)}\n\n"
                    + "[dim]Next steps:[/dim]\n"
                    + "  [cyan]specwiz init --product <name>[/cyan] to create a product",
                    title="SpecWiz Init",
                    expand=False,
                )
            )
            return

        # Create per-product directories
        product_path = cwd / base_path / product

        if product_path.exists():
            console.print(
                f"[red]Error: Product '[bold]{product}[/bold]' already exists at "
                f"{product_path.relative_to(cwd)}.[/red]"
            )
            sys.exit(1)

        # Create only product-specific directories
        # (knowledge-base/ and rulebooks/ are global and auto-created on first use)
        dirs = [
            product_path / "product-context",
            product_path / "generated" / "prd",
            product_path / "generated" / "user-guide",
            product_path / "generated" / "release-notes",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        console.print(
            Panel(
                config_msg
                + "[green]✓ Product initialized![/green]\n"
                + f"Product: [bold]{product}[/bold]\n"
                + f"Model:   [bold]{model}[/bold] ({provider})\n"
                + f"Directory: {product_path.relative_to(cwd)}\n\n"
                + "[dim]Next steps:[/dim]\n"
                + "  1. [cyan]specwiz create knowledge-base --sources ./docs[/cyan]\n"
                + f"  2. [cyan]specwiz create product-context --product {product} --git .[/cyan]\n"
                + "  3. [cyan]specwiz create rulebook prd --resources ./examples[/cyan]",
                title="SpecWiz Init",
                expand=False,
            )
        )

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@app.command()
def doctor() -> None:
    """Check SpecWiz setup: API keys, adapters, and product readiness."""
    from rich.table import Table

    from specwiz.adapters import BlinkerEventBusAdapter, LocalStorageAdapter
    from specwiz.cli._paths import get_base_path

    table = Table(title="SpecWiz System Health")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Details", style="green")

    cwd = Path.cwd()

    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    table.add_row("Python", "✓", f"v{py_version}")

    _add_llm_health_rows(table, cwd)

    # Adapters
    try:
        LocalStorageAdapter()
        table.add_row("Storage Adapter", "✓", "OK")
    except Exception as e:
        table.add_row("Storage Adapter", "✗", str(e))

    try:
        BlinkerEventBusAdapter()
        table.add_row("Event Bus", "✓", "OK")
    except Exception as e:
        table.add_row("Event Bus", "✗", str(e))

    base = get_base_path(cwd)

    # Global: knowledge base
    kb_file = base / "knowledge-base" / "knowledge-base.md"
    if kb_file.exists():
        table.add_row("Knowledge Base", "✓", str(kb_file.relative_to(cwd)))
    else:
        table.add_row(
            "Knowledge Base", "⚠", "Not found — run: specwiz create knowledge-base --sources <path>"
        )

    # Global: rulebooks
    rulebooks_dir = base / "rulebooks"
    _RULEBOOK_TYPES = ["prd", "user-guide", "release-note", "diagram"]
    if rulebooks_dir.exists():
        created = [t for t in _RULEBOOK_TYPES if (rulebooks_dir / f"{t}-rulebook.md").exists()]
        missing = [t for t in _RULEBOOK_TYPES if t not in created]
        rb_detail = f"created: {', '.join(created) or 'none'}" + (
            f"  missing: {', '.join(missing)}" if missing else ""
        )
        table.add_row("Rulebooks", "✓" if created else "⚠", rb_detail)
    else:
        table.add_row(
            "Rulebooks", "⚠", "No rulebooks — run: specwiz create rulebook prd --resources <path>"
        )

    # Products
    _add_product_rows(table, base, cwd)

    console.print(table)


def _add_llm_health_rows(table, cwd: Path) -> None:
    """Add model/provider/API key health rows to the doctor table."""

    from specwiz.cli._engine import _resolve_provider
    from specwiz.core.managers.config import CompositeConfigAdapter

    cfg = CompositeConfigAdapter(project_root=cwd)
    model = str(cfg.get("llm_model") or "qwen2.5:7b")
    provider_from_model = _resolve_provider(model)
    configured_provider = cfg.get("llm_provider")
    provider = str(configured_provider or provider_from_model)

    if provider not in ("gemini", "anthropic", "ollama"):
        table.add_row("LLM Config", "✗", f"Unsupported provider '{provider}' (model: {model})")
        return

    if configured_provider and configured_provider != provider_from_model:
        table.add_row(
            "LLM Config",
            "⚠",
            (
                f"provider={provider}, model={model} "
                f"(model naming suggests provider={provider_from_model})"
            ),
        )
    else:
        table.add_row("LLM Config", "✓", f"provider={provider}, model={model}")

    if provider == "gemini":
        _add_gemini_key_check(table)
    elif provider == "anthropic":
        _add_anthropic_key_check(table)
    elif provider == "ollama":
        _add_ollama_health_check(table, model)


def _add_gemini_key_check(table) -> None:
    """Check and add GOOGLE_API_KEY status row."""
    import os

    if os.getenv("GOOGLE_API_KEY"):
        table.add_row("Provider API Key", "✓", "GOOGLE_API_KEY is set")
    else:
        table.add_row(
            "Provider API Key", "⚠", "GOOGLE_API_KEY not set - Gemini LLM calls will fail"
        )


def _add_anthropic_key_check(table) -> None:
    """Check and add ANTHROPIC_API_KEY status row."""
    import os

    if os.getenv("ANTHROPIC_API_KEY"):
        table.add_row("Provider API Key", "✓", "ANTHROPIC_API_KEY is set")
    else:
        table.add_row(
            "Provider API Key",
            "⚠",
            "ANTHROPIC_API_KEY not set - Anthropic LLM calls will fail",
        )


def _add_ollama_health_check(table, model: str) -> None:
    """Check and add Ollama server status row."""
    import httpx

    try:
        response = httpx.get(
            "http://localhost:11434/api/tags",
            timeout=2.0,
        )
        if response.status_code == 200:
            table.add_row("Ollama Server", "✓", "Running at http://localhost:11434")
            # Check if the configured model is available
            data = response.json()
            available_models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
            configured_base_model = model.split(":")[0]
            if configured_base_model in available_models or model in [
                m.get("name", "") for m in data.get("models", [])
            ]:
                table.add_row("Ollama Model", "✓", f"Model '{model}' is available")
            else:
                table.add_row(
                    "Ollama Model",
                    "⚠",
                    f"Model '{model}' not found. Available: {', '.join(available_models[:5])}",
                )
        else:
            table.add_row("Ollama Server", "⚠", f"HTTP {response.status_code}")
    except (httpx.ConnectError, httpx.TimeoutException):
        table.add_row(
            "Ollama Server",
            "⚠",
            "Not reachable - run: ollama serve",
        )


def _add_product_rows(table, base: Path, cwd: Path) -> None:
    """Add per-product health rows to the doctor table."""
    from specwiz.cli._paths import DEFAULT_BASE

    if not base.exists():
        table.add_row(
            "Products", "⚠", f"No {DEFAULT_BASE}/ directory — run: specwiz init --product <name>"
        )
        return

    products = sorted(
        d for d in base.iterdir() if d.is_dir() and d.name not in ("knowledge-base", "rulebooks")
    )
    try:
        base_rel = base.relative_to(cwd)
    except ValueError:
        base_rel = base

    if not products:
        table.add_row("Products", "⚠", f"No products found in {base_rel}")
        return

    table.add_row("Products", "✓", f"{len(products)} found in {base_rel}")
    for p in products:
        ctx = (
            any((p / "product-context").glob("*.md")) if (p / "product-context").exists() else False
        )
        status = "✓" if ctx else "⚠"
        ctx_hint = (
            "✓" if ctx else f"✗ (run: specwiz create product-context --product {p.name} --git .)"
        )
        detail = f"product-context: {ctx_hint}"
        table.add_row(f"  └ {p.name}", status, detail)


@app.callback(invoke_without_command=True)
def version_callback(
    version: bool = typer.Option(
        None,
        "--version",
        help="Show version information",
    ),
) -> None:
    """Display version information."""
    if version:
        from specwiz import __version__

        console.print(f"SpecWiz v{__version__}")
        raise typer.Exit(code=0)


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()
