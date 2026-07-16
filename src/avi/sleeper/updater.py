from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.config import AviConfig
from avi.io import write_json
from avi.sleeper.client import SleeperClient
from avi.sleeper.history import discover
from avi.trades.ledger import completed_trade_ledger

RAW = Path("data/raw/sleeper")
PROCESSED = Path("data/processed")


def update(config: AviConfig) -> dict[str, Any]:
    if not config.sleeper_league_id:
        raise RuntimeError("SLEEPER_LEAGUE_ID is not set.")

    client = SleeperClient()
    seasons = discover(
        client,
        config.sleeper_league_id,
        config.earliest_supported_season,
    )
    print("Discovered seasons:", ", ".join(str(row.season) for row in seasons))

    all_transactions: list[dict[str, Any]] = []
    season_results: list[dict[str, Any]] = []

    for row in seasons:
        folder = RAW / "leagues" / f"{row.season}_{row.league_id}"
        users = client.users(row.league_id)
        rosters = client.rosters(row.league_id)
        picks = client.traded_picks(row.league_id)
        drafts = client.drafts(row.league_id)

        write_json(folder / "league.json", row.league_data)
        write_json(folder / "users.json", users)
        write_json(folder / "rosters.json", rosters)
        write_json(folder / "traded_picks.json", picks)
        write_json(folder / "drafts.json", drafts)

        season_transactions: list[dict[str, Any]] = []
        for week in range(
            config.transaction_start_week,
            config.transaction_end_week + 1,
        ):
            weekly = client.transactions(row.league_id, week)
            enriched: list[dict[str, Any]] = []
            for tx in weekly:
                item = dict(tx)
                item["_avi_season"] = row.season
                item["_avi_league_id"] = row.league_id
                item["_avi_transaction_week"] = week
                enriched.append(item)
                season_transactions.append(item)
                all_transactions.append(item)
            write_json(folder / "transactions" / f"week_{week:02d}.json", enriched)

        trades = completed_trade_ledger(season_transactions)
        write_json(folder / "transactions.json", season_transactions)
        write_json(folder / "completed_trades.json", trades)

        season_results.append(
            {
                "season": row.season,
                "league_id": row.league_id,
                "users": len(users),
                "rosters": len(rosters),
                "transactions": len(season_transactions),
                "completed_trades": len(trades),
            }
        )

    ledger = completed_trade_ledger(all_transactions)
    if len(ledger) < config.minimum_completed_trades:
        raise RuntimeError(
            f"Trade ledger has {len(ledger)} completed trades; "
            f"minimum is {config.minimum_completed_trades}."
        )

    write_json(PROCESSED / "transactions" / "all_transactions.json", all_transactions)
    write_json(PROCESSED / "trades" / "all_completed_trades.json", ledger)

    players = client.nfl_players()
    write_json(RAW / "nfl_players.json", players)

    now = datetime.now(UTC)
    manifest = {
        "snapshot_id": now.strftime("%Y-%m-%dT%H-%M-%SZ"),
        "downloaded_at_utc": now.isoformat(),
        "seasons_discovered": [row.season for row in seasons],
        "season_results": season_results,
        "record_counts": {
            "completed_trades": len(ledger),
            "nfl_players": len(players),
        },
        "status": "passed",
    }
    write_json(RAW / "manifest.json", manifest)
    return manifest
