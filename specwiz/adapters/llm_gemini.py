"""Google Gemini LLM adapter."""

import os
from typing import Any, AsyncIterator, Optional

from google import genai
from google.genai import types

from specwiz.core.interfaces.adapters import LLMAdapter, LLMResponse


class GeminiAdapter(LLMAdapter):
    """LLM adapter for Google Gemini API.

    Supports both sync and async patterns. Credentials loaded from:
    - GOOGLE_API_KEY environment variable
    """

    def __init__(self, model: str = "gemini-2.0-flash"):
        """Initialize Gemini adapter.

        Args:
            model: Gemini model to use (default: gemini-1.5-pro)

        Raises:
            ValueError: If GOOGLE_API_KEY is not set
        """
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable not set. " "Please configure your API key."
            )

        self.model = model
        self._client = genai.Client(api_key=api_key)

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        """Send prompt to Gemini and return response.

        Args:
            prompt: User message/prompt
            system: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Max tokens in response
            **kwargs: Additional arguments passed to API

        Returns:
            LLMResponse with generated content
        """
        contents = prompt
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system,
        )

        response = await self._client.aio.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )

        content = response.text or ""
        input_tokens = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
        output_tokens = (
            response.usage_metadata.candidates_token_count if response.usage_metadata else 0
        )

        return LLMResponse(
            content=content,
            usage={
                "input_tokens": input_tokens or 0,
                "output_tokens": output_tokens or 0,
            },
            model=self.model,
            stop_reason=None,
        )

    async def stream_complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Stream response from Gemini.

        Args:
            prompt: User message/prompt
            system: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Max tokens in response
            **kwargs: Additional arguments passed to API

        Yields:
            Text chunks from response
        """
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            system_instruction=system,
        )

        async for chunk in self._client.aio.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=config,
        ):
            if chunk.text:
                yield chunk.text
