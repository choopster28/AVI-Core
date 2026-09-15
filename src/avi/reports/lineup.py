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

HARD_UNAVAILABLE_REASON_CODES = {
    "injured_reserve",
    "season_ending",
    "out",
}

HARD_UNAVAILABLE_STATUS_TOKENS = {
    "ir",
    "inactive",
    "injured reserve",
    "reserve injured",
    "pup",
    "nfi",
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


def _projected_lineup_available(
    player: dict[str, Any],
) -> bool:
    """Return False for players who cannot currently contribute to a lineup.

    Routine injury availability is published by the post-model availability
    layer. Projected lineups must honor that state independently of the player's
    C-AVI so an elite player on IR cannot remain a modeled starter simply because
    his residual championship value is still higher than a healthy backup.

    Questionable/doubtful players remain eligible unless the source explicitly
    marks them hard-unavailable. Their uncertainty is already reflected in C-AVI.
    """
    raw_status = str(player.get("status") or "").strip().lower().replace("_", " ").replace("-", " ")
    if raw_status in HARD_UNAVAILABLE_STATUS_TOKENS:
        return False

    availability = player.get("c_avi_availability_adjustment")
    if isinstance(availability, dict):
        reason_code = str(availability.get("reason_code") or "").strip().lower()
        if reason_code in HARD_UNAVAILABLE_REASON_CODES:
            return False

        adjustment_status = str(availability.get("status") or "").strip().lower().replace("_", " ").replace("-", " ")
        if any(token in adjustment_status for token in HARD_UNAVAILABLE_STATUS_TOKENS):
            return False

    return True


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
    valuation. Only QB, RB, WR, TE, and FLEX are considered. Players who are
    currently hard-unavailable (IR, season-ending, inactive, etc.) are excluded
    from projected starter selection while retaining their published C-AVI as an
    asset value.
    """
    available = [
        player
        for player in players
        if player.get("position")
        in OFFENSIVE_POSITIONS
        and _projected_lineup_available(player)
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