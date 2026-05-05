"""Abstract and concrete AI provider implementations."""
from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Optional


class AIProvider(ABC):
    """Abstract base for AI API providers."""

    def __init__(self, api_key: Optional[str], model: str) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None

    @abstractmethod
    def _init_client(self) -> None:
        """Initialize SDK client. Subclass must implement."""

    @abstractmethod
    async def query(self, prompt: str) -> str:
        """Send prompt to AI, return response text."""


class AnthropicProvider(AIProvider):
    """Claude API via Anthropic SDK."""

    DEFAULT_MODEL = "claude-sonnet-4-6"
    ENV_KEY = "ANTHROPIC_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv(self.ENV_KEY)
        if not resolved_key:
            raise ValueError(f"{self.ENV_KEY} env var or api_key param required")
        super().__init__(resolved_key, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError(
                    "anthropic package required. Install with: pip install anthropic"
                )
            self._client = Anthropic(api_key=self._api_key)

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        message = await loop.run_in_executor(
            None,
            lambda: self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return message.content[0].text


class OpenAIProvider(AIProvider):
    """ChatGPT API via OpenAI SDK."""

    DEFAULT_MODEL = "gpt-4o"
    ENV_KEY = "OPENAI_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv(self.ENV_KEY)
        if not resolved_key:
            raise ValueError(f"{self.ENV_KEY} env var or api_key param required")
        super().__init__(resolved_key, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package required. Install with: pip install openai"
                )
            self._client = OpenAI(api_key=self._api_key)

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        completion = await loop.run_in_executor(
            None,
            lambda: self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return completion.choices[0].message.content


class GeminiProvider(AIProvider):
    """Google Gemini API via google-generativeai SDK."""

    DEFAULT_MODEL = "gemini-1.5-flash"
    ENV_KEY = "GOOGLE_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv(self.ENV_KEY)
        if not resolved_key:
            raise ValueError(f"{self.ENV_KEY} env var or api_key param required")
        super().__init__(resolved_key, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                import google.generativeai as genai
            except ImportError:
                raise ImportError(
                    "google-generativeai package required. "
                    "Install with: pip install google-generativeai"
                )
            genai.configure(api_key=self._api_key)
            self._client = genai.GenerativeModel(self._model)

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.generate_content(prompt),
        )
        return response.text


class OllamaProvider(AIProvider):
    """Local Ollama models via ollama SDK."""

    DEFAULT_MODEL = "llama2"
    ENV_KEY = None

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        super().__init__(None, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                import ollama
            except ImportError:
                raise ImportError(
                    "ollama package required. Install with: pip install ollama"
                )
            self._client = ollama

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.chat(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return response["message"]["content"]


class MistralProvider(AIProvider):
    """Mistral API via mistralai SDK."""

    DEFAULT_MODEL = "mistral-large-latest"
    ENV_KEY = "MISTRAL_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv(self.ENV_KEY)
        if not resolved_key:
            raise ValueError(f"{self.ENV_KEY} env var or api_key param required")
        super().__init__(resolved_key, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                from mistralai.client import MistralClient
            except ImportError:
                raise ImportError(
                    "mistralai package required. Install with: pip install mistralai"
                )
            self._client = MistralClient(api_key=self._api_key)

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        message = await loop.run_in_executor(
            None,
            lambda: self._client.chat(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return message.choices[0].message.content


class GroqProvider(AIProvider):
    """Groq API via groq SDK."""

    DEFAULT_MODEL = "mixtral-8x7b-32768"
    ENV_KEY = "GROQ_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv(self.ENV_KEY)
        if not resolved_key:
            raise ValueError(f"{self.ENV_KEY} env var or api_key param required")
        super().__init__(resolved_key, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                from groq import Groq
            except ImportError:
                raise ImportError(
                    "groq package required. Install with: pip install groq"
                )
            self._client = Groq(api_key=self._api_key)

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        completion = await loop.run_in_executor(
            None,
            lambda: self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return completion.choices[0].message.content


class HuggingFaceProvider(AIProvider):
    """Hugging Face Inference API."""

    DEFAULT_MODEL = "meta-llama/Llama-2-70b-chat-hf"
    ENV_KEY = "HF_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv(self.ENV_KEY)
        if not resolved_key:
            raise ValueError(f"{self.ENV_KEY} env var or api_key param required")
        super().__init__(resolved_key, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                from huggingface_hub import InferenceClient
            except ImportError:
                raise ImportError(
                    "huggingface-hub package required. "
                    "Install with: pip install huggingface-hub"
                )
            self._client = InferenceClient(
                model=self._model,
                token=self._api_key,
            )

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.text_generation(prompt, max_new_tokens=1024),
        )
        return response


class TogetherAIProvider(AIProvider):
    """Together.ai open-source model hosting."""

    DEFAULT_MODEL = "meta-llama/Llama-2-70b-chat-hf"
    ENV_KEY = "TOGETHER_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv(self.ENV_KEY)
        if not resolved_key:
            raise ValueError(f"{self.ENV_KEY} env var or api_key param required")
        super().__init__(resolved_key, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                import together
            except ImportError:
                raise ImportError(
                    "together package required. Install with: pip install together"
                )
            together.api_key = self._api_key
            self._client = together

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client.Complete.create(
                model=self._model,
                prompt=prompt,
                max_tokens=1024,
            ),
        )
        return response["output"]["choices"][0]["text"]


class LiteLLMProvider(AIProvider):
    """LiteLLM proxy for 100+ models."""

    DEFAULT_MODEL = "gpt-3.5-turbo"
    ENV_KEY = "LITELLM_API_KEY"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        resolved_key = api_key or os.getenv(self.ENV_KEY)
        if not resolved_key:
            raise ValueError(f"{self.ENV_KEY} env var or api_key param required")
        super().__init__(resolved_key, model)

    def _init_client(self) -> None:
        if self._client is None:
            try:
                from litellm import completion
            except ImportError:
                raise ImportError(
                    "litellm package required. Install with: pip install litellm"
                )
            self._client = completion

    async def query(self, prompt: str) -> str:
        self._init_client()
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._client(
                model=self._model,
                api_key=self._api_key,
                messages=[{"role": "user", "content": prompt}],
            ),
        )
        return response["choices"][0]["message"]["content"]
