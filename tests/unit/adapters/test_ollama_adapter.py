"""Tests for Ollama LLM adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from specwiz.adapters.llm_ollama import OllamaAdapter
from specwiz.cli._engine import _resolve_provider


class TestOllamaAdapter:
    """Tests for OllamaAdapter."""

    @pytest.mark.asyncio
    async def test_ollama_init(self):
        """Test OllamaAdapter initialization."""
        with patch("httpx.AsyncClient"):
            adapter = OllamaAdapter(model="qwen2.5:7b")
            assert adapter.model == "qwen2.5:7b"
            assert adapter.base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_ollama_init_custom_url(self):
        """Test OllamaAdapter initialization with custom base URL."""
        with patch("httpx.AsyncClient"):
            adapter = OllamaAdapter(
                model="mistral:7b",
                base_url="http://127.0.0.1:11435/",
            )
            assert adapter.model == "mistral:7b"
            assert adapter.base_url == "http://127.0.0.1:11435"

    @pytest.mark.asyncio
    async def test_ollama_complete(self):
        """Test OllamaAdapter.complete() method."""
        adapter = OllamaAdapter(model="qwen2.5:7b")

        # Mock the HTTP client response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Test response"},
            "prompt_eval_count": 10,
            "eval_count": 20,
        }

        adapter._client.post = AsyncMock(return_value=mock_response)

        response = await adapter.complete(
            prompt="What is AI?",
            system="You are a helpful assistant.",
            temperature=0.7,
            max_tokens=100,
        )

        assert response.content == "Test response"
        assert response.model == "qwen2.5:7b"
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20
        assert response.stop_reason is None

        # Verify the API was called correctly
        adapter._client.post.assert_called_once()
        call_kwargs = adapter._client.post.call_args[1]
        assert call_kwargs["json"]["model"] == "qwen2.5:7b"
        assert call_kwargs["json"]["messages"][0]["role"] == "system"
        assert call_kwargs["json"]["messages"][1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_ollama_complete_without_system_prompt(self):
        """Test OllamaAdapter.complete() without system prompt."""
        adapter = OllamaAdapter(model="qwen2.5:7b")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {"content": "Response without system prompt"},
            "prompt_eval_count": 5,
            "eval_count": 15,
        }

        adapter._client.post = AsyncMock(return_value=mock_response)

        response = await adapter.complete(prompt="Hello?")

        assert response.content == "Response without system prompt"
        call_kwargs = adapter._client.post.call_args[1]
        # Should only have user message, not system
        assert len(call_kwargs["json"]["messages"]) == 1
        assert call_kwargs["json"]["messages"][0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_ollama_complete_connection_error(self):
        """Test OllamaAdapter.complete() with connection error."""
        adapter = OllamaAdapter(model="qwen2.5:7b")
        adapter._client.post = AsyncMock(side_effect=httpx.ConnectError("Connection failed"))

        with pytest.raises(RuntimeError, match="Cannot connect to Ollama server"):
            await adapter.complete(prompt="Test")

    @pytest.mark.asyncio
    async def test_ollama_complete_api_error(self):
        """Test OllamaAdapter.complete() with API error."""
        adapter = OllamaAdapter(model="qwen2.5:7b")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"

        adapter._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(RuntimeError, match="Ollama API error"):
            await adapter.complete(prompt="Test")

    @pytest.mark.asyncio
    async def test_ollama_stream_complete(self):
        """Test OllamaAdapter.stream_complete() method."""
        adapter = OllamaAdapter(model="qwen2.5:7b")

        # Mock streaming response
        mock_lines = [
            '{"message":{"content":"Hello "}}',
            '{"message":{"content":"world"}}',
            '{"message":{"content":"!"}}',
        ]

        async def mock_aiter_lines():
            for line in mock_lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        adapter._client.stream = MagicMock(return_value=mock_stream_context)

        chunks = []
        async for chunk in adapter.stream_complete(
            prompt="Say hello",
            temperature=0.5,
        ):
            chunks.append(chunk)

        assert chunks == ["Hello ", "world", "!"]

    @pytest.mark.asyncio
    async def test_ollama_stream_complete_connection_error(self):
        """Test OllamaAdapter.stream_complete() with connection error."""
        adapter = OllamaAdapter(model="qwen2.5:7b")

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("Failed"))
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        adapter._client.stream = MagicMock(return_value=mock_stream_context)

        with pytest.raises(RuntimeError, match="Cannot connect to Ollama server"):
            async for _ in adapter.stream_complete(prompt="Test"):
                pass

    @pytest.mark.asyncio
    async def test_ollama_stream_complete_malformed_json(self):
        """Test OllamaAdapter.stream_complete() with malformed JSON lines."""
        adapter = OllamaAdapter(model="qwen2.5:7b")

        async def mock_aiter_lines():
            yield '{"message":{"content":"Valid "}}'
            yield "malformed json"
            yield '{"message":{"content":"content"}}'
            yield ""

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        mock_stream_context = MagicMock()
        mock_stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_context.__aexit__ = AsyncMock(return_value=None)

        adapter._client.stream = MagicMock(return_value=mock_stream_context)

        chunks = []
        async for chunk in adapter.stream_complete(prompt="Test"):
            chunks.append(chunk)

        # Should skip malformed lines and empty lines
        assert chunks == ["Valid ", "content"]

    def test_resolve_provider_ollama(self):
        """Test _resolve_provider for Ollama models."""
        assert _resolve_provider("qwen2.5:7b") == "ollama"
        assert _resolve_provider("llama2:7b") == "ollama"
        assert _resolve_provider("mistral:7b") == "ollama"
        assert _resolve_provider("neural-chat:7b") == "ollama"
        assert _resolve_provider("qwen2.5:14b") == "ollama"

    def test_resolve_provider_gemini(self):
        """Test _resolve_provider for Gemini models."""
        assert _resolve_provider("gemini-2.0-flash") == "gemini"
        assert _resolve_provider("gemini-1.5-pro") == "gemini"
        assert _resolve_provider("gemini-1.5-flash") == "gemini"

    def test_resolve_provider_anthropic(self):
        """Test _resolve_provider for Anthropic models."""
        assert _resolve_provider("claude-3-opus-20240229") == "anthropic"
        assert _resolve_provider("claude-3-5-sonnet-20241022") == "anthropic"
