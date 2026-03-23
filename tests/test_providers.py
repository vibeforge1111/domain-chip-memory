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


def test_minimax_provider_rescues_previous_occupation_from_context(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 0, "total_tokens": 12},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What was my previous occupation?",
        assembled_context=(
            "reflection: I'm actually thinking of automating some of the workflows in my new role as a senior marketing analyst. "
            "In my previous role as a marketing specialist at a small startup, I was responsible for managing a team of interns."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "marketing specialist at a small startup"


def test_minimax_provider_rescues_numeric_count_from_context(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "12 largemouth bass"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="How many largemouth bass did I catch on my fishing trip to Lake Michigan?",
        assembled_context=(
            "reflection: By the way, I've had some experience with fishing in Lake Michigan, "
            "and I caught 12 largemouth bass on my last trip there."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "12"


def test_minimax_provider_rescues_valentines_day_date(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "In February, on Valentine's Day."}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="When did I volunteer at the local animal shelter's fundraising dinner?",
        assembled_context=(
            "reflection: I've had a great experience with similar events in the past, "
            "like the \"Love is in the Air\" fundraising dinner I volunteered at back on Valentine's Day."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "February 14th"


def test_minimax_provider_rescues_shorter_certification_span(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Data Science certification"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What certification did I complete last month?",
        assembled_context=(
            "reflection: I need to update my LinkedIn profile to reflect my latest certification in Data Science, "
            "which I completed last month."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "Data Science"


def test_minimax_provider_rescues_name_and_age_spans(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "s name is Luna, and she"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What is the name of my cat?",
        assembled_context=(
            "reflection: By the way, my cat's name is Luna, and she's been such a sweetie."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "Luna"


def test_minimax_provider_rescues_numeric_and_ratio_spans(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "ve settled on a 3:1 ratio with a dash of citrus bitters. I"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What is my preferred gin-to-vermouth ratio for a classic gin martini?",
        assembled_context=(
            "reflection: I've settled on a 3:1 ratio with a dash of citrus bitters."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "3:1"


def test_minimax_provider_rescues_article_span_for_cake(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Lemon blueberry cake"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What did I bake for my niece's birthday party?",
        assembled_context=(
            "reflection: I recently made a lemon blueberry cake for my niece's birthday party and it was a huge hit."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "a lemon blueberry cake"


def test_minimax_provider_rescues_class_location_without_leading_at(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "At Serenity Yoga"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="Where do I take my yoga classes?",
        assembled_context="reflection: I take my yoga classes at Serenity Yoga before work.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "Serenity Yoga"


def test_minimax_provider_rescues_discount_percentage(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "10% discount"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What was the discount I got at the bookstore sale?",
        assembled_context="reflection: I found a rare cookbook at the bookstore sale and got a 10% discount.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "10%"


def test_minimax_provider_rescues_cocktail_name_from_infinitive_phrase(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "to make a lavender gin fizz"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What type of cocktail recipe did I try this weekend?",
        assembled_context="reflection: I tried to make a lavender gin fizz this weekend and almost nailed it.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "lavender gin fizz"


def test_minimax_provider_rescues_full_painting_worth_sentence(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Triple the amount you paid"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 5, "total_tokens": 17},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="How much is the painting worth compared to the amount I paid for it?",
        assembled_context="reflection: The painting is worth triple what I paid for it according to the gallery owner.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "The painting is worth triple what I paid for it."


def test_minimax_provider_rescues_numeric_duration_from_word_answer(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Four hours"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="How long did it take me to assemble the IKEA bookshelf?",
        assembled_context="reflection: I just assembled an IKEA bookshelf recently and it took me 4 hours, which wasn't too bad.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "4 hours"


def test_minimax_provider_rescues_cocktail_name_for_last_weekend_question(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "to make a lavender gin fizz"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 6, "total_tokens": 18},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What type of cocktail recipe did I try last weekend?",
        assembled_context="reflection: I tried a lavender gin fizz recipe last weekend, but it didn't quite turn out as expected.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "lavender gin fizz"


def test_minimax_provider_rescues_blank_bulb_answer_from_context(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 0, "total_tokens": 12},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="What type of bulb did I replace in my bedside lamp?",
        assembled_context="reflection: I've been using a Philips LED bulb in my bedside lamp, and I really like the warm tone it provides.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "Philips LED bulb"
