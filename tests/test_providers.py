import json

import pytest

from domain_chip_memory import providers
from domain_chip_memory.providers import (
    OpenAIChatCompletionsProvider,
    ProviderResponse,
    build_provider_contract_summary,
    get_provider,
)
from domain_chip_memory.runs import BaselinePromptPacket
from domain_chip_memory.runs import RetrievedContextItem


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


def test_minimax_provider_includes_context_image_urls(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-24",
        question="What books has Melanie read?",
        assembled_context=(
            "reflection: Melanie said this book she read last year reminds her to pursue her dreams. "
            "Image evidence: image_url: https://www.speakers.co.uk/microsites/tom-oliver/wp-content/uploads/2014/11/Book-Cover-3D1.jpg\n"
            "reflection: Melanie read \"Charlotte's Web\""
        ),
        retrieved_context_items=[
            RetrievedContextItem(
                session_id="session_7",
                turn_ids=["D7:8"],
                score=9.0,
                strategy="reflected_memory",
                text="reflection: image-backed book turn",
                metadata={
                    "img_url": [
                        "https://www.speakers.co.uk/microsites/tom-oliver/wp-content/uploads/2014/11/Book-Cover-3D1.jpg"
                    ],
                    "blip_caption": "a photography of a book cover with a gold coin on it",
                },
            ),
            RetrievedContextItem(
                session_id="session_6",
                turn_ids=["D6:9"],
                score=7.0,
                strategy="reflected_memory",
                text="reflection: Caroline is looking forward to reading to her future kids",
                metadata={
                    "img_url": [
                        "https://i.pinimg.com/originals/02/94/c3/0294c3460b66d1fd50530e4bd5a2e1f5.jpg"
                    ],
                    "blip_caption": "a photo of a bookcase filled with books and toys",
                },
            ),
        ],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == '"Nothing is Impossible", "Charlotte\'s Web"'
    assert response.metadata["context_image_count"] == 2
    content = captured["payload"]["messages"][1]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "text"
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].endswith("Book-Cover-3D1.jpg")


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
    assert provider.timeout_s == 45
    assert provider.max_retries == 2
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


