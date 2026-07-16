from __future__ import annotations

from typing import Any


def player_points_are_active(
    player_points_payloads: list[Any],
) -> bool:
    """
    Activate only when at least one payload contains a player with
    positive regular-season games or positive total points.
    """
    for payload in player_points_payloads:
        if not isinstance(payload, dict):
            continue
        players = payload.get("players")
        if not isinstance(players, list):
            continue
        for player in players:
            if not isinstance(player, dict):
                continue
            games = player.get("games", 0) or 0
            points = player.get("points", player.get("total", 0)) or 0
            try:
                if float(games) > 0 or float(points) > 0:
                    return True
            except (TypeError, ValueError):
                continue
    return False
