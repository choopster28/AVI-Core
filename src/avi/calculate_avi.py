from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.io import read_json, write_json
from avi.league.loader import load_league_structure
from avi.valuation.calculator import (
    CAVIComponents,
    DAVIComponents,
    calculate_c_avi,
    calculate_d_avi,
)
from avi.valuation.projections import load_position_projections
from avi.valuation.replacement import calculate_replacement_levels
from avi.valuation.scaling import clamp, field_score, percentile_score


REGISTRY_PATH = Path(
    "data/processed/identity/avi_player_registry.json"
)

FANTASYPROS_ROOT = Path(
    "data/raw/fantasypros"
)

OUTPUT_PATH = Path(
    "data/processed/avi/avi_players.json"
)

MANIFEST_PATH = Path(
    "data/processed/avi/manifest.json"
)

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

SUPPORTED_POSITIONS = (
    *OFFENSIVE_POSITIONS,
    *IDP_POSITIONS,
)


def safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_registry() -> list[dict[str, Any]]:
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

    return [
        record
        for record in registry
        if isinstance(record, dict)
    ]


def load_ranking_records(
    category: str,
    position: str,
) -> list[dict[str, Any]]:
    path = (
        FANTASYPROS_ROOT
        / "rankings"
        / category
        / f"{position}.json"
    )

    if not path.exists():
        return []

    payload = read_json(path)

    if not isinstance(payload, dict):
        return []

    players = payload.get("players")

    if not isinstance(players, list):
        return []

    return [
        record
        for record in players
        if isinstance(record, dict)
    ]


def load_rank_scores(
    category: str,
    position: str,
) -> dict[str, float]:
    records = load_ranking_records(
        category,
        position,
    )

    valid: list[tuple[str, float]] = []

    for record in records:
        player_id = record.get("player_id")
        rank = safe_float(
            record.get("rank_ecr")
        )

        if player_id is None or rank is None:
            continue

        valid.append(
            (
                str(player_id),
                rank,
            )
        )

    if not valid:
        return {}

    ranks = [
        rank
        for _, rank in valid
    ]

    maximum_rank = max(ranks)

    if maximum_rank <= 1:
        return {
            player_id: 100.0
            for player_id, _ in valid
        }

    return {
        player_id: clamp(
            100.0
            * (
                maximum_rank - rank
            )
            / (
                maximum_rank - 1.0
            )
        )
        for player_id, rank in valid
    }


def load_projection_data() -> dict[
    str,
    list[dict[str, Any]],
]:
    projections: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for position in OFFENSIVE_POSITIONS:
        projections[position] = (
            load_position_projections(
                position
            )
        )

    for position in IDP_POSITIONS:
        projections[position] = []

    return projections


def calculate_projection_scores(
    projections_by_position: dict[
        str,
        list[dict[str, Any]],
    ],
    replacement_values: dict[str, float],
) -> dict[str, dict[str, float]]:
    scores: dict[
        str,
        dict[str, float],
    ] = {}

    for position in OFFENSIVE_POSITIONS:
        players = projections_by_position.get(
            position,
            [],
        )

        field = [
            float(
                player[
                    "projected_ppr_points"
                ]
            )
            for player in players
        ]

        if not field:
            continue

        replacement_value = (
            replacement_values.get(
                position,
                0.0,
            )
        )

        for rank, player in enumerate(
            players,
            start=1,
        ):
            points = float(
                player[
                    "projected_ppr_points"
                ]
            )

            component = field_score(
                points,
                field,
                replacement_value,
            )

            scores[
                player["avi_id"]
            ] = {
                "raw_points": points,
                "position_rank": rank,
                "percentile": percentile_score(
                    points,
                    field,
                ),
                "component_score": component,
            }

    return scores


def build_market_score(
    dynasty_score: float | None,
    redraft_score: float | None,
) -> float | None:
    if (
        dynasty_score is None
        and redraft_score is None
    ):
        return None

    if dynasty_score is None:
        return redraft_score

    if redraft_score is None:
        return dynasty_score

    return clamp(
        (
            2.0 * dynasty_score
            + redraft_score
        )
        / 3.0
    )


