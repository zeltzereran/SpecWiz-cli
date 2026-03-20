"""Tests for Gemini LLM adapter."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specwiz.core.interfaces.adapters import LLMResponse


def _make_mock_client():
    """Build a mock genai.Client with aio.models wired up."""
    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_models = MagicMock()
    mock_client.aio = mock_aio
    mock_aio.models = mock_models
    return mock_client, mock_models


@pytest.fixture(autouse=True)
def patch_genai_client(monkeypatch):
    """Prevent real Gemini HTTP calls in every test."""
    mock_client, mock_models = _make_mock_client()
    with patch("specwiz.adapters.llm_gemini.genai.Client", return_value=mock_client):
        yield mock_client, mock_models


@pytest.mark.asyncio
async def test_gemini_adapter_initialization():
    """GeminiAdapter initialises with GOOGLE_API_KEY set."""
    os.environ["GOOGLE_API_KEY"] = "test-key"
    try:
        from specwiz.adapters.llm_gemini import GeminiAdapter

        adapter = GeminiAdapter(model="gemini-2.0-flash")
        assert adapter.model == "gemini-2.0-flash"
    finally:
        os.environ.pop("GOOGLE_API_KEY", None)


@pytest.mark.asyncio
async def test_gemini_adapter_no_api_key():
    """GeminiAdapter raises ValueError when GOOGLE_API_KEY is missing."""
    os.environ.pop("GOOGLE_API_KEY", None)
    from specwiz.adapters.llm_gemini import GeminiAdapter

    with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
        GeminiAdapter()


@pytest.mark.asyncio
async def test_gemini_adapter_complete(patch_genai_client):
    """complete() returns an LLMResponse with correct fields."""
    _, mock_models = patch_genai_client
    os.environ["GOOGLE_API_KEY"] = "test-key"
    try:
        from specwiz.adapters.llm_gemini import GeminiAdapter

        mock_response = MagicMock()
        mock_response.text = "Hello from Gemini"
        mock_response.usage_metadata.prompt_token_count = 20
        mock_response.usage_metadata.candidates_token_count = 10
        mock_models.generate_content = AsyncMock(return_value=mock_response)

        adapter = GeminiAdapter(model="gemini-2.0-flash")
        response = await adapter.complete(prompt="Say hello", temperature=0.5, max_tokens=512)

        assert isinstance(response, LLMResponse)
        assert response.content == "Hello from Gemini"
        assert response.model == "gemini-2.0-flash"
        assert response.usage["input_tokens"] == 20
        assert response.usage["output_tokens"] == 10
        assert response.stop_reason is None
    finally:
        os.environ.pop("GOOGLE_API_KEY", None)


@pytest.mark.asyncio
async def test_gemini_adapter_complete_with_system(patch_genai_client):
    """complete() passes system prompt via GenerateContentConfig."""
    _, mock_models = patch_genai_client
    os.environ["GOOGLE_API_KEY"] = "test-key"
    try:
        from specwiz.adapters.llm_gemini import GeminiAdapter

        mock_response = MagicMock()
        mock_response.text = "response"
        mock_response.usage_metadata.prompt_token_count = 5
        mock_response.usage_metadata.candidates_token_count = 3
        mock_models.generate_content = AsyncMock(return_value=mock_response)

        adapter = GeminiAdapter()
        await adapter.complete(prompt="user msg", system="system instruction")

        call_kwargs = mock_models.generate_content.call_args[1]
        config = call_kwargs.get("config")
        assert config is not None
        assert config.system_instruction == "system instruction"
        assert call_kwargs.get("contents") == "user msg"
    finally:
        os.environ.pop("GOOGLE_API_KEY", None)


@pytest.mark.asyncio
async def test_gemini_adapter_stream_complete(patch_genai_client):
    """stream_complete() yields text chunks from the stream."""
    _, mock_models = patch_genai_client
    os.environ["GOOGLE_API_KEY"] = "test-key"
    try:
        from specwiz.adapters.llm_gemini import GeminiAdapter

        chunk1 = MagicMock()
        chunk1.text = "Hello "
        chunk2 = MagicMock()
        chunk2.text = "world"

        async def _fake_stream(*args, **kwargs):
            for chunk in [chunk1, chunk2]:
                yield chunk

        mock_models.generate_content_stream = _fake_stream

        adapter = GeminiAdapter(model="gemini-1.5-pro")
        chunks = []
        async for text in adapter.stream_complete(prompt="Say hello"):
            chunks.append(text)

        assert chunks == ["Hello ", "world"]
    finally:
        os.environ.pop("GOOGLE_API_KEY", None)


def test_resolve_provider_gemini():
    """_resolve_provider returns 'gemini' for gemini-* model names."""
    from specwiz.cli._engine import _resolve_provider

    assert _resolve_provider("gemini-1.5-pro") == "gemini"
    assert _resolve_provider("gemini-2.0-flash") == "gemini"


def test_resolve_provider_anthropic():
    """_resolve_provider returns 'anthropic' for claude-* model names."""
    from specwiz.cli._engine import _resolve_provider

    assert _resolve_provider("claude-3-5-sonnet-20241022") == "anthropic"
    assert _resolve_provider("claude-3-opus-20240229") == "anthropic"
