from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.config import AviConfig
from avi.io import write_json
from avi.sleeper.client import SleeperClient
from avi.sleeper.history import discover_league_history
from avi.trades.ledger import build_completed_trade_ledger


RAW_ROOT = Path("data/raw/sleeper")
PROCESSED_ROOT = Path("data/processed")


def _validate_collection(label: str, value: Any, minimum: int = 0) -> None:
    if not isinstance(value, (list, dict)):
        raise RuntimeError(f"{label} returned {type(value).__name__}.")
    if len(value) < minimum:
        raise RuntimeError(f"{label} returned fewer than {minimum} records.")


def update_sleeper(config: AviConfig) -> dict[str, Any]:
    if not config.sleeper_league_id:
        raise RuntimeError("SLEEPER_LEAGUE_ID is not set.")

    client = SleeperClient()
    downloaded_at = datetime.now(UTC)
    history = discover_league_history(
        client=client,
        current_league_id=config.sleeper_league_id,
        earliest_supported_season=config.earliest_supported_season,
    )

    print(
        "Discovered league seasons: "
        + ", ".join(str(item.season) for item in history)
    )

    all_transactions: list[dict[str, Any]] = []
    season_results: list[dict[str, Any]] = []

    for item in history:
        season_dir = RAW_ROOT / "leagues" / f"{item.season}_{item.league_id}"
        users = client.get_users(item.league_id)
        rosters = client.get_rosters(item.league_id)
        traded_picks = client.get_traded_picks(item.league_id)
        drafts = client.get_drafts(item.league_id)

        _validate_collection("users", users, 1)
        _validate_collection("rosters", rosters, 1)
        _validate_collection("traded picks", traded_picks)
        _validate_collection("drafts", drafts)

        write_json(season_dir / "league.json", item.league_data)
        write_json(season_dir / "users.json", users)
        write_json(season_dir / "rosters.json", rosters)
        write_json(season_dir / "traded_picks.json", traded_picks)
        write_json(season_dir / "drafts.json", drafts)

        season_transactions: list[dict[str, Any]] = []
        for week in range(
            config.transaction_start_week,
            config.transaction_end_week + 1,
        ):
            weekly = client.get_transactions(item.league_id, week)
            _validate_collection(f"{item.season} week {week} transactions", weekly)

            enriched_week: list[dict[str, Any]] = []
            for transaction in weekly:
                enriched = dict(transaction)
                enriched["_avi_season"] = item.season
                enriched["_avi_league_id"] = item.league_id
                enriched["_avi_transaction_week"] = week
                enriched_week.append(enriched)
                season_transactions.append(enriched)
                all_transactions.append(enriched)

            write_json(
                season_dir / "transactions" / f"week_{week:02d}.json",
                enriched_week,
            )

        season_transactions.sort(
            key=lambda tx: (tx.get("created", 0), tx.get("transaction_id", ""))
        )
        season_trades = build_completed_trade_ledger(season_transactions)

        write_json(season_dir / "transactions.json", season_transactions)
        write_json(season_dir / "completed_trades.json", season_trades)

        season_results.append(
            {
                "season": item.season,
                "league_id": item.league_id,
                "previous_league_id": item.previous_league_id,
                "users": len(users),
                "rosters": len(rosters),
                "traded_picks": len(traded_picks),
                "drafts": len(drafts),
                "transactions": len(season_transactions),
                "completed_trades": len(season_trades),
            }
        )

    all_transactions.sort(
        key=lambda tx: (tx.get("created", 0), tx.get("transaction_id", ""))
    )
    all_trades = build_completed_trade_ledger(all_transactions)

    if len(all_trades) < config.minimum_completed_trades:
        raise RuntimeError(
            f"Completed-trade ledger contains {len(all_trades)} trades, below the "
            f"configured minimum of {config.minimum_completed_trades}."
        )

    write_json(
        PROCESSED_ROOT / "transactions" / "all_transactions.json",
        all_transactions,
    )
    write_json(
        PROCESSED_ROOT / "trades" / "all_completed_trades.json",
        all_trades,
    )

    players = client.get_nfl_players()
    _validate_collection("NFL players", players, 1)
    write_json(RAW_ROOT / "nfl_players.json", players)

    manifest = {
        "snapshot_id": downloaded_at.strftime("%Y-%m-%dT%H-%M-%SZ"),
        "downloaded_at_utc": downloaded_at.isoformat(),
        "current_league_id": config.sleeper_league_id,
        "earliest_supported_season": config.earliest_supported_season,
        "seasons_discovered": [item.season for item in history],
        "season_results": season_results,
        "record_counts": {
            "league_seasons": len(history),
            "all_transactions": len(all_transactions),
            "completed_trades": len(all_trades),
            "nfl_players": len(players),
        },
        "status": "passed",
    }
    write_json(RAW_ROOT / "manifest.json", manifest)

    print(f"Transactions: {len(all_transactions)}")
    print(f"Completed trades: {len(all_trades)}")
    return manifest
