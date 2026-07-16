from __future__ import annotations

from pathlib import Path
from typing import Any

from avi.io import read_json


FANTASYPROS_PROJECTIONS_ROOT = Path(
    "data/raw/fantasypros/projections"
)

REGISTRY_PATH = Path(
    "data/processed/identity/avi_player_registry.json"
)


def extract_ppr_projection(
    record: dict[str, Any],
) -> float | None:
    stats = record.get("stats")

    if not isinstance(stats, dict):
        return None

    value = stats.get("points_ppr")

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_registry_by_fantasypros_id() -> dict[str, dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        raise RuntimeError(
            "AVI Player Registry is missing. "
            "Run build-registry first."
        )

    registry = read_json(REGISTRY_PATH)

    if not isinstance(registry, list):
        raise RuntimeError(
            "AVI Player Registry must contain a JSON list."
        )

    lookup: dict[str, dict[str, Any]] = {}

    for player in registry:
        if not isinstance(player, dict):
            continue

        source_ids = player.get("source_ids", {})

        if not isinstance(source_ids, dict):
            continue

        fantasypros_id = source_ids.get(
            "fantasypros_id"
        )

        if fantasypros_id is None:
            continue

        lookup[str(fantasypros_id)] = player

    return lookup


def load_position_projections(
    position: str,
) -> list[dict[str, Any]]:
    path = (
        FANTASYPROS_PROJECTIONS_ROOT
        / f"{position.upper()}.json"
    )

    if not path.exists():
        raise RuntimeError(
            f"FantasyPros projection file is missing: {path}"
        )

    payload = read_json(path)

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"{path} must contain a JSON object."
        )

    raw_players = payload.get("players")

    if not isinstance(raw_players, list):
        raise RuntimeError(
            f"{path} does not contain a players list."
        )

    registry_lookup = (
        load_registry_by_fantasypros_id()
    )

    normalized: list[dict[str, Any]] = []

    for record in raw_players:
        if not isinstance(record, dict):
            continue

        fantasypros_id = record.get("fpid")

        if fantasypros_id is None:
            continue

        registry_player = registry_lookup.get(
            str(fantasypros_id)
        )

        if registry_player is None:
            continue

        projected_points = extract_ppr_projection(
            record
        )

        if projected_points is None:
            continue

        normalized.append(
            {
                "avi_id": registry_player["avi_id"],
                "fantasypros_id": str(
                    fantasypros_id
                ),
                "player_name": registry_player[
                    "canonical_name"
                ],
                "position": registry_player[
                    "position"
                ],
                "nfl_team": registry_player[
                    "nfl_team"
                ],
                "projected_ppr_points": (
                    projected_points
                ),
            }
        )

    normalized.sort(
        key=lambda player: (
            -player["projected_ppr_points"],
            player["player_name"],
        )
    )

    return normalized