def build_context_score(
    projection_score: float,
    projection_percentile: float,
) -> float:
    return clamp(
        0.60 * projection_score
        + 0.40 * projection_percentile
    )


def build_upside_score(
    projection_score: float,
    market_score: float,
) -> float:
    return clamp(
        0.70 * projection_score
        + 0.30 * market_score
    )


def calculate_age_lifecycle(
    age: float | None,
    position: str,
) -> float:
    if age is None:
        return 50.0

    prime_ranges = {
        "QB": (24, 32),
        "RB": (21, 26),
        "WR": (22, 28),
        "TE": (23, 29),
        "K": (24, 34),
        "DL": (23, 29),
        "LB": (23, 29),
        "DB": (23, 29),
    }

    prime_start, prime_end = prime_ranges.get(
        position,
        (23, 29),
    )

    if prime_start <= age <= prime_end:
        return 100.0

    if age < prime_start:
        years_early = prime_start - age
        return clamp(
            100.0 - 8.0 * years_early
        )

    years_late = age - prime_end

    decline_rates = {
        "QB": 5.0,
        "RB": 12.0,
        "WR": 8.0,
        "TE": 7.0,
        "K": 4.0,
        "DL": 7.0,
        "LB": 8.0,
        "DB": 8.0,
    }

    return clamp(
        100.0
        - decline_rates.get(
            position,
            8.0,
        )
        * years_late
    )


