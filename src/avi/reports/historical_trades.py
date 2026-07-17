from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.io import read_json, write_json


SLEEPER_LEAGUES_ROOT = Path(
    "data/raw/sleeper/leagues"
)

SLEEPER_PLAYERS_PATH = Path(
    "data/raw/sleeper/nfl_players.json"
)

MARKDOWN_OUTPUT_PATH = Path(
    "knowledge/02_AVI_Historical_Trades.md"
)

JSON_OUTPUT_PATH = Path(
    "data/processed/reports/historical_trades.json"
)


def load_sleeper_players() -> dict[str, dict[str, Any]]:
    payload = read_json(
        SLEEPER_PLAYERS_PATH
    )

    if not isinstance(payload, dict):
        raise RuntimeError(
            "nfl_players.json must contain a JSON object."
        )

    return {
        str(player_id): record
        for player_id, record in payload.items()
        if isinstance(record, dict)
    }


def load_all_completed_trades() -> list[dict[str, Any]]:
    trades_by_id: dict[str, dict[str, Any]] = {}

    for path in sorted(
        SLEEPER_LEAGUES_ROOT.glob(
            "*/completed_trades.json"
        )
    ):
        payload = read_json(path)

        if not isinstance(payload, list):
            raise RuntimeError(
                f"{path} must contain a JSON list."
            )

        for trade in payload:
            if not isinstance(trade, dict):
                continue

            if trade.get("type") != "trade":
                continue

            if trade.get("status") != "complete":
                continue

            transaction_id = trade.get(
                "transaction_id"
            )

            if transaction_id is None:
                continue

            trades_by_id[str(transaction_id)] = trade

    trades = list(
        trades_by_id.values()
    )

    trades.sort(
        key=lambda trade: (
            int(
                trade.get(
                    "created",
                    0,
                )
            ),
            str(
                trade.get(
                    "transaction_id",
                    "",
                )
            ),
        )
    )

    return trades


def build_roster_and_owner_maps() -> tuple[
    dict[tuple[int, int], dict[str, Any]],
    dict[int, dict[str, Any]],
]:
    season_roster_map: dict[
        tuple[int, int],
        dict[str, Any],
    ] = {}

    latest_roster_map: dict[
        int,
        dict[str, Any],
    ] = {}

    for league_directory in sorted(
        SLEEPER_LEAGUES_ROOT.iterdir()
    ):
        if not league_directory.is_dir():
            continue

        league_path = (
            league_directory / "league.json"
        )
        rosters_path = (
            league_directory / "rosters.json"
        )
        users_path = (
            league_directory / "users.json"
        )

        if not (
            league_path.exists()
            and rosters_path.exists()
            and users_path.exists()
        ):
            continue

        league = read_json(
            league_path
        )

        rosters = read_json(
            rosters_path
        )

        users = read_json(
            users_path
        )

        if not isinstance(
            league,
            dict,
        ):
            continue

        if not isinstance(
            rosters,
            list,
        ):
            continue

        if not isinstance(
            users,
            list,
        ):
            continue

        season = int(
            league.get(
                "season",
                0,
            )
        )

        users_by_id = {
            str(user.get("user_id")): user
            for user in users
            if isinstance(user, dict)
            and user.get("user_id")
            is not None
        }

        for roster in rosters:
            if not isinstance(
                roster,
                dict,
            ):
                continue

            roster_id = int(
                roster.get(
                    "roster_id"
                )
            )

            owner_id = str(
                roster.get(
                    "owner_id",
                    "",
                )
            )

            user = users_by_id.get(
                owner_id,
                {},
            )

            metadata = user.get(
                "metadata",
                {},
            )

            if not isinstance(
                metadata,
                dict,
            ):
                metadata = {}

            team_name = str(
                metadata.get(
                    "team_name"
                )
                or user.get(
                    "display_name"
                )
                or f"Roster {roster_id}"
            )

            record = {
                "season": season,
                "roster_id": roster_id,
                "owner_id": owner_id,
                "owner_display_name": str(
                    user.get(
                        "display_name",
                        "Unknown Owner",
                    )
                ),
                "team_name": team_name,
            }

            season_roster_map[
                (
                    season,
                    roster_id,
                )
            ] = record

            previous = latest_roster_map.get(
                roster_id
            )

            if (
                previous is None
                or season
                >= int(
                    previous.get(
                        "season",
                        0,
                    )
                )
            ):
                latest_roster_map[
                    roster_id
                ] = record

    return (
        season_roster_map,
        latest_roster_map,
    )


