# SpecWiz CLI

A documentation generation platform that treats organizational documentation standards as first-class, versioned artifacts.

## Vision

Make documentation generation as repeatable and trustworthy as running a test suite. Instead of manually copying prompts into an LLM, teams codify their documentation standards as versioned rulebooks and run SpecWiz CLI to generate PRDs, user guides, and release notes automatically.

## Quick Start

```bash
# Install
pip install -e .

# 0. Set up your LLM provider (choose one)
#
# Option A: Ollama (local, free) - RECOMMENDED FOR LEARNING
#   1. Download Ollama: https://ollama.ai
#   2. Start the server: ollama serve
#   3. Pull a model: ollama pull qwen2.5:7b
#   (no API key needed)
#
# Option B: Google Gemini (free tier available)
#   export GOOGLE_API_KEY="your-gemini-api-key"
#
# Option C: Anthropic Claude (paid)
#   export ANTHROPIC_API_KEY="your-anthropic-api-key"

# 1. Initialize SpecWiz (set LLM model globally)
specwiz init
# Specify a model explicitly:
specwiz init --model qwen2.5:7b           # Ollama (local)
specwiz init --model gemini-2.0-flash     # Google Gemini
specwiz init --model claude-3-5-sonnet-20241022  # Anthropic

# 2. Initialize a product
specwiz init --product MyProduct

# 3. Build the global knowledge base from your docs (once per workspace)
specwiz create knowledge-base --sources ./docs

# 4. Create product context from the git repo
specwiz create product-context --product MyProduct --git .
# or from a remote URL
specwiz create product-context --product MyProduct --git https://github.com/org/repo.git

# 5. Create global rulebooks from your organization's example documents (once per workspace)
specwiz create rulebook prd --resources ./examples/prd
specwiz create rulebook user-guide --resources ./examples/user-guide
specwiz create rulebook release-note --resources ./examples/release-notes

# 6. Generate documents
specwiz generate prd --product MyProduct --feature "New Dashboard"
specwiz generate user-guide --product MyProduct --feature "Dashboard"
specwiz generate release-notes --product MyProduct --release-version v1.2.0 --resources ./changelog.txt

# Inspect what's available
specwiz rulebook list
specwiz doctor
```

## Architecture

SpecWiz follows a **hexagonal architecture**:

```
┌─────────────────────────────────────────────┐
│ CLI Interface (Typer + Rich)                │
│ (thin delivery layer)                       │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│ specwiz-core Library (Pure Python)         │
│ ├─ PipelineEngine (orchestrator)            │
│ ├─ PromptTemplateLayer (Jinja2)             │
│ ├─ RulebookManager (load/validate)          │
│ ├─ ContextManager (extract from repo)       │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┼──────────┐
        │          │          │
    ┌───▼──┐  ┌───▼──┐  ┌───▼────┐
    │Store │  │ LLM  │  │ Events │
    │      │  │Adptr │  │        │
    └──────┘  └──────┘  └────────┘
```

## Project Phases

- **Phase 1**: Core foundation (interfaces, config)
- **Phase 2**: Adapters (storage, LLM, events)
- **Phase 3**: Pipeline engine (orchestration, templating)
- **Phase 4**: CLI commands (Typer interface)
- **Phase 5**: Domain managers (rulebooks, context)
- **Phase 6**: Document generators (PRD, user-guide, release-notes)
- **Phase 7**: Hardening and production readiness

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
ruff check specwiz tests
black --check specwiz tests

# Fix linting
black specwiz tests
ruff check --fix specwiz tests

# Type checking
mypy specwiz
```

## License

Apache 2.0