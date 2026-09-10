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
    """Normalize a player name for deterministic comparison."""
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = normalized.lower()
    normalized = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


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
    return aliases.get(text, text)


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
    return aliases.get(text, text)


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
                for part in (record.get("first_name"), record.get("last_name"))
                if part
            )
        )
        if not full_name:
            continue
        players.append(
            {
                "sleeper_id": str(sleeper_id),
                "name": str(full_name),
                "normalized_name": normalize_name(str(full_name)),
                "position": normalize_position(record.get("position")),
                "team": normalize_team(record.get("team")),
                "active": record.get("active"),
                "raw": record,
            }
        )
    return players


def extract_fantasypros_players(
    fantasypros_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    raw_players = fantasypros_payload.get("players", [])
    if not isinstance(raw_players, list):
        raise RuntimeError(
            "FantasyPros players payload does not contain a players list."
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
                if isinstance(record.get("positions"), list)
                and record.get("positions")
                else None
            )
        )
        normalized_position = normalize_position(position)
        if normalized_position == "DST":
            continue
        players.append(
            {
                "fantasypros_id": str(player_id),
                "nfl_id": (
                    str(record.get("nfl_id"))
                    if record.get("nfl_id") is not None
                    else None
                ),
                "name": str(name),
                "normalized_name": normalize_name(str(name)),
                "position": normalized_position,
                "team": normalize_team(record.get("team_id")),
                "external_ids": {
                    "nfl_id": record.get("nfl_id"),
                    "sportsdata_player_id": record.get("sportsdata_player_id"),
                },
                "raw": record,
            }
        )
    return players


def _unresolved_record(
    player: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "fantasypros_id": player["fantasypros_id"],
        "name": player["name"],
        "normalized_name": player["normalized_name"],
        "position": player["position"],
        "team": player["team"],
        "candidate_count": len(candidates),
        "candidates": [
            {
                "sleeper_id": candidate["sleeper_id"],
                "name": candidate["name"],
                "position": candidate["position"],
                "team": candidate["team"],
            }
            for candidate in candidates
        ],
    }
    if reason:
        record["reason"] = reason
    return record


def build_identity_matches(
    sleeper_players: list[dict[str, Any]],
    fantasypros_players: list[dict[str, Any]],
) -> tuple[list[PlayerIdentityMatch], list[dict[str, Any]]]:
    """
    Match FantasyPros players to Sleeper players with a strict one-to-one join.

    Matching priority:
    1. exact normalized name + position + NFL team (verified)
    2. exact normalized name + position (review)
    3. unresolved

    FantasyPros can occasionally publish duplicate/stale records for the same
    human. Those records used to map to the same Sleeper ID and then create a
    duplicate AVI ID, aborting the daily pipeline. We now arbitrate globally:
    a unique verified team match beats a weaker name/position match. If two
    source records are equally strong, neither is guessed; they remain
    unresolved for review. A Sleeper player can therefore appear at most once
    in the canonical registry.
    """
    sleeper_by_name: dict[str, list[dict[str, Any]]] = {}
    sleeper_by_id = {player["sleeper_id"]: player for player in sleeper_players}
    for player in sleeper_players:
        sleeper_by_name.setdefault(player["normalized_name"], []).append(player)

    provisional: list[tuple[int, PlayerIdentityMatch, dict[str, Any], list[dict[str, Any]]]] = []
    unresolved: list[dict[str, Any]] = []

    for fantasypros_player in fantasypros_players:
        candidates = sleeper_by_name.get(fantasypros_player["normalized_name"], [])
        exact_team_position = [
            candidate
            for candidate in candidates
            if candidate["position"] == fantasypros_player["position"]
            and candidate["team"] == fantasypros_player["team"]
        ]

        if len(exact_team_position) == 1:
            candidate = exact_team_position[0]
            provisional.append(
                (
                    0,
                    PlayerIdentityMatch(
                        sleeper_id=candidate["sleeper_id"],
                        fantasypros_id=fantasypros_player["fantasypros_id"],
                        player_name=fantasypros_player["name"],
                        position=fantasypros_player["position"],
                        nfl_team=fantasypros_player["team"],
                        match_method="exact_name_position_unique",
                        confidence="verified",
                    ),
                    fantasypros_player,
                    candidates,
                )
            )
            continue

        exact_position = [
            candidate
            for candidate in candidates
            if candidate["position"] == fantasypros_player["position"]
        ]
        if len(exact_position) == 1:
            candidate = exact_position[0]
            provisional.append(
                (
                    1,
                    PlayerIdentityMatch(
                        sleeper_id=candidate["sleeper_id"],
                        fantasypros_id=fantasypros_player["fantasypros_id"],
                        player_name=fantasypros_player["name"],
                        position=fantasypros_player["position"],
                        nfl_team=fantasypros_player["team"],
                        match_method="exact_name_position",
                        confidence="review",
                    ),
                    fantasypros_player,
                    candidates,
                )
            )
            continue

        unresolved.append(_unresolved_record(fantasypros_player, candidates))

    grouped: dict[str, list[tuple[int, PlayerIdentityMatch, dict[str, Any], list[dict[str, Any]]]]] = {}
    for item in provisional:
        grouped.setdefault(item[1].sleeper_id, []).append(item)

    matches: list[PlayerIdentityMatch] = []
    for sleeper_id, group in grouped.items():
        if len(group) == 1:
            matches.append(group[0][1])
            continue

        best_priority = min(item[0] for item in group)
        strongest = [item for item in group if item[0] == best_priority]
        if len(strongest) == 1:
            winner = strongest[0]
            matches.append(winner[1])
            for item in group:
                if item is winner:
                    continue
                unresolved.append(
                    _unresolved_record(
                        item[2],
                        [sleeper_by_id[sleeper_id]],
                        reason="duplicate_sleeper_match_superseded",
                    )
                )
            continue

        # Equally strong records for one Sleeper player are ambiguous. Publishing
        # neither is safer than manufacturing two AVI IDs for one player or
        # arbitrarily choosing a stale provider row.
        for item in group:
            unresolved.append(
                _unresolved_record(
                    item[2],
                    [sleeper_by_id[sleeper_id]],
                    reason="ambiguous_duplicate_source_records",
                )
            )

    matches.sort(key=lambda match: (match.player_name, match.sleeper_id, match.fantasypros_id))
    unresolved.sort(key=lambda row: (row.get("name", ""), row.get("fantasypros_id", "")))
    return matches, unresolved
