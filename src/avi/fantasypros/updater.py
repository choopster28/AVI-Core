from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.config import AviConfig
from avi.fantasypros.client import FantasyProsClient
from avi.io import write_json


RAW_ROOT = Path("data/raw/fantasypros")

OFFENSIVE_POSITIONS = (
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
)

IDP_POSITIONS = (
    "DL",
    "LB",
    "DB",
)

PLAYER_POINT_POSITIONS = (
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
    "DE",
    "DT",
    "LB",
    "CB",
    "S",
    "DB",
)


def _record_count(payload: Any) -> int | None:
    """
    Return a useful count when the FantasyPros response exposes
    a common collection field.
    """
    if isinstance(payload, list):
        return len(payload)

    if not isinstance(payload, dict):
        return None

    for key in (
        "players",
        "rankings",
        "news",
        "injuries",
        "results",
        "data",
    ):
        value = payload.get(key)

        if isinstance(value, list):
            return len(value)

        if isinstance(value, dict):
            return len(value)

    return None


def update_fantasypros(
    config: AviConfig,
) -> dict[str, Any]:
    client = FantasyProsClient(
        base_url=config.fantasypros_base_url,
        api_key=config.fantasypros_api_key,
        api_key_header=config.fantasypros_api_key_header,
    )

    downloaded_at = datetime.now(UTC)

    print("=" * 60)
    print("AVI FANTASYPROS UPDATE")
    print("=" * 60)
    print(f"Season: {config.avi_season}")
    print(f"Scoring: {config.avi_scoring}")
    print()

    dataset_counts: dict[str, int | None] = {}
    warnings: list[str] = []

    print("Downloading NFL player directory...")

    players = client.get_players()

    write_json(
        RAW_ROOT / "players.json",
        players,
    )

    dataset_counts["players"] = _record_count(
        players
    )

    print("Downloading injuries...")

    injuries = client.get_injuries(
        season=config.avi_season,
        week=0,
    )

    write_json(
        RAW_ROOT / "injuries.json",
        injuries,
    )

    dataset_counts["injuries"] = _record_count(
        injuries
    )

    print("Downloading news...")

    news = client.get_news(
        limit=500,
    )

    write_json(
        RAW_ROOT / "news.json",
        news,
    )

    dataset_counts["news"] = _record_count(
        news
    )

    print()
    print("Downloading full-season projections...")

    projection_positions = (
        OFFENSIVE_POSITIONS
        + IDP_POSITIONS
    )

    for position in projection_positions:
        print(
            f"Downloading {position} projections..."
        )

        try:
            projections = client.get_projections(
                season=config.avi_season,
                position=position,
                week=0,
                ros=False,
            )
        except Exception as exc:
            if position in IDP_POSITIONS:
                warning = (
                    f"{position} projections unavailable: "
                    f"{type(exc).__name__}: {exc}"
                )
                warnings.append(warning)
                print(f"WARNING: {warning}")
                continue

            raise

        write_json(
            RAW_ROOT
            / "projections"
            / f"{position}.json",
            projections,
        )

        dataset_counts[
            f"projections_{position}"
        ] = _record_count(projections)

    print()
    print("Downloading dynasty consensus rankings...")

    for position in projection_positions:
        print(
            f"Downloading {position} dynasty rankings..."
        )

        dynasty_rankings = (
            client.get_consensus_rankings(
                season=config.avi_season,
                position=position,
                ranking_type="DYNASTY",
                scoring=config.avi_scoring,
                week=0,
                include_idp=(
                    position in IDP_POSITIONS
                ),
            )
        )

        write_json(
            RAW_ROOT
            / "consensus_rankings"
            / "dynasty"
            / f"{position}.json",
            dynasty_rankings,
        )

        dataset_counts[
            f"dynasty_rankings_{position}"
        ] = _record_count(
            dynasty_rankings
        )

    print()
    print("Downloading redraft consensus rankings...")

    for position in projection_positions:
        print(
            f"Downloading {position} redraft rankings..."
        )

        redraft_rankings = (
            client.get_consensus_rankings(
                season=config.avi_season,
                position=position,
                ranking_type="DRAFT",
                scoring=config.avi_scoring,
                week=0,
                include_idp=(
                    position in IDP_POSITIONS
                ),
            )
        )

        write_json(
            RAW_ROOT
            / "consensus_rankings"
            / "redraft"
            / f"{position}.json",
            redraft_rankings,
        )

        dataset_counts[
            f"redraft_rankings_{position}"
        ] = _record_count(
            redraft_rankings
        )

    print()
    print("Downloading player points...")

    for position in PLAYER_POINT_POSITIONS:
        print(
            f"Downloading {position} player points..."
        )

        points = client.get_player_points(
            season=config.avi_season,
            position=position,
            scoring=config.avi_scoring,
            start_week=1,
            end_week=18,
        )

        write_json(
            RAW_ROOT
            / "player_points"
            / f"{position}.json",
            points,
        )

        dataset_counts[
            f"player_points_{position}"
        ] = _record_count(points)

    manifest = {
        "snapshot_id": downloaded_at.strftime(
            "%Y-%m-%dT%H-%M-%SZ"
        ),
        "downloaded_at_utc": (
            downloaded_at.isoformat()
        ),
        "season": config.avi_season,
        "scoring": config.avi_scoring,
        "methodology_version": (
            config.methodology_version
        ),
        "player_points": {
            "collected": True,
            "currently_used_in_c_avi": False,
            "activation_rule": (
                "Activate only after verified "
                "regular-season player points exist."
            ),
            "preseason_weight": 0.0,
            "in_season_weight": 0.10,
        },
        "projection_weights": {
            "preseason": 0.50,
            "in_season": 0.40,
        },
        "dataset_counts": dataset_counts,
        "warnings": warnings,
        "status": "passed",
    }

    write_json(
        RAW_ROOT / "manifest.json",
        manifest,
    )

    print()
    print("=" * 60)
    print("FANTASYPROS UPDATE COMPLETED")
    print("=" * 60)
    print(
        "Player points collected but not "
        "currently used in C-AVI."
    )

    if warnings:
        print(
            f"Warnings: {len(warnings)}"
        )

    return manifest