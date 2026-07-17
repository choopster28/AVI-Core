from __future__ import annotations

from dataclasses import dataclass
from typing import Any


OFFENSIVE_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
}

FLEX_ELIGIBLE_POSITIONS = {
    "RB",
    "WR",
    "TE",
}


@dataclass(frozen=True)
class LineupSlot:
    slot: str
    player: dict[str, Any]


@dataclass(frozen=True)
class ChampionshipLineup:
    slots: tuple[LineupSlot, ...]
    c_avi_sum: float
    c_avi_average: float


def _player_c_avi(
    player: dict[str, Any],
) -> float:
    value = player.get("c_avi")

    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sort_players(
    players: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        players,
        key=lambda player: (
            -_player_c_avi(player),
            str(
                player.get(
                    "canonical_name",
                    "",
                )
            ),
        ),
    )


def _take_best(
    available: list[dict[str, Any]],
    *,
    position: str,
    count: int,
) -> list[dict[str, Any]]:
    eligible = [
        player
        for player in available
        if player.get("position") == position
    ]

    selected = _sort_players(
        eligible
    )[:count]

    selected_ids = {
        player.get("avi_id")
        for player in selected
    }

    available[:] = [
        player
        for player in available
        if player.get("avi_id")
        not in selected_ids
    ]

    return selected


def _take_best_flex(
    available: list[dict[str, Any]],
    *,
    count: int,
) -> list[dict[str, Any]]:
    eligible = [
        player
        for player in available
        if player.get("position")
        in FLEX_ELIGIBLE_POSITIONS
    ]

    selected = _sort_players(
        eligible
    )[:count]

    selected_ids = {
        player.get("avi_id")
        for player in selected
    }

    available[:] = [
        player
        for player in available
        if player.get("avi_id")
        not in selected_ids
    ]

    return selected


def build_championship_lineup(
    *,
    players: list[dict[str, Any]],
    starter_counts: dict[str, int],
) -> ChampionshipLineup:
    """
    Build the highest-C-AVI offensive lineup for the current
    Autobots league structure.

    Kicker and IDP slots are intentionally excluded from AVI lineup
    valuation. Only QB, RB, WR, TE, and FLEX are considered.
    """
    available = [
        player
        for player in players
        if player.get("position")
        in OFFENSIVE_POSITIONS
        and player.get("status")
        != "inactive"
    ]

    slots: list[LineupSlot] = []

    for position in (
        "QB",
        "RB",
        "WR",
        "TE",
    ):
        count = int(
            starter_counts.get(
                position,
                0,
            )
        )

        selected = _take_best(
            available,
            position=position,
            count=count,
        )

        for player in selected:
            slots.append(
                LineupSlot(
                    slot=position,
                    player=player,
                )
            )

    flex_count = int(
        starter_counts.get(
            "FLEX",
            0,
        )
    )

    flex_players = _take_best_flex(
        available,
        count=flex_count,
    )

    for player in flex_players:
        slots.append(
            LineupSlot(
                slot="FLEX",
                player=player,
            )
        )

    c_avi_sum = round(
        sum(
            _player_c_avi(
                slot.player
            )
            for slot in slots
        ),
        1,
    )

    c_avi_average = round(
        (
            c_avi_sum
            / len(slots)
        )
        if slots
        else 0.0,
        2,
    )

    return ChampionshipLineup(
        slots=tuple(slots),
        c_avi_sum=c_avi_sum,
        c_avi_average=c_avi_average,
    )