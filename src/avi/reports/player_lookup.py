from __future__ import annotations

from pathlib import Path
from typing import Any

from avi.io import read_json, write_json
from avi.league.loader import find_current_league_file
from avi.reports.team_profiles import slugify_team_name


AVI_PLAYERS_PATH = Path(
    "data/processed/avi/avi_players.json"
)

SLEEPER_PLAYERS_PATH = Path(
    "data/raw/sleeper/nfl_players.json"
)

TEAM_PROFILES_DIRECTORY = Path(
    "knowledge/teams"
)

MARKDOWN_OUTPUT_PATH = Path(
    "knowledge/03_AVI_Player_Current_Team_Lookup.md"
)

JSON_OUTPUT_PATH = Path(
    "data/processed/reports/player_lookup.json"
)

AVI_ELIGIBLE_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
}


def load_current_rosters_and_users() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    league_directory = (
        find_current_league_file().parent
    )

    rosters = read_json(
        league_directory / "rosters.json"
    )

    users = read_json(
        league_directory / "users.json"
    )

    if not isinstance(rosters, list):
        raise RuntimeError(
            "Current Sleeper rosters.json must contain a JSON list."
        )

    if not isinstance(users, list):
        raise RuntimeError(
            "Current Sleeper users.json must contain a JSON list."
        )

    return rosters, users


def load_avi_players() -> list[dict[str, Any]]:
    if not AVI_PLAYERS_PATH.exists():
        raise RuntimeError(
            "AVI player output is missing. "
            "Run calculate-avi first."
        )

    payload = read_json(
        AVI_PLAYERS_PATH
    )

    if not isinstance(payload, list):
        raise RuntimeError(
            "avi_players.json must contain a JSON list."
        )

    return [
        record
        for record in payload
        if isinstance(record, dict)
    ]


def load_sleeper_players() -> dict[str, dict[str, Any]]:
    if not SLEEPER_PLAYERS_PATH.exists():
        raise RuntimeError(
            "Sleeper NFL player directory is missing."
        )

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


def build_user_lookup(
    users: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(user["user_id"]): user
        for user in users
        if isinstance(user, dict)
        and user.get("user_id") is not None
    }


def build_team_filename(
    roster_id: int,
    team_name: str,
) -> str:
    return (
        f"{roster_id:02d}_"
        f"{slugify_team_name(team_name)}"
        ".md"
    )


