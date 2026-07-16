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


def normalize_previous_league_id(value: Any) -> str | None:
    if value is None:
        return None
    league_id = str(value).strip()
    if not league_id or league_id == "0":
        return None
    return league_id


def discover_league_history(
    client: SleeperClient,
    current_league_id: str,
    earliest_supported_season: int = 2024,
    maximum_seasons: int = 20,
) -> list[LeagueSeason]:
    discovered: list[LeagueSeason] = []
    visited: set[str] = set()
    league_id: str | None = current_league_id.strip()

    if not league_id:
        raise ValueError("current_league_id cannot be empty.")

    while league_id is not None:
        if league_id in visited:
            raise RuntimeError(f"League-history cycle detected at {league_id}.")
        if len(visited) >= maximum_seasons:
            raise RuntimeError(
                f"League history exceeded the configured maximum of {maximum_seasons}."
            )

        visited.add(league_id)
        league_data = client.get_league(league_id)
        if not isinstance(league_data, dict) or not league_data:
            raise RuntimeError(f"Unable to retrieve league metadata for {league_id}.")

        season_text = str(league_data.get("season", "")).strip()
        if not season_text.isdigit():
            raise RuntimeError(f"League {league_id} returned invalid season data.")

        season = int(season_text)
        previous = normalize_previous_league_id(
            league_data.get("previous_league_id")
        )

        if season < earliest_supported_season:
            break

        discovered.append(
            LeagueSeason(
                league_id=league_id,
                season=season,
                previous_league_id=previous,
                league_data=league_data,
            )
        )
        league_id = previous

    if not discovered:
        raise RuntimeError(
            f"No linked Sleeper seasons were found from {earliest_supported_season} onward."
        )

    discovered.sort(key=lambda item: (item.season, item.league_id))
    return discovered
