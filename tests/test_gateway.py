"""Tests for omnillm.gateway — LLM Gateway module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omnillm.gateway import LLMGateway, ModelResponse

CONFIG_PATH = Path(__file__).parent.parent / "config" / "models.yaml"


class TestModelResponse:
    """Tests for the ModelResponse dataclass."""

    def test_defaults(self):
        resp = ModelResponse(model_id="test", content="Hello")
        assert resp.model_id == "test"
        assert resp.content == "Hello"
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0
        assert resp.latency_ms == 0.0
        assert resp.cost_usd == 0.0
        assert resp.error is None
        assert resp.metadata == {}

    def test_total_tokens(self):
        resp = ModelResponse(model_id="test", content="Hi", input_tokens=10, output_tokens=5)
        assert resp.total_tokens == 15

    def test_is_error_false(self):
        resp = ModelResponse(model_id="test", content="Hi")
        assert resp.is_error is False

    def test_is_error_true(self):
        resp = ModelResponse(model_id="test", content="", error="API timeout")
        assert resp.is_error is True

    def test_with_all_fields(self):
        resp = ModelResponse(
            model_id="openai-gpt4o",
            content="The answer is 42.",
            input_tokens=50,
            output_tokens=10,
            latency_ms=1234.5,
            cost_usd=0.00045,
            time_to_first_token_ms=200.0,
            metadata={"finish_reason": "stop"},
        )
        assert resp.total_tokens == 60
        assert resp.is_error is False
        assert resp.latency_ms == pytest.approx(1234.5)


class TestLLMGateway:
    """Tests for LLMGateway."""

    def test_init_with_default_config(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        assert len(gw.list_models()) > 0

    def test_list_models_returns_list(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        models = gw.list_models()
        assert isinstance(models, list)
        assert "openai-gpt4o" in models
        assert "claude-3.5-sonnet" in models
        assert "llama3-local" in models

    def test_list_cloud_models(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        cloud = gw.list_cloud_models()
        assert all(gw.get_model_info(m)["type"] == "cloud" for m in cloud)
        assert "openai-gpt4o" in cloud

    def test_list_local_models(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        local = gw.list_local_models()
        assert all(gw.get_model_info(m)["type"] == "local" for m in local)
        assert "llama3-local" in local

    def test_get_model_info_returns_dict(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        info = gw.get_model_info("openai-gpt4o")
        assert isinstance(info, dict)
        assert info["provider"] == "openai"
        assert info["model"] == "gpt-4o"
        assert info["type"] == "cloud"

    def test_get_model_info_unknown_raises(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        with pytest.raises(KeyError, match="not found"):
            gw.get_model_info("nonexistent-model-xyz")

    def test_build_model_string_openai(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        model_str = gw._build_model_string("openai-gpt4o")
        assert model_str == "gpt-4o"

    def test_build_model_string_ollama(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        model_str = gw._build_model_string("llama3-local")
        assert model_str.startswith("ollama/")
        assert "llama3" in model_str

    def test_build_model_string_anthropic(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        model_str = gw._build_model_string("claude-3.5-sonnet")
        assert "claude" in model_str

    def test_calculate_cost_zero_for_local(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        cost = gw._calculate_cost("llama3-local", 1000, 500)
        assert cost == 0.0

    def test_calculate_cost_cloud(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        # openai-gpt4o: $5/1M input, $15/1M output
        cost = gw._calculate_cost("openai-gpt4o", 1_000_000, 0)
        assert cost == pytest.approx(5.0)
        cost = gw._calculate_cost("openai-gpt4o", 0, 1_000_000)
        assert cost == pytest.approx(15.0)


class TestLLMGatewayQuery:
    """Tests for async query methods using mocks."""

    @pytest.mark.asyncio
    async def test_query_unknown_model(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        resp = await gw.query("nonexistent", [{"role": "user", "content": "hi"}])
        assert resp.is_error
        assert "not found" in resp.error

    @pytest.mark.asyncio
    async def test_query_litellm_not_installed(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        with patch.dict("sys.modules", {"litellm": None}):
            resp = await gw.query("openai-gpt4o", [{"role": "user", "content": "hi"}])
        assert resp.is_error

    @pytest.mark.asyncio
    async def test_query_mocked_success(self):
        gw = LLMGateway(config_path=CONFIG_PATH)

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20

        mock_choice = MagicMock()
        mock_choice.message.content = "Test response"

        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_resp.usage = mock_usage

        with patch("litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            resp = await gw.query(
                "openai-gpt4o", [{"role": "user", "content": "hello"}]
            )

        assert not resp.is_error
        assert resp.content == "Test response"
        assert resp.input_tokens == 10
        assert resp.output_tokens == 20
        assert resp.model_id == "openai-gpt4o"

    @pytest.mark.asyncio
    async def test_query_handles_exception(self):
        gw = LLMGateway(config_path=CONFIG_PATH)

        with patch("litellm.acompletion", new_callable=AsyncMock, side_effect=Exception("API error")):
            resp = await gw.query("openai-gpt4o", [{"role": "user", "content": "hi"}])

        assert resp.is_error
        assert "API error" in resp.error

    @pytest.mark.asyncio
    async def test_query_multiple_concurrent(self):
        gw = LLMGateway(config_path=CONFIG_PATH)
        call_count = 0

        async def mock_completion(**kwargs):
            nonlocal call_count
            call_count += 1
            mock_usage = MagicMock()
            mock_usage.prompt_tokens = 5
            mock_usage.completion_tokens = 10
            mock_choice = MagicMock()
            mock_choice.message.content = f"Response {call_count}"
            mock_resp = MagicMock()
            mock_resp.choices = [mock_choice]
            mock_resp.usage = mock_usage
            return mock_resp

        with patch("litellm.acompletion", side_effect=mock_completion):
            responses = await gw.query_multiple(
                ["openai-gpt4o", "claude-3.5-sonnet"],
                [{"role": "user", "content": "hi"}],
            )

        assert len(responses) == 2
        assert call_count == 2
