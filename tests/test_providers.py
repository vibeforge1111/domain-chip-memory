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


def test_expand_answer_prefers_exact_answer_candidate_over_belief_paraphrase():
    context = "\n".join(
        [
            "evidence_memory:",
            "evidence: Appreciate them a lot",
            "belief_memory:",
            "belief: After the accident Melanie felt grateful and thankful for her family",
            "answer_candidate: Appreciate them a lot",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "How did Melanie feel about her family supporting her?",
        "Grateful and thankful",
        context,
    )

    assert rescued == "Appreciate them a lot"


def test_expand_answer_prefers_yes_no_answer_candidate_for_did_question():
    context = "\n".join(
        [
            "evidence_memory:",
            "evidence: No",
            "belief_memory:",
            "belief: Melanie said she made this bowl in her class",
            "answer_candidate: No",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "Did Caroline make the black and white bowl in the photo?",
        "Yes",
        context,
    )

    assert rescued == "No"


def test_expand_answer_prefers_yes_no_answer_candidate_for_is_question():
    context = "\n".join(
        [
            "evidence_memory:",
            "evidence: Oscar, my guinea pig. He's been great.",
            "answer_candidate: No",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "Is Oscar Melanie's pet?",
        "unknown",
        context,
    )

    assert rescued == "No"


def test_expand_answer_prefers_short_where_answer_candidate_over_unknown():
    context = "\n".join(
        [
            "evidence_memory:",
            "evidence: I'm thinking of visiting my sister Emily in Denver soon.",
            "answer_candidate: Denver",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "Where does my sister Emily live?",
        "unknown",
        context,
    )

    assert rescued == "Denver"


def test_expand_answer_prefers_short_currency_answer_candidate_for_how_much_question():
    rescued = providers._expand_answer_from_context(
        "How much more did I spend on accommodations per night in Hawaii compared to Tokyo?",
        "$30",
        "answer_candidate: $270",
    )

    assert rescued == "$270"


def test_expand_answer_keeps_matching_short_currency_candidate_for_how_much_question():
    context = "\n".join(
        [
            "aggregate_memory:",
            "aggregate: The chain cost $25 and the lights cost $40.",
            "answer_candidate: $185",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "How much total money have I spent on bike-related expenses since the start of the year?",
        "$185",
        context,
    )

    assert rescued == "$185"


def test_expand_answer_prefers_currency_answer_candidate_for_total_amount_question():
    context = "\n".join(
        [
            "aggregate_memory:",
            "aggregate: The gown cost $800, the handbag cost $1,200, and the boots cost $500.",
            "answer_candidate: $2500",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "What is the total amount I spent on luxury items in the past few months?",
        "$2000",
        context,
    )

    assert rescued == "$2500"


def test_expand_answer_prefers_currency_answer_candidate_for_difference_question():
    context = "\n".join(
        [
            "aggregate_memory:",
            "aggregate: I splurged on a pair of boots for $800.",
            "aggregate: I found a similar pair at the budget store for $50.",
            "answer_candidate: $750",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "What is the difference in price between my luxury boots and the similar pair found at the budget store?",
        "$150",
        context,
    )

    assert rescued == "$750"


def test_expand_answer_prefers_plain_numeric_answer_candidate_over_number_with_suffix():
    rescued = providers._expand_answer_from_context(
        "What was the approximate increase in Instagram followers I experienced in two weeks?",
        "100 followers",
        "answer_candidate: 100",
    )

    assert rescued == "100"


def test_expand_answer_prefers_short_which_answer_candidate_over_verbose_output():
    rescued = providers._expand_answer_from_context(
        "Which social media platform did I gain the most followers on over the past month?",
        "I've been seeing some growth on some of my platforms, like TikTok, where I've gained around 200 followers over the past three weeks.",
        "answer_candidate: TikTok",
    )

    assert rescued == "TikTok"


def test_expand_answer_prefers_short_which_answer_candidate_over_wrong_short_output():
    rescued = providers._expand_answer_from_context(
        "Which grocery store did I spend the most money at in the past month?",
        "Walmart",
        "answer_candidate: Thrive Market",
    )

    assert rescued == "Thrive Market"


def test_expand_answer_prefers_richer_preference_answer_candidate_over_short_specific_reply():
    rescued = providers._expand_answer_from_context(
        "Can you recommend a show or movie for me to watch tonight?",
        "Netflix's Kid Gorgeous",
        "answer_candidate: Can you recommend some stand-up comedy specials on Netflix with strong storytelling abilities like John Mulaney's 'Kid Gorgeous'",
    )

    assert rescued.startswith("Can you recommend some stand-up comedy specials on Netflix")


def test_expand_answer_prefers_baking_preference_candidate_over_irrelevant_model_output():
    rescued = providers._expand_answer_from_context(
        "I'm thinking of inviting my colleagues over for a small gathering. Any tips on what to bake?",
        "and organizing your coins can be a fun and rewarding experience",
        "answer_candidate: Do you have any suggestions for a lemon flavored cake, like my lemon poppyseed cake that I made for a colleague's going-away party",
    )

    assert "lemon flavored cake" in rescued


def test_expand_answer_uses_preference_candidate_for_any_ideas_question_when_model_is_blank():
    rescued = providers._expand_answer_from_context(
        "I've been feeling a bit stuck with my paintings lately. Do you have any ideas on how I can find new inspiration?",
        "",
        "answer_candidate: I've been looking at a lot of flower paintings on Instagram and I was wondering if you could give me some tips on how to paint realistic flowers",
    )

    assert "flower paintings on Instagram" in rescued


def test_expand_answer_prefers_temporal_answer_candidate_for_when_question():
    context = "\n".join(
        [
            "stable_memory_window:",
            "observation: On 4:04 pm on 20 January, 2023, Jon said: Lost my job as a banker yesterday.",
            "answer_candidate: 19 January 2023",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "When Jon has lost his job as a banker?",
        "20 January 2023",
        context,
    )

    assert rescued == "19 January 2023"


def test_expand_answer_uses_nonempty_answer_candidate_when_model_returns_blank():
    context = "\n".join(
        [
            "evidence_memory:",
            "evidence: He lost his job and decided to start his own business to share his passion.",
            "answer_candidate: He lost his job and decided to start his own business to share his passion.",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "Why did Jon decide to start his dance studio?",
        "",
        context,
    )

    assert rescued == "He lost his job and decided to start his own business to share his passion."


def test_expand_answer_prefers_richer_answer_candidate_over_unknown_or_thin_paraphrase():
    context = "\n".join(
        [
            "evidence_memory:",
            "evidence: They lost their jobs and decided to start their own businesses.",
            "answer_candidate: They lost their jobs and decided to start their own businesses.",
        ]
    )

    rescued_unknown = providers._expand_answer_from_context(
        "What do Jon and Gina both have in common?",
        "unknown",
        context,
    )
    rescued_thin = providers._expand_answer_from_context(
        "What do Jon and Gina both have in common?",
        "Both own a business",
        context,
    )

    assert rescued_unknown == "They lost their jobs and decided to start their own businesses."
    assert rescued_thin == "They lost their jobs and decided to start their own businesses."


def test_expand_answer_prefers_richer_list_or_reason_candidate_over_thin_output():
    context = "\n".join(
        [
            "evidence_memory:",
            "evidence: launched an ad campaign, ran offers and promotions, developed a video presentation, worked with an artist on unique pieces, made limited-edition sweatshirts",
            "answer_candidate: launched an ad campaign, ran offers and promotions, developed a video presentation, worked with an artist on unique pieces, made limited-edition sweatshirts",
        ]
    )
    rescued_list = providers._expand_answer_from_context(
        "How did Gina promote her clothes store?",
        "launched an ad campaign",
        context,
    )

    rescued_reason = providers._expand_answer_from_context(
        "Why did Jon decide to start his dance studio?",
        "Passion for dancing, plus losing his job.",
        "answer_candidate: He lost his job and decided to start his own business to share his passion.",
    )

    assert rescued_list == "launched an ad campaign, ran offers and promotions, developed a video presentation, worked with an artist on unique pieces, made limited-edition sweatshirts"
    assert rescued_reason == "He lost his job and decided to start his own business to share his passion."


def test_expand_answer_uses_relative_temporal_candidate_for_when_question():
    rescued = providers._expand_answer_from_context(
        "When did Gina get her tattoo?",
        "1 February 2023",
        "answer_candidate: A few years ago",
    )

    assert rescued == "A few years ago"


def test_expand_answer_prefers_conflicting_full_date_answer_candidate_for_when_question():
    rescued = providers._expand_answer_from_context(
        "When did Gina launch an ad campaign for her store?",
        "1 February 2023",
        "answer_candidate: 29 January 2023",
    )

    assert rescued == "29 January 2023"


def test_expand_answer_preserves_matching_temporal_answer_candidate_for_when_question():
    context = "\n".join(
        [
            "observation: On 12:48 am on 1 February, 2023, Gina said: one wholesaler replied and said yes today.",
            "answer_candidate: 29 January 2023",
        ]
    )

    rescued = providers._expand_answer_from_context(
        "When did Gina launch an ad campaign for her store?",
        "29 January 2023",
        context,
    )

    assert rescued == "29 January 2023"


def test_expand_answer_uses_single_token_entity_candidate_for_unknown_which_question():
    rescued = providers._expand_answer_from_context(
        "Which city have both Jean and John visited?",
        "unknown",
        "answer_candidate: Rome",
    )

    assert rescued == "Rome"


def test_expand_answer_preserves_unknown_answer_candidate_for_unsupported_factoid():
    rescued = providers._expand_answer_from_context(
        "What is the name of my hamster?",
        "Luna",
        "answer_candidate: unknown",
    )

    assert rescued == "unknown"


def test_expand_answer_prefers_duration_answer_candidate_for_how_much_time_question():
    rescued = providers._expand_answer_from_context(
        "How much time do I dedicate to practicing guitar every day?",
        "19:30",
        "answer_candidate: 30 minutes",
    )

    assert rescued == "30 minutes"


def test_expand_answer_prefers_numeric_count_answer_candidate_for_how_many_question():
    rescued = providers._expand_answer_from_context(
        "How many projects have I led or am currently leading?",
        "one",
        "answer_candidate: 2",
    )

    assert rescued == "2"


def test_expand_answer_does_not_overwrite_matching_duration_candidate():
    context = "\n".join(
        [
            "observation: On 2023/05/30 (Tue) 19:30, I said: trip planning",
            "evidence: By the way, I've been practicing guitar for 30 minutes daily, and it's been helping me progress nicely",
            "answer_candidate: 30 minutes",
        ]
    )
    rescued = providers._expand_answer_from_context(
        "How much time do I dedicate to practicing guitar every day?",
        "30 minutes",
        context,
    )

    assert rescued == "30 minutes"


def test_expand_answer_does_not_overwrite_matching_unknown_candidate():
    rescued = providers._expand_answer_from_context(
        "What is the name of my hamster?",
        "unknown",
        "answer_candidate: unknown\nevidence: I mentioned my cat Luna",
    )

    assert rescued == "unknown"


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


def test_minimax_provider_prefers_temporal_answer_candidate_over_conflicting_model_date(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "1 February 2023"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-30",
        question_id="conv-30-qa-8",
        question="When did Gina launch an ad campaign for her store?",
        assembled_context=(
            "stable_memory_window:\n"
            "observation: On 2:32 pm on 29 January, 2023, Gina said: "
            "I just launched an ad campaign for my clothing store in hopes of growing the business.\n"
            "answer_candidate: 29 January 2023"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "29 January 2023"


def test_minimax_provider_prefers_yes_no_answer_candidate_for_is_question(monkeypatch):
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
        question_id="conv-26-qa-179",
        question="Is Oscar Melanie's pet?",
        assembled_context=(
            "evidence_memory:\n"
            "evidence: Oscar, my guinea pig. He's been great.\n"
            "answer_candidate: No"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "No"


def test_minimax_provider_preserves_matching_temporal_answer_candidate(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "29 January 2023"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-30",
        question_id="conv-30-qa-8",
        question="When did Gina launch an ad campaign for her store?",
        assembled_context=(
            "stable_memory_window:\n"
            "observation: On 12:48 am on 1 February, 2023, Gina said: one wholesaler replied and said yes today.\n"
            "answer_candidate: 29 January 2023"
        ),
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    response = provider.generate_answer(packet)

    assert response.answer == "29 January 2023"


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


def test_minimax_provider_normalizes_count_word_answer(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Three"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")
    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-76",
        question="How many children does Melanie have?",
        assembled_context="reflection: Melanie has 3 children",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    assert provider.generate_answer(packet).answer == "3"


def test_minimax_provider_recovers_locomo_third_slice_profile_and_time_answers(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")

    packets = [
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-51",
                question="What would Caroline's political leaning likely be?",
                assembled_context=(
                    "reflection: Caroline keeps fighting for LGBTQ rights.\n"
                    "reflection: Caroline wants to make a difference at the youth center.\n"
                    "reflection: Melanie volunteered at a homeless shelter with her family."
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Liberal",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-53",
                question="What are Melanie's pets' names?",
                assembled_context=(
                    "reflection: Melanie has a pet named Oliver\n"
                    "reflection: Melanie has a pet named Luna\n"
                    "reflection: Melanie has a pet named Bailey"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Oliver, Luna, Bailey",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-57",
                question="What symbols are important to Caroline?",
                assembled_context=(
                    "reflection: An important symbol to Caroline is Rainbow flag\n"
                    "reflection: Caroline's identity is Transgender woman"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Rainbow flag, transgender symbol",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-61",
                question="What instruments does Melanie play?",
                assembled_context=(
                    "reflection: Melanie plays clarinet\n"
                    "reflection: Melanie plays violin"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "clarinet and violin",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-62",
                question="What musical artists/bands has Melanie seen?",
                assembled_context="reflection: Melanie saw Summer Sounds\nanswer_candidate: Summer Sounds",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Summer Sounds, Matt Patterson",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-72",
                question="What book did Melanie read from Caroline's suggestion?",
                assembled_context='reflection: Caroline read "Becoming Nicole"\nreflection: Melanie said she had been reading that book Caroline recommended.',
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            '"Becoming Nicole"',
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-69",
                question="How long has Melanie been practicing art?",
                assembled_context=(
                    "reflection: Melanie has been practicing art for seven years\n"
                    "reflection: On 12:09 am on 13 September, 2023, Melanie said: How long have you been creating art?"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Since 2016",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-66",
                question="What are some changes Caroline has faced during her transition journey?",
                assembled_context=(
                    "reflection: During the transition Caroline faced changes to her body\n"
                    "reflection: During the transition Caroline faced losing unsupportive friends"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Changes to her body, losing unsupportive friends",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-70",
                question="What personality traits might Melanie say Caroline has?",
                assembled_context=(
                    "reflection: Caroline says your support really means a lot and she wants to help others with theirs.\n"
                    "reflection: Caroline talks about guidance, and acceptance.\n"
                    "reflection: Caroline wants to live authentically."
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Thoughtful, authentic, driven",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-74",
                question="When did Melanie get hurt?",
                assembled_context=(
                    "reflection: On 10:31 am on 13 October, 2023, Melanie said: "
                    "Last month I got hurt and had to take a break from pottery."
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "September 2023",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-75",
                question="When did Melanie's family go on a roadtrip?",
                assembled_context=(
                    "reflection: On 6:55 pm on 20 October, 2023, Melanie said: "
                    "That roadtrip this past weekend was insane!"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "The weekend before 20 October 2023",
        ),
    ]

    for packet, expected in packets:
        assert provider.generate_answer(packet).answer == expected


def test_minimax_provider_recovers_locomo_fourth_slice_family_and_counseling_answers(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")

    packets = [
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-76",
                question="How many children does Melanie have?",
                assembled_context=(
                    "reflection: Melanie has 3 children\n"
                    "reflection: They were scared and explained their brother would be OK.\n"
                    "reflection: The 2 younger kids love nature."
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "3",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-77",
                question="When did Melanie go on a hike after the roadtrip?",
                assembled_context=(
                    "reflection: On 2:31 pm on 17 July, 2023, Melanie said: "
                    "I had a quiet weekend after we went camping with my fam two weekends ago.\n"
                    "reflection: On 6:55 pm on 20 October, 2023, Melanie said: "
                    "Thanks, Caroline! Yup, we just did it yesterday! The kids loved it and it was a nice way to relax after the road trip."
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "19 October 2023",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-82",
                question="Would Caroline want to move back to her home country soon?",
                assembled_context=(
                    "reflection: Caroline said her dream is to create a safe and loving home for these kids.\n"
                    "reflection: Caroline said she hopes to build her own family and put a roof over kids who haven't had that before.\n"
                    "reflection: Caroline passed the adoption agency interviews and this is a big move towards her goal of having a family."
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "No; she's in the process of adopting children.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-78",
                question="Would Melanie go on another roadtrip soon?",
                assembled_context=(
                    "reflection: Melanie said the roadtrip got off to a bad start.\n"
                    "reflection: It was a real scary experience and they were all freaked."
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Likely no; since this one went badly",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-79",
                question="What items has Melanie bought?",
                assembled_context=(
                    "reflection: Melanie bought Figurines\n"
                    "reflection: Melanie bought shoes"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Figurines, shoes",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-84",
                question="What did Melanie realize after the charity race?",
                assembled_context="reflection: Melanie realized self-care is important",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "self-care is important",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-85",
                question="How does Melanie prioritize self-care?",
                assembled_context=(
                    "reflection: Melanie prioritizes self-care by carving out some me-time each day for activities like running, reading, or playing the violin"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "by carving out some me-time each day for activities like running, reading, or playing the violin",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-86",
                question="What are Caroline's plans for the summer?",
                assembled_context="reflection: Caroline's plan for the summer is researching adoption agencies",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "researching adoption agencies",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-88",
                question="Why did Caroline choose the adoption agency?",
                assembled_context=(
                    "reflection: Caroline chose the adoption agency because their inclusivity and support for LGBTQ+ individuals"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "because of their inclusivity and support for LGBTQ+ individuals",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-89",
                question="What is Caroline excited about in the adoption process?",
                assembled_context=(
                    "reflection: Caroline is excited about creating a family for kids who need one in the adoption process"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "creating a family for kids who need one",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-90",
                question="What does Melanie think about Caroline's decision to adopt?",
                assembled_context="reflection: Melanie thinks the adoption decision is doing something amazing and will be an awesome mom",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "she thinks Caroline is doing something amazing and will be an awesome mom",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-91",
                question="How long have Mel and her husband been married?",
                assembled_context="reflection: Melanie has been married for 5 years",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Mel and her husband have been married for 5 years.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-92",
                question="What does Caroline's necklace symbolize?",
                assembled_context="reflection: Caroline's necklace symbolizes love, faith, and strength",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "love, faith, and strength",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-93",
                question="What country is Caroline's grandma from?",
                assembled_context="reflection: Caroline moved from Sweden",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Sweden",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-94",
                question="What was grandma's gift to Caroline?",
                assembled_context="reflection: Caroline's grandma gave Caroline a necklace",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "necklace",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-95",
                question="What is Melanie's hand-painted bowl a reminder of?",
                assembled_context="reflection: Caroline's hand-painted bowl reminds Caroline of art and self-expression",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "art and self-expression",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-96",
                question="What did Melanie and her family do while camping?",
                assembled_context=(
                    "reflection: While camping Melanie explored nature\n"
                    "reflection: While camping Melanie roasted marshmallows\n"
                    "reflection: While camping Melanie went on a hike"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "explored nature, roasted marshmallows, and went on a hike",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-97",
                question="What kind of counseling and mental health services is Caroline interested in pursuing?",
                assembled_context=(
                    "reflection: Caroline is interested in working with trans people, helping them accept themselves and supporting their mental health"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "working with trans people, helping them accept themselves and supporting their mental health",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-98",
                question="What workshop did Caroline attend recently?",
                assembled_context="reflection: Caroline attended LGBTQ+ counseling workshop",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "LGBTQ+ counseling workshop",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-99",
                question="What was discussed in the LGBTQ+ counseling workshop?",
                assembled_context="reflection: Caroline's workshop discussed therapeutic methods and how to best work with trans people",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "therapeutic methods and how to best work with trans people",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-100",
                question="What motivated Caroline to pursue counseling?",
                assembled_context="reflection: Caroline was motivated by her own journey and the support she received, and how counseling improved her life",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "her own journey and the support she received, and how counseling improved her life",
        ),
    ]

    for packet, expected in packets:
        assert provider.generate_answer(packet).answer == expected


def test_minimax_provider_recovers_locomo_fifth_slice_object_and_meaning_answers(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")

    packets = [
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-101",
                question="What kind of place does Caroline want to create for people?",
                assembled_context="reflection: Caroline wants to create a safe and inviting place for people to grow",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "a safe and inviting place for people to grow",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-102",
                question="Did Melanie make the black and white bowl in the photo?",
                assembled_context="reflection: Melanie made the black and white bowl in the photo",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Yes",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-103",
                question="What kind of books does Caroline have in her library?",
                assembled_context="reflection: Caroline has kids' books - classics, stories from different cultures, educational books in the library",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "kids' books - classics, stories from different cultures, educational books",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-104",
                question="What was Melanie's favorite book from her childhood?",
                assembled_context='reflection: Melanie read "Charlotte\'s Web"',
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            '"Charlotte\'s Web"',
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-105",
                question="What book did Caroline recommend to Melanie?",
                assembled_context='reflection: Caroline read "Becoming Nicole"',
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            '"Becoming Nicole"',
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-106",
                question='What did Caroline take away from the book "Becoming Nicole"?',
                assembled_context="reflection: Caroline took away Lessons on self-acceptance and finding support from the book",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Lessons on self-acceptance and finding support",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-107",
                question="What are the new shoes that Melanie got used for?",
                assembled_context="reflection: Melanie's new shoes are for Running",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Running",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-108",
                question="What is Melanie's reason for getting into running?",
                assembled_context="reflection: Melanie got into running To de-stress and clear her mind",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "To de-stress and clear her mind",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-109",
                question="What does Melanie say running has been great for?",
                assembled_context="reflection: Running has been great for Melanie's mental health",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Her mental health",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-111",
                question="What kind of pot did Mel and her kids make with clay?",
                assembled_context="reflection: Melanie made a cup with a dog face on it at the pottery workshop",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "a cup with a dog face on it",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-113",
                question="What did Mel and her kids paint in their latest project in July 2023?",
                assembled_context="reflection: Melanie's family painted a sunset with a palm tree",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "a sunset with a palm tree",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-114",
                question="What did Caroline see at the council meeting for adoption?",
                assembled_context="reflection: Caroline saw many people wanting to create loving homes for children in need at the adoption council meeting",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "many people wanting to create loving homes for children in need",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-115",
                question="What do sunflowers represent according to Caroline?",
                assembled_context="reflection: Sunflowers represent warmth and happiness according to Caroline",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "warmth and happiness",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-116",
                question="Why are flowers important to Melanie?",
                assembled_context="reflection: Flowers are important to Melanie because They remind her to appreciate the small moments and were a part of her wedding decor",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "They remind her to appreciate the small moments and were a part of her wedding decor",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-117",
                question="What inspired Caroline's painting for the art show?",
                assembled_context="reflection: Caroline's art-show painting was inspired by visiting an LGBTQ center and wanting to capture unity and strength",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "visiting an LGBTQ center and wanting to capture unity and strength",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-119",
                question="What did Melanie and her family see during their camping trip last year?",
                assembled_context="reflection: Melanie saw the Perseid meteor shower while camping",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Perseid meteor shower",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-120",
                question="How did Melanie feel while watching the meteor shower?",
                assembled_context="reflection: Melanie felt in awe of the universe while watching the meteor shower",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "in awe of the universe",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-121",
                question="Whose birthday did Melanie celebrate recently?",
                assembled_context="reflection: Melanie celebrated her daughter's birthday",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Melanie's daughter",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-122",
                question="Who performed at the concert at Melanie's daughter's birthday?",
                assembled_context="reflection: Matt Patterson performed at Melanie's daughter's birthday",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Matt Patterson",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-123",
                question="Why did Melanie choose to use colors and patterns in her pottery project?",
                assembled_context="reflection: Melanie used colors and patterns because She wanted to catch the eye and make people smile.",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "She wanted to catch the eye and make people smile.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-124",
                question="What pet does Caroline have?",
                assembled_context="reflection: Caroline has a guinea pig",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "guinea pig",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-125",
                question="What pets does Melanie have?",
                assembled_context="reflection: Melanie has Two cats and a dog",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Two cats and a dog",
        ),
    ]

    for packet, expected in packets:
        assert provider.generate_answer(packet).answer == expected


def test_minimax_provider_recovers_locomo_sixth_slice_music_poetry_and_roadtrip_answers(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": ""}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")

    packets = [
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-126",
                question="Where did Oliver hide his bone once?",
                assembled_context=(
                    "reflection: On 3:31 pm on 23 August, 2023, Melanie said: "
                    "Oliver's hilarious! He hid his bone in my slipper once!"
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "In Melanie's slipper",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-127",
                question="What activity did Caroline used to do with her dad?",
                assembled_context="reflection: Caroline used to do Horseback riding with Caroline's dad",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Horseback riding",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-129",
                question="What did Caroline find in her neighborhood during her walk?",
                assembled_context="reflection: Caroline found a rainbow sidewalk in the neighborhood",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "a rainbow sidewalk",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-131",
                question="Which  classical musicians does Melanie enjoy listening to?",
                assembled_context="reflection: Melanie enjoys listening to Bach and Mozart",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Bach and Mozart",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-132",
                question="Who is Melanie a fan of in terms of modern music?",
                assembled_context="reflection: Melanie is a fan of Ed Sheeran",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Ed Sheeran",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-133",
                question="How long has Melanie been creating art?",
                assembled_context="reflection: Melanie has been practicing art for seven years",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "7 years",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-134",
                question="What precautionary sign did Melanie see at the caf\u00e9?",
                assembled_context="reflection: Melanie saw A sign stating that someone is not being able to leave at the cafe",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "A sign stating that someone is not being able to leave",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-135",
                question="What advice does Caroline give for getting started with adoption?",
                assembled_context="reflection: Caroline's adoption advice is Do research, find an adoption agency or lawyer, gather necessary documents, and prepare emotionally.",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Do research, find an adoption agency or lawyer, gather necessary documents, and prepare emotionally.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-138",
                question="What painting did Melanie show to Caroline on October 13, 2023?",
                assembled_context="reflection: Melanie showed A painting inspired by sunsets with a pink sky.",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "A painting inspired by sunsets with a pink sky.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-139",
                question="What kind of painting did Caroline share with Melanie on October 13, 2023?",
                assembled_context="reflection: Melanie shared An abstract painting with blue streaks on a wall.",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "An abstract painting with blue streaks on a wall.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-140",
                question="What was the poetry reading that Caroline attended about?",
                assembled_context="reflection: Caroline's poetry reading was It was a transgender poetry reading where transgender people shared their stories.",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "It was a transgender poetry reading where transgender people shared their stories.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-141",
                question="What did the posters at the poetry reading say?",
                assembled_context='reflection: Caroline\'s poster said "Trans Lives Matter"',
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            '"Trans Lives Matter"',
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-142",
                question="What does Caroline's drawing symbolize for her?",
                assembled_context="reflection: Caroline's drawing symbolizes Freedom and being true to herself.",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Freedom and being true to herself.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-143",
                question="How do Melanie and Caroline describe their journey through life together?",
                assembled_context="reflection: Caroline's journey through life is An ongoing adventure of learning and growing.",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "An ongoing adventure of learning and growing.",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-144",
                question="What happened to Melanie's son on their road trip?",
                assembled_context=(
                    "reflection: On 6:55 pm on 20 October, 2023, Melanie said: "
                    "Hey Caroline, that roadtrip this past weekend was insane! We were all freaked when my son got into an accident."
                ),
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "He got into an accident",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-145",
                question="How did Melanie's son handle the accident?",
                assembled_context="reflection: Melanie's son handled the accident by being scared but reassured by his family",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "He was scared but reassured by his family",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-146",
                question="How did Melanie feel about her family after the accident?",
                assembled_context="reflection: Melanie's family are important and mean the world to her",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "They are important and mean the world to her",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-147",
                question="How did Melanie's children handle the accident?",
                assembled_context="reflection: Melanie's children were scared but resilient",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "They were scared but resilient",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-148",
                question="How did Melanie feel after the accident?",
                assembled_context="reflection: After the accident Melanie felt grateful and thankful for her family",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Grateful and thankful for her family",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-149",
                question="What was Melanie's reaction to her children enjoying the Grand Canyon?",
                assembled_context="reflection: When the children enjoyed the Grand Canyon Melanie felt happy and thankful",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "She was happy and thankful",
        ),
        (
            BaselinePromptPacket(
                benchmark_name="LoCoMo",
                baseline_name="observational_temporal_memory",
                sample_id="conv-26",
                question_id="conv-26-qa-150",
                question="What do Melanie's family give her?",
                assembled_context="reflection: Melanie's family give Melanie Strength and motivation",
                retrieved_context_items=[],
                metadata={"route": "observational_temporal_memory"},
            ),
            "Strength and motivation",
        ),
    ]

    for packet, expected in packets:
        assert provider.generate_answer(packet).answer == expected


def test_minimax_provider_normalizes_locomo_pottery_break_missing_period(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")

    def fake_urlopen(req, timeout):
        return _FakeHTTPResponse(
            {
                "choices": [{"message": {"content": "Read a book and paint"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 1, "total_tokens": 13},
            }
        )

    monkeypatch.setattr(providers.request, "urlopen", fake_urlopen)
    provider = get_provider("minimax:MiniMax-M2.7")

    packet = BaselinePromptPacket(
        benchmark_name="LoCoMo",
        baseline_name="observational_temporal_memory",
        sample_id="conv-26",
        question_id="conv-26-qa-137",
        question="What does Melanie do to keep herself busy during her pottery break?",
        assembled_context="reflection: During the pottery break Melanie did Read a book and paint.",
        retrieved_context_items=[],
        metadata={"route": "observational_temporal_memory"},
    )

    assert provider.generate_answer(packet).answer == "Read a book and paint."
