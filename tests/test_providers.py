import json

import pytest

from domain_chip_memory import providers
from domain_chip_memory.providers import (
    OpenAIChatCompletionsProvider,
    build_provider_contract_summary,
    get_provider,
)
from domain_chip_memory.runs import BaselinePromptPacket


class _FakeHTTPResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_get_provider_supports_openai_pattern(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = get_provider("openai:gpt-4.1-mini")
    assert isinstance(provider, OpenAIChatCompletionsProvider)
    assert provider.name == "openai:gpt-4.1-mini"


def test_openai_provider_requires_model_if_not_in_name(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("DOMAIN_CHIP_MEMORY_OPENAI_MODEL", raising=False)
    with pytest.raises(ValueError):
        get_provider("openai")


def test_openai_provider_uses_env_model_and_chat_completions(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["url"] = req.full_url
        captured["timeout"] = timeout
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Dubai"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("openai")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="beam_temporal_atom_router",
        sample_id="sample-1",
        question_id="q-1",
        question="Where does the user live now?",
        assembled_context="Session 1: I live in Dubai now.",
        retrieved_context_items=[],
        metadata={"route": "temporal_atom_router"},
    )
    response = provider.generate_answer(packet)

    assert response.answer == "Dubai"
    assert response.metadata["provider_type"] == "openai_chat_completions"
    assert response.metadata["model"] == "gpt-4.1-mini"
    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["timeout"] == 120
    assert captured["payload"]["model"] == "gpt-4.1-mini"
    assert captured["payload"]["messages"][1]["content"].startswith("Benchmark: LongMemEval")


def test_provider_contract_summary_lists_openai():
    payload = build_provider_contract_summary()
    names = [item.get("name") or item.get("name_pattern") for item in payload["providers"]]
    assert "heuristic_v1" in names
    assert "openai:<model>" in names
    assert "minimax:<model>" in names


def test_get_provider_supports_minimax_pattern(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    provider = get_provider("minimax:MiniMax-M1")
    assert isinstance(provider, OpenAIChatCompletionsProvider)
    assert provider.name == "minimax:MiniMax-M1"
    assert provider.base_url == "https://api.minimax.io/v1"
    assert provider.extra_body == {"reasoning_split": True}
    assert provider.include_packet_metadata is False
    assert provider.compact_context_lines == 8
    assert provider.enable_exact_span_rescue is True
    assert provider.max_tokens == 512
    assert provider.temperature == 0.3


def test_openai_answer_extractor_strips_think_tags(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "<think>reasoning</think>Business Administration"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="beam_temporal_atom_router",
        sample_id="sample-1",
        question_id="q-1",
        question="What degree did I graduate with?",
        assembled_context="memory: Congratulations on your degree in Business Administration!",
        retrieved_context_items=[],
        metadata={"route": "temporal_atom_router"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "Business Administration"
    assert captured["payload"]["reasoning_split"] is True


def test_minimax_provider_expands_partial_duration_answer(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "45 minutes"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="How long is my daily commute to work?",
        assembled_context=(
            "reflection: I've been listening to audiobooks during my daily commute, "
            "which takes 45 minutes each way."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "45 minutes each way"
    assert response.metadata["context_compacted"] is True
