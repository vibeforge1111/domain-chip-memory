from __future__ import annotations

import evaluate_chip


def test_io_protocol_accepts_canonical_spark_hook_contract(monkeypatch) -> None:
    monkeypatch.setattr(evaluate_chip, "_chip", lambda: {"io_protocol": "spark-hook-io.v1"})

    assert evaluate_chip.check_io_protocol() is True


def test_io_protocol_keeps_legacy_structured_manifest_compatibility(monkeypatch) -> None:
    monkeypatch.setattr(
        evaluate_chip,
        "_chip",
        lambda: {
            "io_protocol": {
                "input": "schemas/input.json",
                "output": "schemas/output.json",
                "schemas_dir": "schemas",
            }
        },
    )

    assert evaluate_chip.check_io_protocol() is True


def test_io_protocol_rejects_unknown_contract(monkeypatch) -> None:
    monkeypatch.setattr(evaluate_chip, "_chip", lambda: {"io_protocol": "unknown"})

    assert evaluate_chip.check_io_protocol() is False
