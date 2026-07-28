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


AGE_CURVES: dict[
    str,
    tuple[tuple[float, float], ...],
] = {
    "QB": (
        (20, 74),
        (22, 84),
        (24, 93),
        (26, 98),
        (28, 100),
        (30, 98),
        (32, 94),
        (34, 87),
        (36, 77),
        (38, 64),
        (40, 48),
    ),
    "RB": (
        (19, 84),
        (20, 92),
        (21, 98),
        (22, 100),
        (23, 99),
        (24, 96),
        (25, 91),
        (26, 83),
        (27, 72),
        (28, 59),
        (29, 45),
        (30, 31),
        (32, 10),
    ),
    "WR": (
        (19, 82),
        (20, 89),
        (21, 95),
        (22, 99),
        (23, 100),
        (24, 99),
        (25, 98),
        (26, 96),
        (27, 93),
        (28, 89),
        (29, 83),
        (30, 76),
        (31, 67),
        (32, 57),
        (34, 35),
        (36, 15),
    ),
    "TE": (
        (20, 77),
        (21, 83),
        (22, 90),
        (23, 95),
        (24, 98),
        (25, 100),
        (26, 99),
        (27, 97),
        (28, 94),
        (29, 90),
        (30, 85),
        (31, 78),
        (32, 70),
        (34, 52),
        (36, 32),
    ),
    "K": (
        (20, 65),
        (23, 80),
        (26, 92),
        (29, 98),
        (32, 100),
        (35, 96),
        (38, 88),
        (41, 75),
        (44, 58),
    ),
    "DL": (
        (20, 82),
        (22, 94),
        (24, 100),
        (26, 98),
        (28, 93),
        (30, 84),
        (32, 70),
        (34, 50),
        (36, 28),
    ),
    "LB": (
        (20, 84),
        (22, 96),
        (24, 100),
        (26, 97),
        (28, 90),
        (30, 79),
        (32, 64),
        (34, 44),
        (36, 24),
    ),
    "DB": (
        (20, 85),
        (22, 97),
        (24, 100),
        (26, 96),
        (28, 88),
        (30, 76),
        (32, 60),
        (34, 40),
        (36, 20),
    ),
}


def safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def interpolate_curve(
    value: float,
    points: tuple[tuple[float, float], ...],
) -> float:
    if value <= points[0][0]:
        return points[0][1]

    if value >= points[-1][0]:
        return points[-1][1]

    for index in range(1, len(points)):
        right_x, right_y = points[index]
        left_x, left_y = points[index - 1]

        if value <= right_x:
            span = right_x - left_x

            if span <= 0:
                return clamp(right_y)

            ratio = (
                value - left_x
            ) / span

            return clamp(
                left_y
                + ratio
                * (right_y - left_y)
            )

    return clamp(points[-1][1])


def calculate_age_career_horizon(
    age: float | None,
    position: str,
) -> float | None:
    if age is None:
        return None

    curve = AGE_CURVES.get(position)

    if curve is None:
        return None

    return round(
        interpolate_curve(
            age,
            curve,
        ),
        1,
    )


def calculate_position_liquidity(
    *,
    position: str,
    team_count: int,
    starter_demand: dict[str, int],
    flex_allocations: dict[str, int],
) -> float:
    if team_count < 1:
        raise ValueError(
            "Team count must be positive."
        )

    mandatory_per_team = (
        starter_demand.get(
            position,
            0,
        )
        / team_count
    )

    flex_per_team = (
        flex_allocations.get(
            position,
            0,
        )
        / team_count
    )

    score = (
        35.0
        + 25.0 * mandatory_per_team
        + 20.0 * flex_per_team
    )

    caps = {
        "QB": 62.0,
        "K": 25.0,
        "DL": 78.0,
        "LB": 82.0,
        "DB": 74.0,
    }

    if position in caps:
        score = min(
            score,
            caps[position],
        )

    return round(
        clamp(score),
        1,
    )


def build_long_term_ceiling(
    *,
    dynasty_market: float,
    projection_component: float,
    age_career_horizon: float | None,
) -> float:
    inputs: list[
        tuple[float, float]
    ] = [
        (
            0.50,
            dynasty_market,
        ),
        (
            0.30,
            projection_component,
        ),
    ]

    if age_career_horizon is not None:
        inputs.append(
            (
                0.20,
                age_career_horizon,
            )
        )

    total_weight = sum(
        weight
        for weight, _ in inputs
    )

    return round(
        clamp(
            sum(
                weight * value
                for weight, value in inputs
            )
            / total_weight
        ),
        1,
    )