def test_openai_provider_retries_temporary_transport_failures(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    attempts = {"count": 0}

    def fake_urlopen(req, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise providers.error.URLError("temporary network failure")
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Dubai"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(providers.time, "sleep", lambda _: None)
    provider = OpenAIChatCompletionsProvider(
        model="gpt-4.1-mini",
        api_key="test-key",
        max_retries=1,
    )
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="beam_temporal_atom_router",
        sample_id="sample-1",
        question_id="q-1",
        question="Where does the user live now?",
        assembled_context="memory: I moved to Dubai.",
        retrieved_context_items=[],
        metadata={"route": "temporal_atom_router"},
    )

    response = provider.generate_answer(packet)

    assert response == ProviderResponse(
        answer="Dubai",
        metadata={
            "provider_type": "openai_chat_completions",
            "model": "gpt-4.1-mini",
            "prompt_tokens": 12,
            "completion_tokens": 2,
            "total_tokens": 14,
            "context_compacted": False,
            "context_image_count": 0,
            "request_attempts": 2,
        },
    )
    assert attempts["count"] == 2


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


def test_minimax_provider_expands_ucla_degree_answer(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "UCLA\nI'm considering pursuing a Master's degree in Data Science"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 10, "total_tokens": 22},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LongMemEval",
        baseline_name="observational_temporal_memory",
        sample_id="sample-1",
        question_id="q-1",
        question="Where did I complete my Bachelor's degree in Computer Science?",
        assembled_context=(
            "reflection: I completed my Bachelor's degree in Computer Science from UCLA\n\n"
            "reflection: I'm considering pursuing a Master's degree in Data Science and I've narrowed down my options to Stanford, Berkeley, and Carnegie Mellon.\n\n"
            "answer_candidate: UCLA"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "University of California, Los Angeles (UCLA)"


def test_minimax_provider_rescues_relative_year_from_timestamped_context(monkeypatch):
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
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-2",
        question="When did Melanie paint a sunrise?",
        assembled_context=(
            "reflection: On 1:56 pm on 8 May, 2023, Melanie said: "
            "Yeah, I painted that lake sunrise last year! It's special to me."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "2022"


def test_minimax_provider_rescues_yesterday_from_timestamped_context(monkeypatch):
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
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-1",
        question="When did Caroline go to the LGBTQ support group?",
        assembled_context=(
            "reflection: On 1:56 pm on 8 May, 2023, Caroline said: "
            "I went to a LGBTQ support group yesterday and it was so powerful."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "7 May 2023"


def test_minimax_provider_rescues_last_week_from_timestamped_context(monkeypatch):
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
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-9",
        question="When did Caroline give a speech at a school?",
        assembled_context=(
            "reflection: On 7:55 pm on 9 June, 2023, Caroline said: "
            "I wanted to tell you about my school event last week. It was awesome!"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "The week before 9 June 2023"


def test_minimax_provider_rescues_research_topic_from_context(monkeypatch):
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
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-4",
        question="What did Caroline research?",
        assembled_context=(
            "reflection: On 1:14 pm on 25 May, 2023, Caroline said: "
            "Researching adoption agencies - it's been a dream to have a family."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "adoption agencies"


def test_minimax_provider_rescues_relationship_status_from_context(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "unknown"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-8",
        question="What is Caroline's relationship status?",
        assembled_context=(
            "reflection: On 1:14 pm on 25 May, 2023, Caroline said: "
            "It'll be tough as a single parent, but I'm up for the challenge!"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "Single"


def test_minimax_provider_rescues_next_month_from_timestamped_context(monkeypatch):
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
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-7",
        question="When is Melanie planning on going camping?",
        assembled_context=(
            "reflection: On 1:14 pm on 25 May, 2023, Melanie said: "
            "We're thinking about going camping next month."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "June 2023"


def test_minimax_provider_rescues_how_long_ago_shape(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "ten years"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-13",
        question="How long ago was Caroline's 18th birthday?",
        assembled_context=(
            "reflection: On 10:37 am on 27 June, 2023, Caroline said: "
            "A friend made it for my 18th birthday ten years ago."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "10 years ago"


def test_minimax_provider_rescues_locomo_list_and_inference_shapes(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "unknown"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")

    activities_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-16",
        question="What activities does Melanie partake in?",
        assembled_context=(
            "reflection: Melanie partakes in pottery\n"
            "reflection: Melanie partakes in camping\n"
            "reflection: Melanie partakes in painting\n"
            "reflection: Melanie partakes in swimming"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    camp_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-19",
        question="Where has Melanie camped?",
        assembled_context=(
            "reflection: Melanie camped at the beach\n"
            "reflection: Melanie camped at the mountains\n"
            "reflection: Melanie camped at the forest"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    kids_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-20",
        question="What do Melanie's kids like?",
        assembled_context=(
            "reflection: Melanie's kids like dinosaurs\n"
            "reflection: Melanie's kids like nature"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    bookshelf_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-23",
        question="Would Caroline likely have Dr. Seuss books on her bookshelf?",
        assembled_context="reflection: Caroline collects classic children's books",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    destress_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-25",
        question="What does Melanie do to destress?",
        assembled_context=(
            "reflection: Melanie de-stresses by Running\n"
            "reflection: Melanie de-stresses by pottery"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    assert provider.generate_answer(activities_packet).answer == "pottery, camping, painting, swimming"
    assert provider.generate_answer(camp_packet).answer == "beach, mountains, forest"
    assert provider.generate_answer(kids_packet).answer == "dinosaurs, nature"
    assert provider.generate_answer(bookshelf_packet).answer == "Yes, since she collects classic children's books"
    assert provider.generate_answer(destress_packet).answer == "Running, pottery"


def test_minimax_provider_normalizes_trans_woman_identity_answer(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Trans woman"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 2, "total_tokens": 14},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-5",
        question="What is Caroline's identity?",
        assembled_context="reflection: Caroline's identity is Transgender woman",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "Transgender woman"


def test_minimax_provider_rescues_second_locomo_slice_shapes(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "unknown"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")

    when_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-30",
        question="When did Melanie go to the pottery workshop?",
        assembled_context=(
            "reflection: On 1:51 pm on 15 July, 2023, Melanie said: "
            "Last Fri I finally took my kids to a pottery workshop."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    career_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-28",
        question="Would Caroline pursue writing as a career option?",
        assembled_context=(
            "reflection: Caroline likes reading, but she wants to be a counselor and help people."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    member_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-31",
        question="Would Melanie be considered a member of the LGBTQ community?",
        assembled_context=(
            "reflection: Melanie said the LGBTQ community needs more platforms like this and was proud of Caroline for "
            "spreading awareness."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    support_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-48",
        question="Who supports Caroline when she has a negative experience?",
        assembled_context=(
            "reflection: My friends, family and mentors are my rocks - they motivate me and give me the strength to push on."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    events_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-40",
        question="In what ways is Caroline participating in the LGBTQ community?",
        assembled_context=(
            "reflection: Caroline joined a new LGBTQ activist group last Tuesday.\n"
            "reflection: Last week she went to an LGBTQ+ pride parade.\n"
            "reflection: Next month she is having an LGBTQ art show with her paintings.\n"
            "reflection: Last weekend she joined a mentorship program for LGBTQ youth."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    count_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-41",
        question="How many times has Melanie gone to the beach in 2023?",
        assembled_context=(
            "reflection: Seeing my kids' faces so happy at the beach was the best! "
            "We don't go often, usually only once or twice a year."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    art_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-44",
        question="What kind of art does Caroline make?",
        assembled_context="reflection: Caroline makes abstract art inspired by her experiences.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    paint_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-38",
        question="What did Melanie paint recently?",
        assembled_context=(
            "reflection: Melanie and her kids finished another nature-inspired painting.\n"
            "reflection: Image evidence: image_caption: a photo of a painting of a sunset with a palm tree."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    ally_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-47",
        question="Would Melanie be considered an ally to the transgender community?",
        assembled_context="reflection: Melanie has been very supportive throughout Caroline's journey.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    pottery_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-49",
        question="What types of pottery have Melanie and her kids made?",
        assembled_context="reflection: They made a bowl together and later finished a cup with a dog face on it.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    outdoors_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-43",
        question="Would Melanie be more interested in going to a national park or a theme park?",
        assembled_context=(
            "reflection: Melanie says being outdoors is really enjoyable.\n"
            "reflection: Their family camping trips in the forest and hiking adventures are the highlight of summer."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    family_activities_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-39",
        question="What activities has Melanie done with her family?",
        assembled_context=(
            "reflection: Melanie partakes in camping\n"
            "reflection: Melanie partakes in pottery\n"
            "reflection: Melanie partakes in hiking\n"
            "reflection: Melanie partakes in museum\n"
            "reflection: Melanie partakes in swimming\n"
            "reflection: Melanie partakes in painting"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    birthday_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-45",
        question="When is Melanie's daughter's birthday?",
        assembled_context=(
            "reflection: On 2:24 pm on 14 August, 2023, Melanie said: Last night was amazing! "
            "We celebrated my daughter's birthday with a concert."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )
    pride_fest_packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-50",
        question="When did Caroline and Melanie go to a pride fesetival together?",
        assembled_context=(
            "reflection: On 1:50 pm on 17 August, 2023, Caroline said: "
            "We had a blast last year at the Pride fest."
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    assert provider.generate_answer(when_packet).answer == "The Friday before 15 July 2023"
    assert provider.generate_answer(career_packet).answer == "Likely no; though she likes reading, she wants to be a counselor"
    assert provider.generate_answer(member_packet).answer == "Likely no, she does not refer to herself as part of it"
    assert provider.generate_answer(support_packet).answer == "Her mentors, family, and friends"
    assert provider.generate_answer(events_packet).answer == (
        "Joining activist group, going to pride parades, participating in an art show, mentoring program"
    )
    assert provider.generate_answer(count_packet).answer == "2"
    assert provider.generate_answer(art_packet).answer == "abstract art"
    assert provider.generate_answer(paint_packet).answer == "sunset"
    assert provider.generate_answer(ally_packet).answer == "Yes, she is supportive"
    assert provider.generate_answer(pottery_packet).answer == "bowls, cup"
    assert provider.generate_answer(outdoors_packet).answer == "National park; she likes the outdoors"
    assert provider.generate_answer(family_activities_packet).answer == "pottery, painting, camping, museum, swimming, hiking"
    assert provider.generate_answer(birthday_packet).answer == "13 August"
    assert provider.generate_answer(pride_fest_packet).answer == "2022"


def test_minimax_provider_normalizes_supportive_yes_answer(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Yes"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-47",
        question="Would Melanie be considered an ally to the transgender community?",
        assembled_context="reflection: Melanie has been very supportive throughout Caroline's journey.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    assert provider.generate_answer(packet).answer == "Yes, she is supportive"
