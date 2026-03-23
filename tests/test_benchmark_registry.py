from domain_chip_memory.benchmark_registry import build_benchmark_scorecard, suggest_mutations


def test_scorecard_has_longmemeval_target():
    scorecard = build_benchmark_scorecard()
    names = [target["benchmark_name"] for target in scorecard["public_targets"]]
    assert "LongMemEval" in names
    assert "GoodAI LTM Benchmark" in names
    assert scorecard["coverage_summary"]["target_count"] >= 3
    assert scorecard["experimental_frontier_claims"]


def test_mutation_suggestions_are_bounded():
    suggestions = suggest_mutations()
    assert len(suggestions) >= 3
    assert all("mutation_id" in suggestion for suggestion in suggestions)
    assert all("benchmark" in suggestion for suggestion in suggestions)