def player_name(
    player_id: str,
    sleeper_players: dict[
        str,
        dict[str, Any],
    ],
) -> str:
    record = sleeper_players.get(
        str(player_id),
        {},
    )

    return str(
        record.get("full_name")
        or record.get(
            "search_full_name"
        )
        or " ".join(
            part
            for part in (
                record.get(
                    "first_name"
                ),
                record.get(
                    "last_name"
                ),
            )
            if part
        )
        or f"Player {player_id}"
    )


def datetime_from_ms(
    value: Any,
) -> datetime:
    try:
        milliseconds = int(value)
    except (
        TypeError,
        ValueError,
    ):
        milliseconds = 0

    return datetime.fromtimestamp(
        milliseconds / 1000,
        tz=UTC,
    )


def normalize_trade(
    *,
    trade: dict[str, Any],
    sleeper_players: dict[
        str,
        dict[str, Any],
    ],
    season_roster_map: dict[
        tuple[int, int],
        dict[str, Any],
    ],
) -> dict[str, Any]:
    season = int(
        trade.get(
            "_avi_season",
            0,
        )
    )

    roster_ids = [
        int(roster_id)
        for roster_id in (
            trade.get(
                "roster_ids",
                [],
            )
            or []
        )
    ]

    adds = trade.get(
        "adds",
        {},
    ) or {}

    drops = trade.get(
        "drops",
        {},
    ) or {}

    draft_picks = trade.get(
        "draft_picks",
        [],
    ) or []

    teams: dict[int, dict[str, Any]] = {}

    for roster_id in roster_ids:
        identity = season_roster_map.get(
            (
                season,
                roster_id,
            ),
            {
                "season": season,
                "roster_id": roster_id,
                "owner_id": "",
                "owner_display_name": (
                    "Unknown Owner"
                ),
                "team_name": (
                    f"Roster {roster_id}"
                ),
            },
        )

        teams[roster_id] = {
            **identity,
            "players_received": [],
            "players_sent": [],
            "picks_received": [],
            "picks_sent": [],
        }

    for raw_player_id, raw_roster_id in (
        adds.items()
    ):
        roster_id = int(
            raw_roster_id
        )

        teams.setdefault(
            roster_id,
            {
                "season": season,
                "roster_id": roster_id,
                "owner_id": "",
                "owner_display_name": (
                    "Unknown Owner"
                ),
                "team_name": (
                    f"Roster {roster_id}"
                ),
                "players_received": [],
                "players_sent": [],
                "picks_received": [],
                "picks_sent": [],
            },
        )

        teams[roster_id][
            "players_received"
        ].append(
            {
                "player_id": str(
                    raw_player_id
                ),
                "player_name": (
                    player_name(
                        str(
                            raw_player_id
                        ),
                        sleeper_players,
                    )
                ),
            }
        )

    for raw_player_id, raw_roster_id in (
        drops.items()
    ):
        roster_id = int(
            raw_roster_id
        )

        teams.setdefault(
            roster_id,
            {
                "season": season,
                "roster_id": roster_id,
                "owner_id": "",
                "owner_display_name": (
                    "Unknown Owner"
                ),
                "team_name": (
                    f"Roster {roster_id}"
                ),
                "players_received": [],
                "players_sent": [],
                "picks_received": [],
                "picks_sent": [],
            },
        )

        teams[roster_id][
            "players_sent"
        ].append(
            {
                "player_id": str(
                    raw_player_id
                ),
                "player_name": (
                    player_name(
                        str(
                            raw_player_id
                        ),
                        sleeper_players,
                    )
                ),
            }
        )

    for pick in draft_picks:
        if not isinstance(
            pick,
            dict,
        ):
            continue

        current_owner = int(
            pick.get(
                "owner_id"
            )
        )

        previous_owner = int(
            pick.get(
                "previous_owner_id"
            )
        )

        pick_record = {
            "season": str(
                pick.get(
                    "season"
                )
            ),
            "round": int(
                pick.get(
                    "round"
                )
            ),
            "original_roster_id": int(
                pick.get(
                    "roster_id"
                )
            ),
        }

        teams.setdefault(
            current_owner,
            {
                "season": season,
                "roster_id": current_owner,
                "owner_id": "",
                "owner_display_name": (
                    "Unknown Owner"
                ),
                "team_name": (
                    f"Roster {current_owner}"
                ),
                "players_received": [],
                "players_sent": [],
                "picks_received": [],
                "picks_sent": [],
            },
        )

        teams.setdefault(
            previous_owner,
            {
                "season": season,
                "roster_id": previous_owner,
                "owner_id": "",
                "owner_display_name": (
                    "Unknown Owner"
                ),
                "team_name": (
                    f"Roster {previous_owner}"
                ),
                "players_received": [],
                "players_sent": [],
                "picks_received": [],
                "picks_sent": [],
            },
        )

        teams[current_owner][
            "picks_received"
        ].append(
            pick_record
        )

        teams[previous_owner][
            "picks_sent"
        ].append(
            pick_record
        )

    timestamp = datetime_from_ms(
        trade.get(
            "created"
        )
    )

    return {
        "transaction_id": str(
            trade.get(
                "transaction_id"
            )
        ),
        "season": season,
        "week": int(
            trade.get(
                "_avi_transaction_week",
                0,
            )
        ),
        "created_at_utc": (
            timestamp.isoformat()
        ),
        "created_timestamp_ms": int(
            trade.get(
                "created",
                0,
            )
        ),
        "team_count": len(
            roster_ids
        ),
        "roster_ids": roster_ids,
        "teams": [
            teams[roster_id]
            for roster_id in sorted(
                teams
            )
        ],
    }


