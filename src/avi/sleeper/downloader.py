from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.config import AviConfig
from avi.sleeper.client import SleeperClient


RAW_DIRECTORY = Path("data/raw")


def save_json(path: Path, data: Any) -> None:
    """Save JSON safely without leaving a partially written file."""
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = path.with_suffix(path.suffix + ".tmp")

    with temporary_path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )

    temporary_path.replace(path)
    print(f"Saved: {path}")


def validate_collection(
    label: str,
    value: Any,
    minimum_count: int = 1,
) -> None:
    """Confirm Sleeper returned a list or dictionary."""
    if not isinstance(value, (list, dict)):
        raise RuntimeError(
            f"{label} returned unexpected type "
            f"{type(value).__name__}."
        )

    if len(value) < minimum_count:
        raise RuntimeError(
            f"{label} returned fewer than "
            f"{minimum_count} records."
        )


def download_sleeper_snapshot(
    config: AviConfig,
) -> dict[str, Any]:
    client = SleeperClient()

    downloaded_at = datetime.now(UTC)
    snapshot_id = downloaded_at.strftime(
        "%Y-%m-%dT%H-%M-%SZ"
    )

    print("=" * 50)
    print("AVI SLEEPER UPDATE")
    print("=" * 50)
    print(f"League ID: {config.league_id}")
    print(f"Season: {config.season}")
    print()

    league = client.get_league(config.league_id)
    users = client.get_users(config.league_id)
    rosters = client.get_rosters(config.league_id)
    traded_picks = client.get_traded_picks(
        config.league_id
    )
    drafts = client.get_drafts(config.league_id)

    validate_collection("League", league)
    validate_collection("Users", users)
    validate_collection("Rosters", rosters)
    validate_collection(
        "Traded picks",
        traded_picks,
        minimum_count=0,
    )
    validate_collection(
        "Drafts",
        drafts,
        minimum_count=0,
    )

    save_json(RAW_DIRECTORY / "league.json", league)
    save_json(RAW_DIRECTORY / "users.json", users)
    save_json(RAW_DIRECTORY / "rosters.json", rosters)
    save_json(
        RAW_DIRECTORY / "traded_picks.json",
        traded_picks,
    )
    save_json(RAW_DIRECTORY / "drafts.json", drafts)

    transactions_directory = (
        RAW_DIRECTORY / "transactions"
    )

    combined_transactions: list[
        dict[str, Any]
    ] = []

    print()
    print("Downloading transactions...")

    for week in range(
        config.transaction_start_week,
        config.transaction_end_week + 1,
    ):
        transactions = client.get_transactions(
            config.league_id,
            week,
        )

        validate_collection(
            f"Transactions for week {week}",
            transactions,
            minimum_count=0,
        )

        save_json(
            transactions_directory
            / f"week_{week:02d}.json",
            transactions,
        )

        for transaction in transactions:
            transaction_copy = dict(transaction)
            transaction_copy[
                "_avi_transaction_week"
            ] = week
            combined_transactions.append(
                transaction_copy
            )

    combined_transactions.sort(
        key=lambda transaction: (
            transaction.get("created", 0),
            transaction.get(
                "transaction_id",
                "",
            ),
        )
    )

    save_json(
        RAW_DIRECTORY / "transactions.json",
        combined_transactions,
    )

    print()
    print("Downloading NFL player directory...")

    nfl_players = client.get_nfl_players()

    validate_collection(
        "NFL players",
        nfl_players,
    )

    save_json(
        RAW_DIRECTORY / "nfl_players.json",
        nfl_players,
    )

    manifest = {
        "snapshot_id": snapshot_id,
        "downloaded_at_utc": (
            downloaded_at.isoformat()
        ),
        "league_id": config.league_id,
        "season": config.season,
        "transaction_week_range": {
            "start": (
                config.transaction_start_week
            ),
            "end": (
                config.transaction_end_week
            ),
        },
        "record_counts": {
            "users": len(users),
            "rosters": len(rosters),
            "traded_picks": len(
                traded_picks
            ),
            "drafts": len(drafts),
            "transactions": len(
                combined_transactions
            ),
            "nfl_players": len(nfl_players),
        },
        "status": "passed",
    }

    save_json(
        RAW_DIRECTORY / "manifest.json",
        manifest,
    )

    print()
    print("=" * 50)
    print("UPDATE COMPLETED SUCCESSFULLY")
    print("=" * 50)
    print(f"Snapshot: {snapshot_id}")
    print(
        "Transactions: "
        f"{len(combined_transactions)}"
    )
    print(f"NFL players: {len(nfl_players)}")

    return manifest