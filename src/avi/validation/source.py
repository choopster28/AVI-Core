from __future__ import annotations

from pathlib import Path

from avi.config import AviConfig
from avi.io import read_json, write_json


def validate_sleeper(config: AviConfig) -> dict:
    manifest = read_json(Path("data/raw/sleeper/manifest.json"))
    trades = read_json(
        Path("data/processed/trades/all_completed_trades.json")
    )

    failures: list[str] = []
    if len(trades) < config.minimum_completed_trades:
        failures.append("Completed-trade ledger is below the configured minimum.")

    seasons = manifest.get("seasons_discovered", [])
    if any(int(season) < config.earliest_supported_season for season in seasons):
        failures.append("A pre-2024 season was published.")

    latest = max(manifest.get("season_results", []), key=lambda row: row["season"])
    if latest["rosters"] != config.expected_team_count:
        failures.append("Current roster count does not equal 16.")
    if latest["users"] != config.expected_team_count:
        failures.append("Current user count does not equal 16.")

    result = {"status": "failed" if failures else "passed", "failures": failures}
    write_json(Path("data/processed/validation/sleeper.json"), result)
    if failures:
        raise RuntimeError(" | ".join(failures))
    return result


def validate_fantasypros() -> dict:
    manifest = read_json(Path("data/raw/fantasypros/manifest.json"))
    failures: list[str] = []

    required = [
        Path("data/raw/fantasypros/players.json"),
        Path("data/raw/fantasypros/injuries.json"),
        Path("data/raw/fantasypros/news.json"),
    ]
    required.extend(
        Path(f"data/raw/fantasypros/projections/{position}.json")
        for position in ("QB", "RB", "WR", "TE", "K")
    )

    for path in required:
        if not path.exists():
            failures.append(f"Missing {path}")

    if manifest.get("player_points", {}).get("preseason_weight") != 0.0:
        failures.append("Player-points preseason weight must be zero.")

    result = {"status": "failed" if failures else "passed", "failures": failures}
    write_json(Path("data/processed/validation/fantasypros.json"), result)
    if failures:
        raise RuntimeError(" | ".join(failures))
    return result