def format_pick(
    pick: dict[str, Any],
) -> str:
    return (
        f"{pick['season']} "
        f"Round {pick['round']} "
        f"(original roster "
        f"{pick['original_roster_id']})"
    )


def build_statistics(
    trades: list[dict[str, Any]],
    latest_roster_map: dict[
        int,
        dict[str, Any],
    ],
) -> dict[str, Any]:
    by_season = Counter(
        trade["season"]
        for trade in trades
    )

    team_stats: dict[
        int,
        dict[str, Any],
    ] = {}

    partner_counts: dict[
        int,
        Counter[int],
    ] = defaultdict(Counter)

    owner_participations = 0
    two_team_trades = 0
    three_team_trades = 0

    for trade in trades:
        team_count = int(
            trade["team_count"]
        )

        owner_participations += team_count

        if team_count == 2:
            two_team_trades += 1

        if team_count == 3:
            three_team_trades += 1

        roster_ids = [
            int(value)
            for value in (
                trade["roster_ids"]
            )
        ]

        for roster_id in roster_ids:
            identity = latest_roster_map.get(
                roster_id,
                {
                    "team_name": (
                        f"Roster {roster_id}"
                    ),
                    "owner_display_name": (
                        "Unknown Owner"
                    ),
                },
            )

            stats = team_stats.setdefault(
                roster_id,
                {
                    "roster_id": roster_id,
                    "team_name": (
                        identity[
                            "team_name"
                        ]
                    ),
                    "owner_display_name": (
                        identity[
                            "owner_display_name"
                        ]
                    ),
                    "total": 0,
                    "by_season": Counter(),
                    "players_in": 0,
                    "players_out": 0,
                    "picks_in": 0,
                    "picks_out": 0,
                    "firsts_in": 0,
                    "firsts_out": 0,
                },
            )

            stats["total"] += 1
            stats["by_season"][
                trade["season"]
            ] += 1

            team_entry = next(
                (
                    team
                    for team in trade["teams"]
                    if int(
                        team[
                            "roster_id"
                        ]
                    )
                    == roster_id
                ),
                None,
            )

            if team_entry is not None:
                stats["players_in"] += len(
                    team_entry[
                        "players_received"
                    ]
                )

                stats["players_out"] += len(
                    team_entry[
                        "players_sent"
                    ]
                )

                stats["picks_in"] += len(
                    team_entry[
                        "picks_received"
                    ]
                )

                stats["picks_out"] += len(
                    team_entry[
                        "picks_sent"
                    ]
                )

                stats["firsts_in"] += sum(
                    1
                    for pick in team_entry[
                        "picks_received"
                    ]
                    if int(
                        pick["round"]
                    )
                    == 1
                )

                stats["firsts_out"] += sum(
                    1
                    for pick in team_entry[
                        "picks_sent"
                    ]
                    if int(
                        pick["round"]
                    )
                    == 1
                )

            for partner_id in roster_ids:
                if partner_id == roster_id:
                    continue

                partner_counts[
                    roster_id
                ][
                    partner_id
                ] += 1

    team_rows = sorted(
        team_stats.values(),
        key=lambda row: (
            -int(row["total"]),
            str(row["team_name"]),
        ),
    )

    partner_rows: list[
        dict[str, Any]
    ] = []

    for roster_id, counts in (
        partner_counts.items()
    ):
        if not counts:
            continue

        max_count = max(
            counts.values()
        )

        partner_ids = sorted(
            partner_id
            for partner_id, count
            in counts.items()
            if count == max_count
        )

        partner_rows.append(
            {
                "roster_id": roster_id,
                "team_name": (
                    latest_roster_map.get(
                        roster_id,
                        {},
                    ).get(
                        "team_name",
                        f"Roster {roster_id}",
                    )
                ),
                "partner_count": max_count,
                "partners": [
                    latest_roster_map.get(
                        partner_id,
                        {},
                    ).get(
                        "team_name",
                        f"Roster {partner_id}",
                    )
                    for partner_id
                    in partner_ids
                ],
            }
        )

    partner_rows.sort(
        key=lambda row: str(
            row["team_name"]
        )
    )

    return {
        "unique_completed_trades": len(
            trades
        ),
        "owner_trade_participations": (
            owner_participations
        ),
        "two_team_trades": (
            two_team_trades
        ),
        "three_team_trades": (
            three_team_trades
        ),
        "trades_by_season": {
            str(season): count
            for season, count
            in sorted(
                by_season.items()
            )
        },
        "team_stats": team_rows,
        "partner_matrix": partner_rows,
    }