def load_registry() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        raise RuntimeError(
            "AVI Player Registry is missing. "
            "Run build-registry first."
        )

    registry = read_json(
        REGISTRY_PATH
    )

    if not isinstance(
        registry,
        list,
    ):
        raise RuntimeError(
            "AVI Player Registry must contain "
            "a JSON list."
        )

    return [
        record
        for record in registry
        if isinstance(
            record,
            dict,
        )
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

    if not isinstance(
        payload,
        dict,
    ):
        return []

    players = payload.get(
        "players"
    )

    if not isinstance(
        players,
        list,
    ):
        return []

    return [
        record
        for record in players
        if isinstance(
            record,
            dict,
        )
    ]


def load_rank_scores(
    category: str,
    position: str,
) -> dict[str, float]:
    records = load_ranking_records(
        category,
        position,
    )

    valid: list[
        tuple[str, float]
    ] = []

    for record in records:
        player_id = record.get(
            "player_id"
        )

        rank = safe_float(
            record.get(
                "rank_ecr"
            )
        )

        if (
            player_id is None
            or rank is None
        ):
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
        players = (
            projections_by_position.get(
                position,
                [],
            )
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
                "percentile": (
                    percentile_score(
                        points,
                        field,
                    )
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


def build_avi_players() -> dict[str, Any]:
    registry = load_registry()
    league = load_league_structure()

    registry_by_fantasypros_id = {
        str(
            record[
                "source_ids"
            ][
                "fantasypros_id"
            ]
        ): record
        for record in registry
        if record.get(
            "source_ids",
            {},
        ).get(
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

    dynasty_scores: dict[
        str,
        float,
    ] = {}

    redraft_scores: dict[
        str,
        float,
    ] = {}

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

    output: list[
        dict[str, Any]
    ] = []

    unresolved: list[
        dict[str, Any]
    ] = []

    for fantasypros_id, player in (
        registry_by_fantasypros_id.items()
    ):
        avi_id = player["avi_id"]
        position = player["position"]

        dynasty_score = (
            dynasty_scores.get(
                fantasypros_id
            )
        )

        redraft_score = (
            redraft_scores.get(
                fantasypros_id
            )
        )

        market_score = build_market_score(
            dynasty_score,
            redraft_score,
        )

        projection = (
            projection_scores.get(
                avi_id
            )
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
                            "age_career_horizon": None,
                            "position_liquidity": None,
                            "long_term_security": None,
                            "health_outlook": None,
                            "long_term_ceiling": None,
                        },
                        "reason": (
                            "No complete current "
                            "FantasyPros projection and "
                            "ranking profile."
                        ),
                    }
                )
                continue

            projection_component = (
                projection[
                    "component_score"
                ]
            )

            projection_percentile = (
                projection[
                    "percentile"
                ]
            )

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
                public_market=(
                    market_score
                ),
                elite_upside=(
                    upside_score
                ),
            ),
            player_points_active=False,
        )

        sleeper_record = player.get(
            "raw",
            {},
        )

        age = safe_float(
            player.get(
                "age"
            )
        )

        if age is None:
            age = safe_float(
                sleeper_record.get(
                    "age"
                )
                if isinstance(
                    sleeper_record,
                    dict,
                )
                else None
            )

        age_career_horizon = (
            calculate_age_career_horizon(
                age,
                position,
            )
        )

        position_liquidity = (
            calculate_position_liquidity(
                position=position,
                team_count=(
                    league.team_count
                ),
                starter_demand=(
                    replacement_levels.starter_demand
                ),
                flex_allocations=(
                    replacement_levels.flex_allocations
                ),
            )
        )

        verified_dynasty_market = (
            dynasty_score
            if dynasty_score is not None
            else market_score
        )

        long_term_ceiling = (
            build_long_term_ceiling(
                dynasty_market=(
                    verified_dynasty_market
                ),
                projection_component=(
                    projection_component
                ),
                age_career_horizon=(
                    age_career_horizon
                ),
            )
        )

        d_avi = calculate_d_avi(
            DAVIComponents(
                dynasty_market=(
                    verified_dynasty_market
                ),
                age_career_horizon=(
                    age_career_horizon
                ),
                long_term_security=None,
                position_liquidity=(
                    position_liquidity
                ),
                current_c_avi=c_avi,
                health_outlook=None,
                long_term_ceiling=(
                    long_term_ceiling
                ),
            )
        )

        output.append(
            {
                **player,
                "methodology_status": (
                    "provisional_2026_2"
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
                    "age_career_horizon": (
                        age_career_horizon
                    ),
                    "position_liquidity": (
                        position_liquidity
                    ),
                    "long_term_security": None,
                    "health_outlook": None,
                    "long_term_ceiling": (
                        long_term_ceiling
                    ),
                },
            }
        )

    output.sort(
        key=lambda record: (
            -record["d_avi"],
            -record["c_avi"],
            record["canonical_name"],
        )
    )

    now = datetime.now(UTC)

    manifest = {
        "methodology_version": "2026.2",
        "methodology_status": (
            "provisional_2026_2"
        ),
        "generated_at_utc": (
            now.isoformat()
        ),
        "league_id": league.league_id,
        "season": league.season,
        "season_phase": "preseason",
        "player_points_active": False,
        "c_avi_weights": {
            "player_points": 0.00,
            "projections": 0.50,
            "league_context": 0.10,
            "public_market": 0.30,
            "elite_upside": 0.10,
        },
        "d_avi_weights": {
            "dynasty_market": 0.35,
            "age_career_horizon": 0.20,
            "long_term_security": 0.15,
            "position_liquidity": 0.10,
            "current_c_avi": 0.10,
            "health_outlook": 0.05,
            "long_term_ceiling": 0.05,
        },
        "d_avi_missing_component_policy": (
            "Redistribute missing optional "
            "component weights proportionally "
            "across verified components."
        ),
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
            "registry_players": (
                len(registry)
            ),
            "calculated_players": (
                len(output)
            ),
            "unresolved_players": (
                len(unresolved)
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
    print(
        "D-AVI methodology: 2026.2"
    )

    return manifest
