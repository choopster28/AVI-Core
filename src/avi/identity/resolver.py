from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PlayerIdentityMatch:
    sleeper_id: str
    fantasypros_id: str
    player_name: str
    position: str | None
    nfl_team: str | None
    match_method: str
    confidence: str


def normalize_name(value: str) -> str:
    """
    Normalize a player name for deterministic comparison.

    Examples:
        "A.J. Brown" -> "aj brown"
        "D'Andre Swift" -> "dandre swift"
        "Marvin Harrison Jr." -> "marvin harrison"
    """
    normalized = unicodedata.normalize(
        "NFKD",
        value,
    )

    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )

    normalized = normalized.lower()

    normalized = re.sub(
        r"\b(jr|sr|ii|iii|iv|v)\b\.?",
        "",
        normalized,
    )

    normalized = re.sub(
        r"[^a-z0-9]+",
        " ",
        normalized,
    )

    return " ".join(
        normalized.split()
    )


def normalize_team(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().upper()

    if not text:
        return None

    aliases = {
        "JAX": "JAC",
        "WSH": "WAS",
        "LA": "LAR",
        "LV": "LVR",
    }

    return aliases.get(
        text,
        text,
    )


def normalize_position(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().upper()

    if not text:
        return None

    aliases = {
        "DE": "DL",
        "DT": "DL",
        "CB": "DB",
        "S": "DB",
        "FS": "DB",
        "SS": "DB",
    }

    return aliases.get(
        text,
        text,
    )


def extract_sleeper_players(
    sleeper_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    players: list[dict[str, Any]] = []

    for sleeper_id, record in sleeper_payload.items():
        if not isinstance(record, dict):
            continue

        full_name = (
            record.get("full_name")
            or record.get("search_full_name")
            or " ".join(
                part
                for part in (
                    record.get("first_name"),
                    record.get("last_name"),
                )
                if part
            )
        )

        if not full_name:
            continue

        players.append(
            {
                "sleeper_id": str(sleeper_id),
                "name": str(full_name),
                "normalized_name": normalize_name(
                    str(full_name)
                ),
                "position": normalize_position(
                    record.get("position")
                ),
                "team": normalize_team(
                    record.get("team")
                ),
                "active": record.get("active"),
                "raw": record,
            }
        )

    return players


def extract_fantasypros_players(
    fantasypros_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_players = fantasypros_payload.get(
        "players",
        [],
    )

    if not isinstance(raw_players, list):
        raise RuntimeError(
            "FantasyPros players payload does not contain "
            "a players list."
        )

    players: list[dict[str, Any]] = []

    for record in raw_players:
        if not isinstance(record, dict):
            continue

        player_id = record.get("player_id")
        name = record.get("player_name")

        if player_id is None or not name:
            continue

        position = (
            record.get("position_id")
            or (
                record.get("positions", [None])[0]
                if isinstance(
                    record.get("positions"),
                    list,
                )
                and record.get("positions")
                else None
            )
        )

        normalized_position = normalize_position(
            position
        )

        # Autobots does not use Team Defense (DST).
        # Ignore them entirely so they never enter the
        # identity registry or AVI calculations.
        if normalized_position == "DST":
            continue

        players.append(
            {
                "fantasypros_id": str(player_id),
                "nfl_id": (
                    str(record.get("nfl_id"))
                    if record.get("nfl_id")
                    is not None
                    else None
                ),
                "name": str(name),
                "normalized_name": normalize_name(
                    str(name)
                ),
                "position": normalized_position,
                "team": normalize_team(
                    record.get("team_id")
                ),
                "external_ids": {
                    "nfl_id": record.get(
                        "nfl_id"
                    ),
                    "sportsdata_player_id": (
                        record.get(
                            "sportsdata_player_id"
                        )
                    ),
                },
                "raw": record,
            }
        )

    return players


def build_identity_matches(
    sleeper_players: list[dict[str, Any]],
    fantasypros_players: list[dict[str, Any]],
) -> tuple[
    list[PlayerIdentityMatch],
    list[dict[str, Any]],
]:
    """
    Match FantasyPros players to Sleeper players.

    Matching order:
    1. exact normalized name + position + NFL team
    2. exact normalized name + position
    3. unresolved

    Ambiguous matches are never guessed.
    """
    sleeper_by_name: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for player in sleeper_players:
        sleeper_by_name.setdefault(
            player["normalized_name"],
            [],
        ).append(player)

    matches: list[PlayerIdentityMatch] = []
    unresolved: list[dict[str, Any]] = []

    for fantasypros_player in fantasypros_players:
        candidates = sleeper_by_name.get(
            fantasypros_player[
                "normalized_name"
            ],
            [],
        )

        exact_team_position = [
            candidate
            for candidate in candidates
            if candidate["position"]
            == fantasypros_player["position"]
            and candidate["team"]
            == fantasypros_player["team"]
        ]

        if len(exact_team_position) == 1:
            candidate = exact_team_position[0]

            matches.append(
                PlayerIdentityMatch(
                    sleeper_id=(
                        candidate["sleeper_id"]
                    ),
                    fantasypros_id=(
                        fantasypros_player[
                            "fantasypros_id"
                        ]
                    ),
                    player_name=(
                        fantasypros_player["name"]
                    ),
                    position=(
                        fantasypros_player[
                            "position"
                        ]
                    ),
                    nfl_team=(
                        fantasypros_player["team"]
                    ),
                    match_method=(
                        "exact_name_position_unique"
                    ),
                    confidence="verified",
                )
            )
            continue

        exact_position = [
            candidate
            for candidate in candidates
            if candidate["position"]
            == fantasypros_player["position"]
        ]

        if len(exact_position) == 1:
            candidate = exact_position[0]

            matches.append(
                PlayerIdentityMatch(
                    sleeper_id=(
                        candidate["sleeper_id"]
                    ),
                    fantasypros_id=(
                        fantasypros_player[
                            "fantasypros_id"
                        ]
                    ),
                    player_name=(
                        fantasypros_player["name"]
                    ),
                    position=(
                        fantasypros_player[
                            "position"
                        ]
                    ),
                    nfl_team=(
                        fantasypros_player["team"]
                    ),
                    match_method=(
                        "exact_name_position"
                    ),
                    confidence="review",
                )
            )
            continue

        unresolved.append(
            {
                "fantasypros_id": (
                    fantasypros_player[
                        "fantasypros_id"
                    ]
                ),
                "name": fantasypros_player[
                    "name"
                ],
                "normalized_name": (
                    fantasypros_player[
                        "normalized_name"
                    ]
                ),
                "position": (
                    fantasypros_player[
                        "position"
                    ]
                ),
                "team": fantasypros_player[
                    "team"
                ],
                "candidate_count": len(
                    candidates
                ),
                "candidates": [
                    {
                        "sleeper_id": candidate[
                            "sleeper_id"
                        ],
                        "name": candidate["name"],
                        "position": candidate[
                            "position"
                        ],
                        "team": candidate["team"],
                    }
                    for candidate in candidates
                ],
            }
        )

    return matches, unresolved