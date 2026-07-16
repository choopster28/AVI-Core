from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from avi.sleeper.client import SleeperClient


@dataclass(frozen=True)
class LeagueSeason:
    league_id: str
    season: int
    previous_league_id: str | None
    league_data: dict[str, Any]


def _previous(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return None if not text or text == "0" else text


def discover(
    client: SleeperClient,
    current_league_id: str,
    earliest_season: int,
) -> list[LeagueSeason]:
    found: list[LeagueSeason] = []
    visited: set[str] = set()
    league_id: str | None = current_league_id

    while league_id:
        if league_id in visited:
            raise RuntimeError(f"League history cycle detected at {league_id}.")
        visited.add(league_id)

        data = client.league(league_id)
        season_text = str(data.get("season", "")).strip()
        if not season_text.isdigit():
            raise RuntimeError(f"Invalid season for league {league_id}.")
        season = int(season_text)
        previous = _previous(data.get("previous_league_id"))

        if season < earliest_season:
            break

        found.append(
            LeagueSeason(
                league_id=league_id,
                season=season,
                previous_league_id=previous,
                league_data=data,
            )
        )
        league_id = previous

    if not found:
        raise RuntimeError("No supported Sleeper seasons discovered.")

    return sorted(found, key=lambda row: (row.season, row.league_id))
