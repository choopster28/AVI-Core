from __future__ import annotations

from dataclasses import dataclass

from avi.league.loader import LeagueStructure


FLEX_POSITIONS = {
    "RB",
    "WR",
    "TE",
}


@dataclass(frozen=True)
class ReplacementLevels:
    starter_demand: dict[str, int]
    flex_allocations: dict[str, int]
    replacement_ranks: dict[str, int]
    replacement_values: dict[str, float]


def calculate_replacement_levels(
    *,
    projections_by_position: dict[
        str,
        list[dict],
    ],
    league: LeagueStructure,
) -> ReplacementLevels:
    """
    Calculate Autobots replacement levels from the live Sleeper
    league structure and current FantasyPros projections.

    Process:
    1. Fill mandatory positional starters.
    2. Pool the remaining RB, WR, and TE players.
    3. Award FLEX spots to the highest projected remaining players.
    4. Set each positional replacement rank at the end of expected
       league-wide starter demand.
    """
    starter_demand: dict[str, int] = {}

    for position, starter_count in (
        league.starter_counts.items()
    ):
        if position in {
            "FLEX",
            "SUPERFLEX",
        }:
            continue

        starter_demand[position] = (
            starter_count
            * league.team_count
        )

    flex_spots = (
        league.starter_counts.get(
            "FLEX",
            0,
        )
        * league.team_count
    )

    flex_candidates: list[
        dict
    ] = []

    for position in FLEX_POSITIONS:
        players = projections_by_position.get(
            position,
            [],
        )

        mandatory_count = starter_demand.get(
            position,
            0,
        )

        remaining_players = players[
            mandatory_count:
        ]

        for player in remaining_players:
            flex_candidates.append(
                {
                    "position": position,
                    "projected_ppr_points": float(
                        player[
                            "projected_ppr_points"
                        ]
                    ),
                }
            )

    flex_candidates.sort(
        key=lambda player: (
            -player[
                "projected_ppr_points"
            ],
            player["position"],
        )
    )

    selected_flex_players = (
        flex_candidates[:flex_spots]
    )

    flex_allocations = {
        "RB": 0,
        "WR": 0,
        "TE": 0,
    }

    for player in selected_flex_players:
        position = player["position"]

        flex_allocations[position] += 1

    replacement_ranks: dict[
        str,
        int,
    ] = {}

    replacement_values: dict[
        str,
        float,
    ] = {}

    all_positions = set(
        starter_demand
    ) | set(
        projections_by_position
    )

    for position in all_positions:
        mandatory_count = (
            starter_demand.get(
                position,
                0,
            )
        )

        flex_count = flex_allocations.get(
            position,
            0,
        )

        replacement_rank = (
            mandatory_count
            + flex_count
        )

        replacement_ranks[
            position
        ] = replacement_rank

        players = projections_by_position.get(
            position,
            [],
        )

        if (
            replacement_rank < 1
            or not players
        ):
            replacement_values[
                position
            ] = 0.0
            continue

        index = min(
            replacement_rank - 1,
            len(players) - 1,
        )

        replacement_values[
            position
        ] = float(
            players[index][
                "projected_ppr_points"
            ]
        )

    return ReplacementLevels(
        starter_demand=starter_demand,
        flex_allocations=flex_allocations,
        replacement_ranks=(
            replacement_ranks
        ),
        replacement_values=(
            replacement_values
        ),
    )