"""Ollama LLM adapter for local models."""

from typing import Any, AsyncIterator, Optional

import httpx

from specwiz.core.interfaces.adapters import LLMAdapter, LLMResponse


class OllamaAdapter(LLMAdapter):
    """LLM adapter for Ollama (local model serving).

    Supports both sync and async patterns. Ollama must be running locally
    at the specified base_url (default: http://localhost:11434).
    """

    def __init__(self, model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"):
        """Initialize Ollama adapter.

        Args:
            model: Ollama model to use (default: qwen2.5:7b)
            base_url: Ollama server URL (default: http://localhost:11434)

        Raises:
            ValueError: If Ollama server is not reachable
        """
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self.base_url)

        # Try to connect to verify Ollama is running
        # We'll do this lazily on first use to avoid blocking initialization

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send prompt to Ollama and return response.

        Args:
            prompt: User message/prompt
            system: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Max tokens in response
            **kwargs: Additional arguments passed to API

        Returns:
            LLMResponse with generated content

        Raises:
            RuntimeError: If Ollama server is not reachable
        """
        try:
            # Build messages list
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            # Call Ollama API
            response = await self._client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=300.0,  # 5 minute timeout for large responses
            )

            if response.status_code != 200:
                raise RuntimeError(f"Ollama API error: {response.status_code} - {response.text}")

            data = response.json()
            content = data.get("message", {}).get("content", "")

            # Extract token counts if available
            input_tokens = data.get("prompt_eval_count", 0)
            output_tokens = data.get("eval_count", 0)

            return LLMResponse(
                content=content,
                usage={
                    "input_tokens": input_tokens or 0,
                    "output_tokens": output_tokens or 0,
                },
                model=self.model,
                stop_reason=None,
            )

        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Cannot connect to Ollama server at {self.base_url}. "
                f"Make sure Ollama is running: ollama serve"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}") from e

    async def stream_complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream response from Ollama.

        Args:
            prompt: User message/prompt
            system: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Max tokens in response

        Yields:
            Text chunks from response

        Raises:
            RuntimeError: If Ollama server is not reachable
        """
        try:
            # Build messages list
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            # Call Ollama API with streaming
            async with self._client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
                timeout=300.0,
            ) as response:
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Ollama API error: {response.status_code} - {response.text}"
                    )

                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json as json_module

                            chunk_data = json_module.loads(line)
                            content = chunk_data.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except Exception:
                            # Skip malformed lines
                            pass

        except httpx.ConnectError as e:
            raise RuntimeError(
                f"Cannot connect to Ollama server at {self.base_url}. "
                f"Make sure Ollama is running: ollama serve"
            ) from e
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}") from e

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