def build_avi_players() -> dict[str, Any]:
    registry = load_registry()
    league = load_league_structure()

    registry_by_fantasypros_id = {
        str(
            record["source_ids"][
                "fantasypros_id"
            ]
        ): record
        for record in registry
        if record.get("source_ids", {}).get(
            "fantasypros_id"
        )
        is not None
    }

    projections_by_position = (
        load_projection_data()
    )

    replacement_levels = (
        calculate_replacement_levels(
            projections_by_position=(
                projections_by_position
            ),
            league=league,
        )
    )

    projection_scores = (
        calculate_projection_scores(
            projections_by_position,
            replacement_levels.replacement_values,
        )
    )

    dynasty_scores: dict[str, float] = {}
    redraft_scores: dict[str, float] = {}

    for position in SUPPORTED_POSITIONS:
        dynasty_scores.update(
            load_rank_scores(
                "dynasty",
                position,
            )
        )

        redraft_scores.update(
            load_rank_scores(
                "redraft",
                position,
            )
        )

    output: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for fantasypros_id, player in (
        registry_by_fantasypros_id.items()
    ):
        avi_id = player["avi_id"]
        position = player["position"]

        dynasty_score = dynasty_scores.get(
            fantasypros_id
        )

        redraft_score = redraft_scores.get(
            fantasypros_id
        )

        market_score = build_market_score(
            dynasty_score,
            redraft_score,
        )

        projection = projection_scores.get(
            avi_id
        )

        if position in OFFENSIVE_POSITIONS:
            if (
                projection is None
                or market_score is None
            ):
                output.append(
                    {
                        **player,
                        "methodology_status": (
                            "inactive_unranked"
                        ),
                        "season_phase": "preseason",
                        "status": "inactive",
                        "c_avi": 0.0,
                        "d_avi": 0.0,
                        "projection": projection,
                        "components": {
                            "projection": None,
                            "league_context": None,
                            "public_market": (
                                market_score
                            ),
                            "elite_upside": None,
                            "player_points": 0.0,
                            "dynasty_market": (
                                dynasty_score
                            ),
                            "redraft_market": (
                                redraft_score
                            ),
                            "age_lifecycle": None,
                        },
                        "reason": (
                            "No complete current "
                            "FantasyPros projection and "
                            "ranking profile."
                        ),
                    }
                )
                continue

            projection_component = projection[
                "component_score"
            ]

            projection_percentile = projection[
                "percentile"
            ]

        elif position in IDP_POSITIONS:
            if market_score is None:
                unresolved.append(
                    {
                        "avi_id": avi_id,
                        "player_name": player[
                            "canonical_name"
                        ],
                        "position": position,
                        "reason": (
                            "Missing IDP ranking."
                        ),
                    }
                )
                continue

            projection_component = (
                redraft_score
                if redraft_score is not None
                else market_score
            )

            projection_percentile = (
                projection_component
            )

            projection = {
                "raw_points": None,
                "position_rank": None,
                "percentile": (
                    projection_percentile
                ),
                "component_score": (
                    projection_component
                ),
                "source": (
                    "FantasyPros ranking proxy"
                ),
            }

        else:
            continue

        context_score = build_context_score(
            projection_component,
            projection_percentile,
        )

        upside_score = build_upside_score(
            projection_component,
            market_score,
        )

        c_avi = calculate_c_avi(
            CAVIComponents(
                player_points=0.0,
                projections=(
                    projection_component
                ),
                league_context=(
                    context_score
                ),
                public_market=market_score,
                elite_upside=upside_score,
            ),
            player_points_active=False,
        )

        raw = player.get(
            "source_ids",
            {},
        )

        sleeper_record = player.get(
            "raw",
            {},
        )

        age = safe_float(
            player.get("age")
        )

        if age is None:
            age = safe_float(
                sleeper_record.get("age")
                if isinstance(
                    sleeper_record,
                    dict,
                )
                else None
            )

        age_lifecycle = (
            calculate_age_lifecycle(
                age,
                position,
            )
        )

        d_avi = calculate_d_avi(
            DAVIComponents(
                dynasty_market=(
                    dynasty_score
                    if dynasty_score is not None
                    else market_score
                ),
                current_c_avi=c_avi,
                age_lifecycle=(
                    age_lifecycle
                ),
                role_stability=market_score,
                prior_d_avi=market_score,
                health=market_score,
                long_term_ceiling=max(
                    market_score,
                    projection_component,
                ),
            )
        )

        output.append(
            {
                **player,
                "methodology_status": (
                    "provisional_v1"
                ),
                "season_phase": "preseason",
                "c_avi": c_avi,
                "d_avi": d_avi,
                "projection": projection,
                "components": {
                    "projection": (
                        projection_component
                    ),
                    "league_context": (
                        context_score
                    ),
                    "public_market": (
                        market_score
                    ),
                    "elite_upside": (
                        upside_score
                    ),
                    "player_points": 0.0,
                    "dynasty_market": (
                        dynasty_score
                    ),
                    "redraft_market": (
                        redraft_score
                    ),
                    "age_lifecycle": (
                        age_lifecycle
                    ),
                },
            }
        )

    output.sort(
        key=lambda record: (
            -record["c_avi"],
            record["canonical_name"],
        )
    )

    now = datetime.now(UTC)

    manifest = {
        "methodology_version": "2026.1",
        "methodology_status": (
            "provisional_v1"
        ),
        "generated_at_utc": now.isoformat(),
        "league_id": league.league_id,
        "season": league.season,
        "season_phase": "preseason",
        "player_points_active": False,
        "weights": {
            "player_points": 0.00,
            "projections": 0.50,
            "league_context": 0.10,
            "public_market": 0.30,
            "elite_upside": 0.10,
        },
        "replacement_levels": {
            "starter_demand": (
                replacement_levels.starter_demand
            ),
            "flex_allocations": (
                replacement_levels.flex_allocations
            ),
            "replacement_ranks": (
                replacement_levels.replacement_ranks
            ),
            "replacement_values": (
                replacement_levels.replacement_values
            ),
        },
        "record_counts": {
            "registry_players": len(
                registry
            ),
            "calculated_players": len(
                output
            ),
            "unresolved_players": len(
                unresolved
            ),
        },
        "status": (
            "passed"
            if output
            else "failed"
        ),
    }

    write_json(
        OUTPUT_PATH,
        output,
    )

    write_json(
        Path(
            "data/processed/avi/"
            "unresolved_players.json"
        ),
        unresolved,
    )

    write_json(
        MANIFEST_PATH,
        manifest,
    )

    print()
    print("=" * 60)
    print("AVI CALCULATION COMPLETE")
    print("=" * 60)
    print(
        f"Calculated players: "
        f"{len(output)}"
    )
    print(
        f"Unresolved players: "
        f"{len(unresolved)}"
    )
    print(
        "Player points active: False"
    )

    return manifest