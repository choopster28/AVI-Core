from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from avi.identity.resolver import (
    build_identity_matches,
    extract_fantasypros_players,
    extract_sleeper_players,
)
from avi.io import read_json, write_json


SLEEPER_PLAYERS_PATH = Path(
    "data/raw/sleeper/nfl_players.json"
)

FANTASYPROS_PLAYERS_PATH = Path(
    "data/raw/fantasypros/players.json"
)

OUTPUT_DIRECTORY = Path(
    "data/processed/identity"
)


def build_player_identity_map() -> dict:
    if not SLEEPER_PLAYERS_PATH.exists():
        raise RuntimeError(
            "Sleeper player directory is missing. "
            "Run update-sleeper first."
        )

    if not FANTASYPROS_PLAYERS_PATH.exists():
        raise RuntimeError(
            "FantasyPros player directory is missing. "
            "Run update-fantasypros first."
        )

    sleeper_payload = read_json(
        SLEEPER_PLAYERS_PATH
    )

    fantasypros_payload = read_json(
        FANTASYPROS_PLAYERS_PATH
    )

    sleeper_players = extract_sleeper_players(
        sleeper_payload
    )

    fantasypros_players = (
        extract_fantasypros_players(
            fantasypros_payload
        )
    )

    matches, unresolved = (
        build_identity_matches(
            sleeper_players,
            fantasypros_players,
        )
    )

    match_records = [
        asdict(match)
        for match in matches
    ]

    summary = {
        "sleeper_players": len(
            sleeper_players
        ),
        "fantasypros_players": len(
            fantasypros_players
        ),
        "matched_players": len(
            match_records
        ),
        "unresolved_players": len(
            unresolved
        ),
        "verified_matches": sum(
            1
            for match in match_records
            if match["confidence"] == "verified"
        ),
        "review_matches": sum(
            1
            for match in match_records
            if match["confidence"] == "review"
        ),
    }

    write_json(
        OUTPUT_DIRECTORY
        / "player_identity_map.json",
        match_records,
    )

    write_json(
        OUTPUT_DIRECTORY
        / "unresolved_players.json",
        unresolved,
    )

    write_json(
        OUTPUT_DIRECTORY
        / "identity_summary.json",
        summary,
    )

    print()
    print("=" * 60)
    print("PLAYER IDENTITY BUILD COMPLETE")
    print("=" * 60)
    print(
        f"Matched: {summary['matched_players']}"
    )
    print(
        "Needs review: "
        f"{summary['review_matches']}"
    )
    print(
        "Unresolved: "
        f"{summary['unresolved_players']}"
    )

    return summary