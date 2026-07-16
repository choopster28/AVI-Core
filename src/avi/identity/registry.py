from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from avi.identity.resolver import (
    PlayerIdentityMatch,
    build_identity_matches,
    extract_fantasypros_players,
    extract_sleeper_players,
    normalize_name,
)
from avi.io import read_json, write_json


SLEEPER_PLAYERS_PATH = Path(
    "data/raw/sleeper/nfl_players.json"
)

FANTASYPROS_PLAYERS_PATH = Path(
    "data/raw/fantasypros/players.json"
)

OVERRIDES_PATH = Path(
    "config/player_identity_overrides.json"
)

OUTPUT_DIRECTORY = Path(
    "data/processed/identity"
)

AVI_ELIGIBLE_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
}

def load_overrides() -> dict[str, Any]:
    if not OVERRIDES_PATH.exists():
        return {
            "aliases": [],
            "position_overrides": [],
            "ignored_players": [],
        }

    overrides = read_json(OVERRIDES_PATH)

    if not isinstance(overrides, dict):
        raise RuntimeError(
            "player_identity_overrides.json must contain "
            "a JSON object."
        )

    overrides.setdefault("aliases", [])
    overrides.setdefault("position_overrides", [])
    overrides.setdefault("ignored_players", [])

    return overrides


def build_alias_map(
    overrides: dict[str, Any],
) -> dict[str, str]:
    alias_map: dict[str, str] = {}

    for record in overrides.get("aliases", []):
        fantasypros_name = record.get(
            "fantasypros_name"
        )
        sleeper_name = record.get(
            "sleeper_name"
        )

        if not fantasypros_name or not sleeper_name:
            continue

        alias_map[
            normalize_name(
                str(fantasypros_name)
            )
        ] = normalize_name(
            str(sleeper_name)
        )

    return alias_map


def build_position_override_map(
    overrides: dict[str, Any],
) -> dict[str, str]:
    position_map: dict[str, str] = {}

    for record in overrides.get(
        "position_overrides",
        [],
    ):
        player_name = record.get(
            "player_name"
        )
        avi_position = record.get(
            "avi_position"
        )

        if not player_name or not avi_position:
            continue

        position_map[
            normalize_name(
                str(player_name)
            )
        ] = str(
            avi_position
        ).strip().upper()

    return position_map


def build_ignored_name_set(
    overrides: dict[str, Any],
) -> set[str]:
    ignored: set[str] = set()

    for record in overrides.get(
        "ignored_players",
        [],
    ):
        fantasypros_name = record.get(
            "fantasypros_name"
        )

        if fantasypros_name:
            ignored.add(
                normalize_name(
                    str(fantasypros_name)
                )
            )

    return ignored


def apply_overrides(
    fantasypros_players: list[dict[str, Any]],
    overrides: dict[str, Any],
) -> list[dict[str, Any]]:
    alias_map = build_alias_map(overrides)
    position_map = build_position_override_map(
        overrides
    )
    ignored_names = build_ignored_name_set(
        overrides
    )

    adjusted_players: list[
        dict[str, Any]
    ] = []

    for player in fantasypros_players:
        adjusted = dict(player)

        normalized_name = adjusted[
            "normalized_name"
        ]

        if normalized_name in ignored_names:
            continue

        if normalized_name in alias_map:
            adjusted[
                "normalized_name"
            ] = alias_map[
                normalized_name
            ]

        canonical_name = adjusted[
            "normalized_name"
        ]

        if canonical_name in position_map:
            adjusted[
                "position"
            ] = position_map[
                canonical_name
            ]

        adjusted_players.append(adjusted)

    return adjusted_players


def build_avi_id(
    sleeper_id: str,
) -> str:
    return f"AVI-{str(sleeper_id).zfill(8)}"


