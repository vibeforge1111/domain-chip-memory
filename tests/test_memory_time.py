from datetime import datetime

from domain_chip_memory.memory_time import parse_observation_anchor


def test_parse_observation_anchor_handles_none_and_beam_public_date_format():
    assert parse_observation_anchor(None) is None
    assert parse_observation_anchor("") is None
    assert parse_observation_anchor("April-15-2024") == datetime(2024, 4, 15)


def test_parse_observation_anchor_handles_longmemeval_datetime_format():
    assert parse_observation_anchor("2023/01/15 (Sun) 00:27") == datetime(2023, 1, 15, 0, 27)
