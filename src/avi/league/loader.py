from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from avi.io import read_json


LEAGUE_PATH = Path(
    "data/raw/sleeper/leagues"
)


@dataclass(frozen=True)
class LeagueStructure:
    league_id: str
    league_name: str
    season: int
    team_count: int
    roster_positions: tuple[str, ...]
    starter_counts: dict[str, int]
    bench_spots: int
    reserve_spots: int
    playoff_teams: int
    playoff_start_week: int
    trade_deadline_week: int
    scoring_settings: dict[str, float]


def find_current_league_file() -> Path:
    if not LEAGUE_PATH.exists():
        raise RuntimeError(
            "Sleeper league-history directory is missing. "
            "Run update-sleeper first."
        )

    league_files = list(
        LEAGUE_PATH.glob("*/league.json")
    )

    if not league_files:
        raise RuntimeError(
            "No Sleeper league.json files were found."
        )

    league_records: list[
        tuple[int, Path]
    ] = []

    for path in league_files:
        payload = read_json(path)

        season_text = str(
            payload.get("season", "")
        ).strip()

        if not season_text.isdigit():
            continue

        league_records.append(
            (
                int(season_text),
                path,
            )
        )

    if not league_records:
        raise RuntimeError(
            "No valid Sleeper league seasons were found."
        )

    league_records.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return league_records[0][1]


def normalize_starter_position(
    position: str,
) -> str:
    normalized = position.strip().upper()

    aliases = {
        "SUPER_FLEX": "SUPERFLEX",
        "REC_FLEX": "FLEX",
        "WRRB_FLEX": "FLEX",
        "WRRBTE_FLEX": "FLEX",
    }

    return aliases.get(
        normalized,
        normalized,
    )


def load_league_structure() -> LeagueStructure:
    league_file = find_current_league_file()
    payload: dict[str, Any] = read_json(
        league_file
    )

    roster_positions = tuple(
        normalize_starter_position(
            str(position)
        )
        for position in payload.get(
            "roster_positions",
            [],
        )
    )

    if not roster_positions:
        raise RuntimeError(
            "Sleeper league file has no roster positions."
        )

    non_starter_positions = {
        "BN",
        "IR",
        "TAXI",
    }

    starter_positions = [
        position
        for position in roster_positions
        if position not in non_starter_positions
    ]

    starter_counts = dict(
        Counter(starter_positions)
    )

    settings = payload.get(
        "settings",
        {},
    )

    scoring_settings = payload.get(
        "scoring_settings",
        {},
    )

    return LeagueStructure(
        league_id=str(
            payload.get("league_id", "")
        ),
        league_name=str(
            payload.get("name", "")
        ),
        season=int(
            payload.get("season")
        ),
        team_count=int(
            settings.get(
                "num_teams",
                payload.get(
                    "total_rosters",
                    0,
                ),
            )
        ),
        roster_positions=roster_positions,
        starter_counts=starter_counts,
        bench_spots=roster_positions.count(
            "BN"
        ),
        reserve_spots=int(
            settings.get(
                "reserve_slots",
                0,
            )
        ),
        playoff_teams=int(
            settings.get(
                "playoff_teams",
                0,
            )
        ),
        playoff_start_week=int(
            settings.get(
                "playoff_week_start",
                0,
            )
        ),
        trade_deadline_week=int(
            settings.get(
                "trade_deadline",
                0,
            )
        ),
        scoring_settings={
            str(key): float(value)
            for key, value
            in scoring_settings.items()
        },
    )