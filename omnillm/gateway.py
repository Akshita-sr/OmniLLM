"""Unified LLM Gateway using LiteLLM.

This module provides a single interface to query 100+ LLM providers through
LiteLLM, abstracting away provider-specific API differences. It handles:
- Provider-specific model string construction (ollama/, openai/, anthropic/, etc.)
- Cost calculation from the model registry (config/models.yaml)
- Latency measurement with high-resolution timers
- Graceful error handling with structured error responses
- Concurrent multi-model querying via asyncio

Note: ``litellm.drop_params = True`` is set at module level so that
unsupported parameters (e.g. ``temperature`` for o-series/gpt-5 models) are
silently dropped rather than raising ``UnsupportedParamsError``.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import litellm
import yaml

litellm.drop_params = True
# Suppress LiteLLM's background LoggingWorker — the Flask server runs each
# request in a short-lived event loop, so the worker task is orphaned at
# loop close, producing noisy "Task was destroyed but it is pending" errors.
# We don't use LiteLLM callbacks anyway; OmniLLM logs via ExperimentLogger.
litellm.callbacks = []
litellm.success_callback = []
litellm.failure_callback = []
litellm._async_success_callback = []
litellm._async_failure_callback = []


@dataclass
class ModelResponse:
    """Structured response from an LLM query."""

    model_id: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0
    time_to_first_token_ms: float = 0.0
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.input_tokens + self.output_tokens

    @property
    def is_error(self) -> bool:
        """True if this response contains an error."""
        return self.error is not None


class LLMGateway:
    """Unified LLM Gateway — single interface to all registered models.

    Loads model configuration from models.yaml and uses LiteLLM to route
    requests to the correct provider with proper authentication.

    Example::

        gateway = LLMGateway()
        response = await gateway.query(
            "openai-gpt4o",
            [{"role": "user", "content": "Hello!"}]
        )
        print(response.content)
    """

    def __init__(self, config_path: str | Path | None = None) -> None:
        """Initialise the gateway from a model registry YAML file.

        Args:
            config_path: Path to models.yaml.  Defaults to
                ``<repo_root>/config/models.yaml`` relative to this file.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "models.yaml"
        self._config_path = Path(config_path)
        self._config: dict[str, Any] = {}
        self._models: dict[str, dict[str, Any]] = {}
        self._load_config()

    # ── Private helpers ──────────────────────────────────────────────────────

    def _load_config(self) -> None:
        """Load and validate models.yaml."""
        with open(self._config_path, "r", encoding="utf-8") as fh:
            self._config = yaml.safe_load(fh)
        self._models = self._config.get("models", {})

    def _build_model_string(self, model_id: str) -> str:
        """Construct the LiteLLM model string for a registered model.

        LiteLLM uses prefixes to route to different providers.  For example:
        - Ollama: ``ollama/llama3:8b``
        - OpenAI: ``gpt-4o`` (no prefix needed)
        - Anthropic: ``claude-3-5-sonnet-20241022`` (no prefix needed)
        - Generic OpenAI-compatible: ``openai/<model>`` with custom api_base
        """
        cfg = self._models[model_id]
        provider = cfg.get("provider", "openai")
        model = cfg["model"]

        if provider == "ollama":
            return f"ollama/{model}"
        if provider == "openai_compatible":
            return f"openai/{model}"
        if provider == "deepseek":
            return f"openai/{model}"
        if provider == "google":
            return f"gemini/{model}"
        if provider == "anthropic":          
            return f"anthropic/{model}"
        # For openai, anthropic — LiteLLM uses the model name directly
        return model

    def _calculate_cost(
        self, model_id: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Estimate cost in USD based on model's per-million-token pricing."""
        cfg = self._models.get(model_id, {})
        cost_in = cfg.get("cost_per_1m_input", 0.0)
        cost_out = cfg.get("cost_per_1m_output", 0.0)
        return (input_tokens * cost_in + output_tokens * cost_out) / 1_000_000

    # ── Public listing API ───────────────────────────────────────────────────

    def list_models(self) -> list[str]:
        """Return all registered model IDs."""
        return list(self._models.keys())

    def list_cloud_models(self) -> list[str]:
        """Return model IDs for cloud-hosted models."""
        return [
            mid
            for mid, cfg in self._models.items()
            if cfg.get("type", "cloud") == "cloud"
        ]

    def list_local_models(self) -> list[str]:
        """Return model IDs for locally-hosted models (Ollama, etc.)."""
        return [
            mid
            for mid, cfg in self._models.items()
            if cfg.get("type", "cloud") == "local"
        ]

    def get_model_info(self, model_id: str) -> dict[str, Any]:
        """Return the configuration dict for a specific model.

        Args:
            model_id: Registered model identifier.

        Returns:
            Model configuration dictionary.

        Raises:
            KeyError: If model_id is not registered.
        """
        if model_id not in self._models:
            raise KeyError(f"Model '{model_id}' not found in registry.")
        return dict(self._models[model_id])

    # ── Query API ────────────────────────────────────────────────────────────

    async def query(
        self,
        model_id: str,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> ModelResponse:
        """Query a single model and return a structured response.

        Args:
            model_id: Registered model identifier.
            messages: OpenAI-style message list (role/content dicts).
            temperature: Sampling temperature (0.0 = deterministic).
            max_tokens: Maximum tokens to generate.

        Returns:
            :class:`ModelResponse` with content, tokens, latency and cost.
            On error, returns a response with ``error`` field set.
        """
        if model_id not in self._models:
            return ModelResponse(
                model_id=model_id,
                content="",
                error=f"Model '{model_id}' not found in registry.",
            )

        cfg = self._models[model_id]
        model_string = self._build_model_string(model_id)

        kwargs: dict[str, Any] = {
            "model": model_string,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Set provider-specific API base / key
        api_base = cfg.get("api_base")
        if api_base:
            kwargs["api_base"] = api_base

        api_key_env = cfg.get("api_key_env")
        if api_key_env:
            import os

            api_key = os.environ.get(api_key_env, "")
            if api_key:
                kwargs["api_key"] = api_key

        start = time.perf_counter()
        try:
            resp = await litellm.acompletion(**kwargs)
            latency_ms = (time.perf_counter() - start) * 1000

            content = resp.choices[0].message.content or ""
            usage = getattr(resp, "usage", None)
            input_tokens = getattr(usage, "prompt_tokens", 0) or 0
            output_tokens = getattr(usage, "completion_tokens", 0) or 0
            cost = self._calculate_cost(model_id, input_tokens, output_tokens)

            return ModelResponse(
                model_id=model_id,
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cost_usd=cost,
            )
        except Exception as exc:  # noqa: BLE001
            latency_ms = (time.perf_counter() - start) * 1000
            return ModelResponse(
                model_id=model_id,
                content="",
                latency_ms=latency_ms,
                error=str(exc),
            )

    async def query_multiple(
        self,
        model_ids: list[str],
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> list[ModelResponse]:
        """Query multiple models concurrently.

        Uses :func:`asyncio.gather` to dispatch all queries simultaneously,
        dramatically reducing wall-clock time compared to sequential queries.

        Args:
            model_ids: List of registered model identifiers.
            messages: OpenAI-style message list shared across all models.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate per model.

        Returns:
            List of :class:`ModelResponse` objects in the same order as
            *model_ids*.
        """
        tasks = [
            self.query(mid, messages, temperature, max_tokens) for mid in model_ids
        ]
        return list(await asyncio.gather(*tasks))
