from pathlib import Path

from domain_chip_memory.env import load_dotenv


def test_load_dotenv_reads_key_values(tmp_path: Path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "MINIMAX_API_KEY=test-key",
                'MINIMAX_MODEL="MiniMax-M1"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("MINIMAX_MODEL", raising=False)

    loaded = load_dotenv(env_file)

    assert loaded["MINIMAX_API_KEY"] == "test-key"
    assert loaded["MINIMAX_MODEL"] == "MiniMax-M1"
