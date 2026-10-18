"""2026 in-season power ranking calculation.

Use verified current-season Sleeper records and official C-AVI only.
Optimal starters are produced by the existing championship lineup optimizer,
not by the lineup submitted in a particular matchup.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _score(value: Any, label: str) -> float:
    if value is None or isinstance(value, bool):
        raise ValueError(f"Missing verified {label}")
    try:
        score = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid {label}: {value!r}") from exc
    if not 0 <= score <= 100:
        raise ValueError(f"{label} must be in [0, 100]")
    return score


def rank_2026_teams(teams: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Rank teams using 60% record, 32% optimal starters, 8% full roster.

    Input per team: roster_id, team_name, wins, losses, ties,
    projected_starters_c_avi (mean C-AVI of the optimal legal lineup),
    entire_roster_c_avi (mean C-AVI of all valued offensive players).
    The full-roster mean includes starters and bench, including injured players.
    K/IDP are excluded because the official offensive C-AVI does not value them.
    A team without verified values or a played game is not ranked.
    """
    ranked: list[dict[str, Any]] = []
    seen: set[int] = set()
    for team in teams:
        roster_id = int(team["roster_id"])
        if roster_id in seen:
            raise ValueError(f"Duplicate roster_id {roster_id}")
        seen.add(roster_id)
        wins, losses, ties = (int(team[key]) for key in ("wins", "losses", "ties"))
        if min(wins, losses, ties) < 0:
            raise ValueError(f"Negative record for roster {roster_id}")
        games = wins + losses + ties
        if not games:
            raise ValueError(f"No completed games for roster {roster_id}")
        record_score = 100 * (wins + 0.5 * ties) / games
        starters = _score(team.get("projected_starters_c_avi"), "starters C-AVI")
        roster = _score(team.get("entire_roster_c_avi"), "full-roster C-AVI")
        score = 0.60 * record_score + 0.32 * starters + 0.08 * roster
        ranked.append({
            "roster_id": roster_id,
            "team_name": str(team["team_name"]),
            "wins": wins, "losses": losses, "ties": ties,
            "record_score": round(record_score, 4),
            "projected_starters_c_avi": starters,
            "entire_roster_c_avi": roster,
            "power_score": round(score, 4),
        })
    ranked.sort(key=lambda t: (-t["power_score"], -t["record_score"], -t["projected_starters_c_avi"], t["roster_id"]))
    for index, team in enumerate(ranked, 1):
        team["rank"] = index
    return ranked