def render_markdown(
    *,
    trades: list[dict[str, Any]],
    statistics: dict[str, Any],
) -> str:
    earliest = (
        trades[0][
            "created_at_utc"
        ]
        if trades
        else "None"
    )

    latest = (
        trades[-1][
            "created_at_utc"
        ]
        if trades
        else "None"
    )

    lines = [
        "# AVI HISTORICAL TRADES",
        "",
        "## Data Authority and Retrieval Purpose",
        "",
        (
            "- This file is the authoritative Autobots League "
            "historical trade ledger and manager-tendency source."
        ),
        (
            "- Coverage includes every verified completed trade "
            "supplied for the 2024, 2025, and 2026 league seasons."
        ),
        (
            "- Historical trades are used for league history, "
            "owner activity, trade-partner analysis, asset-flow "
            "analysis, and manager tendencies."
        ),
        (
            "- Never use this file to determine current player "
            "ownership, current draft-pick ownership, or current "
            "AVI values."
        ),
        "",
        "## Permanent Preservation and Daily Update Policy",
        "",
        (
            "- Preserve every existing verified transaction "
            "permanently."
        ),
        (
            "- Append only completed trades whose transaction_id "
            "is not already present."
        ),
        (
            "- Deduplicate exclusively by transaction_id."
        ),
        (
            "- Exclude waivers, free-agent moves, commissioner "
            "moves, failed transactions, and non-trade activity."
        ),
        (
            "- Recalculate all statistics and manager profiles "
            "from the complete ledger after every update."
        ),
        "",
        "## Archive Integrity Summary",
        "",
        (
            "- Unique completed trades: "
            f"**{statistics['unique_completed_trades']}**"
        ),
        (
            "- Owner trade participations: "
            f"**{statistics['owner_trade_participations']}**"
        ),
        (
            "- Two-team trades: "
            f"**{statistics['two_team_trades']}**"
        ),
        (
            "- Three-team trades: "
            f"**{statistics['three_team_trades']}**"
        ),
    ]

    for season, count in (
        statistics[
            "trades_by_season"
        ].items()
    ):
        lines.append(
            f"- {season} completed trades: "
            f"**{count}**"
        )

    lines.extend(
        [
            (
                "- Earliest verified trade: "
                f"**{earliest}**"
            ),
            (
                "- Latest verified trade: "
                f"**{latest}**"
            ),
            "",
            "## Trades by Owner",
            "",
            (
                "| Rank | Team | Owner | Total | 2024 | 2025 | "
                "2026 | Players In | Players Out | Picks In | "
                "Picks Out | 1sts In | 1sts Out |"
            ),
            (
                "|---:|---|---|---:|---:|---:|---:|---:|---:|"
                "---:|---:|---:|---:|"
            ),
        ]
    )

    for rank, row in enumerate(
        statistics[
            "team_stats"
        ],
        start=1,
    ):
        by_season = row[
            "by_season"
        ]

        lines.append(
            "| "
            f"{rank} | "
            f"{row['team_name']} | "
            f"{row['owner_display_name']} | "
            f"**{row['total']}** | "
            f"{by_season.get(2024, 0)} | "
            f"{by_season.get(2025, 0)} | "
            f"{by_season.get(2026, 0)} | "
            f"{row['players_in']} | "
            f"{row['players_out']} | "
            f"{row['picks_in']} | "
            f"{row['picks_out']} | "
            f"{row['firsts_in']} | "
            f"{row['firsts_out']} |"
        )

    lines.extend(
        [
            "",
            "## Trade-Partner Matrix",
            "",
            (
                "| Team | Most Frequent Partner(s) | "
                "Completed Trades |"
            ),
            "|---|---|---:|",
        ]
    )

    for row in statistics[
        "partner_matrix"
    ]:
        lines.append(
            "| "
            f"{row['team_name']} | "
            f"{', '.join(row['partners'])} | "
            f"{row['partner_count']} |"
        )

    lines.extend(
        [
            "",
            "## Complete Trade Ledger",
            "",
        ]
    )

    for trade in reversed(
        trades
    ):
        lines.extend(
            [
                (
                    "### TRADE: "
                    f"{trade['transaction_id']}"
                ),
                (
                    "- Season: "
                    f"{trade['season']}"
                ),
                (
                    "- Week: "
                    f"{trade['week']}"
                ),
                (
                    "- Created at UTC: "
                    f"{trade['created_at_utc']}"
                ),
                (
                    "- Teams involved: "
                    f"{trade['team_count']}"
                ),
                "",
            ]
        )

        for team in trade["teams"]:
            lines.append(
                (
                    "#### "
                    f"{team['team_name']} "
                    f"({team['owner_display_name']})"
                )
            )

            players_received = [
                player["player_name"]
                for player in team[
                    "players_received"
                ]
            ]

            players_sent = [
                player["player_name"]
                for player in team[
                    "players_sent"
                ]
            ]

            picks_received = [
                format_pick(pick)
                for pick in team[
                    "picks_received"
                ]
            ]

            picks_sent = [
                format_pick(pick)
                for pick in team[
                    "picks_sent"
                ]
            ]

            lines.extend(
                [
                    (
                        "- Players received: "
                        + (
                            ", ".join(
                                players_received
                            )
                            if players_received
                            else "None"
                        )
                    ),
                    (
                        "- Players sent: "
                        + (
                            ", ".join(
                                players_sent
                            )
                            if players_sent
                            else "None"
                        )
                    ),
                    (
                        "- Picks received: "
                        + (
                            ", ".join(
                                picks_received
                            )
                            if picks_received
                            else "None"
                        )
                    ),
                    (
                        "- Picks sent: "
                        + (
                            ", ".join(
                                picks_sent
                            )
                            if picks_sent
                            else "None"
                        )
                    ),
                    "",
                ]
            )

    return "\n".join(
        lines
    ).rstrip() + "\n"


def build_historical_trades() -> dict[str, Any]:
    sleeper_players = (
        load_sleeper_players()
    )

    raw_trades = (
        load_all_completed_trades()
    )

    (
        season_roster_map,
        latest_roster_map,
    ) = build_roster_and_owner_maps()

    trades = [
        normalize_trade(
            trade=trade,
            sleeper_players=(
                sleeper_players
            ),
            season_roster_map=(
                season_roster_map
            ),
        )
        for trade in raw_trades
    ]

    statistics = build_statistics(
        trades,
        latest_roster_map,
    )

    payload = {
        "generated_at_utc": (
            datetime.now(
                UTC
            ).isoformat()
        ),
        "statistics": statistics,
        "trades": trades,
    }

    write_json(
        JSON_OUTPUT_PATH,
        payload,
    )

    MARKDOWN_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MARKDOWN_OUTPUT_PATH.write_text(
        render_markdown(
            trades=trades,
            statistics=statistics,
        ),
        encoding="utf-8",
    )

    print(
        f"Generated: "
        f"{MARKDOWN_OUTPUT_PATH}"
    )

    print(
        f"Historical trades: "
        f"{len(trades)}"
    )

    return payload