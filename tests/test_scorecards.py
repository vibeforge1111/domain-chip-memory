from domain_chip_memory.baselines import build_full_context_packets, build_lexical_packets
from domain_chip_memory.canonical_configs import get_canonical_configs
from domain_chip_memory.responders import heuristic_response
from domain_chip_memory.sample_data import demo_samples
from domain_chip_memory.scorecards import (
    build_scorecard,
    build_scorecard_contract_summary,
    run_baseline_predictions,
)


def test_demo_scorecards_run_end_to_end():
    samples = demo_samples()

    full_manifest, full_packets = build_full_context_packets(samples)
    full_predictions = run_baseline_predictions(
        samples,
        full_packets,
        responder_name="heuristic_v1",
        responder=heuristic_response,
    )
    full_scorecard = build_scorecard(full_manifest, full_predictions)

    lexical_manifest, lexical_packets = build_lexical_packets(samples, top_k_sessions=1)
    lexical_predictions = run_baseline_predictions(
        samples,
        lexical_packets,
        responder_name="heuristic_v1",
        responder=heuristic_response,
    )
    lexical_scorecard = build_scorecard(lexical_manifest, lexical_predictions)

    assert full_scorecard["overall"]["total"] == 2
    assert lexical_scorecard["overall"]["total"] == 2
    assert full_scorecard["overall"]["accuracy"] >= 0.5
    assert lexical_scorecard["overall"]["accuracy"] >= 0.5


def test_scorecard_contract_and_canonical_config_exist():
    summary = build_scorecard_contract_summary()
    configs = get_canonical_configs()

    assert summary["scorecard_fields"]
    assert configs
    assert configs[0]["config_id"] == "benchmark-v3-32k.yml"
