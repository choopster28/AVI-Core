from __future__ import annotations

from pathlib import Path
from typing import Any

from avi.config import AviConfig
from avi.io import read_json, write_json


RAW_ROOT = Path("data/raw/sleeper")
PROCESSED_ROOT = Path("data/processed")


def validate_sleeper_outputs(config: AviConfig) -> dict[str, Any]:
    manifest_path = RAW_ROOT / "manifest.json"
    trades_path = PROCESSED_ROOT / "trades" / "all_completed_trades.json"

    if not manifest_path.exists():
        raise RuntimeError("Sleeper manifest does not exist.")
    if not trades_path.exists():
        raise RuntimeError("Completed-trade ledger does not exist.")

    manifest = read_json(manifest_path)
    trades = read_json(trades_path)

    failures: list[str] = []

    seasons = manifest.get("seasons_discovered", [])
    if not seasons:
        failures.append("No Sleeper seasons were discovered.")
    if any(int(season) < config.earliest_supported_season for season in seasons):
        failures.append("A season before the configured earliest season was published.")

    current_results = manifest.get("season_results", [])
    if not current_results:
        failures.append("No per-season results exist.")
    else:
        newest = max(current_results, key=lambda row: int(row["season"]))
        if newest.get("rosters") != config.expected_team_count:
            failures.append(
                f"Current roster count is {newest.get('rosters')}; "
                f"expected {config.expected_team_count}."
            )
        if newest.get("users") != config.expected_team_count:
            failures.append(
                f"Current user count is {newest.get('users')}; "
                f"expected {config.expected_team_count}."
            )

    transaction_ids = [
        str(item.get("transaction_id", "")).strip() for item in trades
    ]
    if any(not value for value in transaction_ids):
        failures.append("At least one completed trade lacks transaction_id.")
    if len(transaction_ids) != len(set(transaction_ids)):
        failures.append("Duplicate completed-trade transaction IDs exist.")
    if len(trades) < config.minimum_completed_trades:
        failures.append(
            f"Trade count {len(trades)} is below minimum "
            f"{config.minimum_completed_trades}."
        )

    result = {
        "status": "failed" if failures else "passed",
        "failures": failures,
        "checks": {
            "seasons": seasons,
            "completed_trades": len(trades),
            "expected_team_count": config.expected_team_count,
        },
    }
    write_json(
        PROCESSED_ROOT / "validation" / "sleeper_validation.json",
        result,
    )

    if failures:
        raise RuntimeError("Sleeper validation failed: " + " | ".join(failures))

    print("Sleeper validation passed.")
    return result