def build_rostered_player_lookup(
    *,
    rosters: list[dict[str, Any]],
    users_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    for roster in rosters:
        if not isinstance(roster, dict):
            continue

        roster_id = int(
            roster.get("roster_id")
        )

        owner_id = str(
            roster.get("owner_id", "")
        )

        user = users_by_id.get(
            owner_id,
            {},
        )

        metadata = user.get(
            "metadata",
            {},
        )

        if not isinstance(metadata, dict):
            metadata = {}

        team_name = str(
            metadata.get("team_name")
            or user.get("display_name")
            or f"Roster {roster_id}"
        )

        team_file = build_team_filename(
            roster_id,
            team_name,
        )

        player_ids = roster.get(
            "players",
            [],
        )

        if not isinstance(player_ids, list):
            continue

        for player_id in player_ids:
            lookup[str(player_id)] = {
                "roster_id": roster_id,
                "owner_id": owner_id,
                "team_name": team_name,
                "team_file": team_file,
            }

    return lookup


def build_player_lookup() -> dict[str, Any]:
    rosters, users = (
        load_current_rosters_and_users()
    )

    avi_players = load_avi_players()
    sleeper_players = load_sleeper_players()

    users_by_id = build_user_lookup(
        users
    )

    rostered_lookup = (
        build_rostered_player_lookup(
            rosters=rosters,
            users_by_id=users_by_id,
        )
    )

    rostered_players: list[
        dict[str, Any]
    ] = []

    available_players: list[
        dict[str, Any]
    ] = []

    for avi_player in avi_players:
        source_ids = avi_player.get(
            "source_ids",
            {},
        )

        if not isinstance(source_ids, dict):
            continue

        sleeper_id = source_ids.get(
            "sleeper_id"
        )

        if sleeper_id is None:
            continue

        sleeper_id = str(sleeper_id)

        sleeper_record = sleeper_players.get(
            sleeper_id,
            {},
        )

        position = avi_player.get(
            "position"
        )

        if position not in AVI_ELIGIBLE_POSITIONS:
            continue

        record = {
            "avi_id": avi_player.get(
                "avi_id"
            ),
            "sleeper_id": sleeper_id,
            "player_name": avi_player.get(
                "canonical_name"
            ),
            "position": position,
            "nfl_team": avi_player.get(
                "nfl_team"
            ),
            "active": sleeper_record.get(
                "active"
            ),
            "status": sleeper_record.get(
                "status"
            ),
            "c_avi": avi_player.get(
                "c_avi"
            ),
            "d_avi": avi_player.get(
                "d_avi"
            ),
        }

        ownership = rostered_lookup.get(
            sleeper_id
        )

        if ownership is not None:
            rostered_players.append(
                {
                    **record,
                    **ownership,
                    "availability": (
                        "rostered"
                    ),
                }
            )
        else:
            available_players.append(
                {
                    **record,
                    "availability": (
                        "available"
                    ),
                }
            )

    rostered_players.sort(
        key=lambda record: (
            str(
                record.get(
                    "player_name",
                    "",
                )
            )
        )
    )

    available_players.sort(
        key=lambda record: (
            -float(
                record.get("c_avi")
                or 0.0
            ),
            str(
                record.get(
                    "player_name",
                    "",
                )
            ),
        )
    )

    payload = {
        "rostered_players": (
            rostered_players
        ),
        "available_players": (
            available_players
        ),
        "counts": {
            "rostered_players": len(
                rostered_players
            ),
            "available_players": len(
                available_players
            ),
        },
    }

    write_json(
        JSON_OUTPUT_PATH,
        payload,
    )

    lines = [
        "# AVI PLAYER TO TEAM LOOKUP",
        "",
        (
            "Retrieval purpose: identify whether a player is "
            "rostered or available. For rostered players, route "
            "questions to the authoritative current team file. "
            "For unrostered players, this file is the authoritative "
            "source for availability, C-AVI, and D-AVI."
        ),
        "",
        "## Rostered Players",
        "",
    ]

    for player in rostered_players:
        lines.extend(
            [
                (
                    "## PLAYER LOOKUP: "
                    f"{player['player_name']}"
                ),
                (
                    "- Player name: "
                    f"{player['player_name']}"
                ),
                (
                    "- Player ID: "
                    f"{player['sleeper_id']}"
                ),
                (
                    "- Position: "
                    f"{player['position']}"
                ),
                (
                    "- Current owner team: "
                    f"{player['team_name']}"
                ),
                (
                    "- Current owner roster ID: "
                    f"{player['roster_id']}"
                ),
                (
                    "- Team file: "
                    f"{player['team_file']}"
                ),
                "",
            ]
        )

    lines.extend(
        [
            "## Available Player Board",
            "",
        ]
    )

    for player in available_players:
        lines.extend(
            [
                (
                    "## AVAILABLE PLAYER: "
                    f"{player['player_name']}"
                ),
                (
                    "- Player name: "
                    f"{player['player_name']}"
                ),
                (
                    "- Player ID: "
                    f"{player['sleeper_id']}"
                ),
                (
                    "- Position: "
                    f"{player['position']}"
                ),
                (
                    "- NFL team: "
                    f"{player['nfl_team']}"
                ),
                (
                    "- Championship AVI "
                    "(C-AVI, 0-100): "
                    f"{player['c_avi']}"
                ),
                (
                    "- Dynasty AVI "
                    "(D-AVI, 0-100): "
                    f"{player['d_avi']}"
                ),
                (
                    "- Availability: available"
                ),
                "",
            ]
        )

    MARKDOWN_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MARKDOWN_OUTPUT_PATH.write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated: {MARKDOWN_OUTPUT_PATH}"
    )

    print(
        f"Saved: {JSON_OUTPUT_PATH}"
    )

    return payload