def build_registry_record(
    match: PlayerIdentityMatch,
    sleeper_lookup: dict[
        str,
        dict[str, Any],
    ],
    fantasypros_lookup: dict[
        str,
        dict[str, Any],
    ],
) -> dict[str, Any]:
    sleeper_player = sleeper_lookup[
        match.sleeper_id
    ]

    fantasypros_player = (
        fantasypros_lookup[
            match.fantasypros_id
        ]
    )

    sleeper_raw = sleeper_player.get(
        "raw",
        {},
    )

    fantasypros_raw = fantasypros_player.get(
        "raw",
        {},
    )

    return {
        "avi_id": build_avi_id(
            match.sleeper_id
        ),
        "canonical_name": sleeper_player[
            "name"
        ],
        "normalized_name": sleeper_player[
            "normalized_name"
        ],
        "position": match.position,
        "nfl_team": (
            sleeper_player.get("team")
            or fantasypros_player.get("team")
        ),
        "active": sleeper_player.get(
            "active"
        ),
        "match": {
            "method": match.match_method,
            "confidence": match.confidence,
        },
        "source_ids": {
            "sleeper_id": match.sleeper_id,
            "fantasypros_id": (
                match.fantasypros_id
            ),
            "nfl_id": fantasypros_raw.get(
                "nfl_id"
            ),
            "espn_id": sleeper_raw.get(
                "espn_id"
            ),
            "rotowire_id": sleeper_raw.get(
                "rotowire_id"
            ),
            "fantasy_data_id": sleeper_raw.get(
                "fantasy_data_id"
            ),
            "sportradar_id": sleeper_raw.get(
                "sportradar_id"
            ),
            "sportsdata_player_id": (
                fantasypros_raw.get(
                    "sportsdata_player_id"
                )
            ),
        },
        "aliases": sorted(
            {
                sleeper_player["name"],
                fantasypros_player["name"],
            }
        ),
    }


def build_player_registry() -> dict[str, Any]:
    if not SLEEPER_PLAYERS_PATH.exists():
        raise RuntimeError(
            "Sleeper player directory is missing."
        )

    if not FANTASYPROS_PLAYERS_PATH.exists():
        raise RuntimeError(
            "FantasyPros player directory is missing."
        )

    sleeper_payload = read_json(
        SLEEPER_PLAYERS_PATH
    )

    fantasypros_payload = read_json(
        FANTASYPROS_PLAYERS_PATH
    )

    overrides = load_overrides()

    sleeper_players = extract_sleeper_players(
        sleeper_payload
    )

    fantasypros_players = (
        extract_fantasypros_players(
            fantasypros_payload
        )
    )

    adjusted_fantasypros_players = (
        apply_overrides(
            fantasypros_players,
            overrides,
        )
    )

    sleeper_players = [
        player
        for player in sleeper_players
        if player.get("position")
        in AVI_ELIGIBLE_POSITIONS
    ]

    adjusted_fantasypros_players = [
        player
        for player in adjusted_fantasypros_players
        if player.get("position")
        in AVI_ELIGIBLE_POSITIONS
    ]

    matches, unresolved = (
        build_identity_matches(
            sleeper_players,
            adjusted_fantasypros_players,
        )
    )

    sleeper_lookup = {
        player["sleeper_id"]: player
        for player in sleeper_players
    }

    fantasypros_lookup = {
        player["fantasypros_id"]: player
        for player in (
            adjusted_fantasypros_players
        )
    }

    registry = [
        build_registry_record(
            match,
            sleeper_lookup,
            fantasypros_lookup,
        )
        for match in matches
    ]

    registry.sort(
        key=lambda record: (
            record["canonical_name"],
            record["avi_id"],
        )
    )

    duplicate_avi_ids = {
        record["avi_id"]
        for record in registry
        if sum(
            1
            for candidate in registry
            if candidate["avi_id"]
            == record["avi_id"]
        )
        > 1
    }

    if duplicate_avi_ids:
        raise RuntimeError(
            "Duplicate AVI IDs found: "
            + ", ".join(
                sorted(duplicate_avi_ids)
            )
        )

    summary = {
        "registry_players": len(registry),
        "unresolved_players": len(unresolved),
        "verified_matches": sum(
            1
            for record in registry
            if record["match"]["confidence"]
            == "verified"
        ),
        "review_matches": sum(
            1
            for record in registry
            if record["match"]["confidence"]
            == "review"
        ),
    }

    write_json(
        OUTPUT_DIRECTORY
        / "avi_player_registry.json",
        registry,
    )

    write_json(
        OUTPUT_DIRECTORY
        / "registry_unresolved.json",
        unresolved,
    )

    write_json(
        OUTPUT_DIRECTORY
        / "registry_summary.json",
        summary,
    )

    print()
    print("=" * 60)
    print("AVI PLAYER REGISTRY COMPLETE")
    print("=" * 60)
    print(
        f"Registry players: "
        f"{summary['registry_players']}"
    )
    print(
        f"Verified: "
        f"{summary['verified_matches']}"
    )
    print(
        f"Needs review: "
        f"{summary['review_matches']}"
    )
    print(
        f"Unresolved: "
        f"{summary['unresolved_players']}"
    )

    return summary