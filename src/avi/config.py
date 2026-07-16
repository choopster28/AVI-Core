from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _integer(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


@dataclass(frozen=True)
class AviConfig:
    sleeper_league_id: str
    earliest_supported_season: int
    transaction_start_week: int
    transaction_end_week: int
    expected_team_count: int
    minimum_completed_trades: int

    fantasypros_api_key: str
    fantasypros_base_url: str
    fantasypros_api_key_header: str
    fantasypros_players_path: str
    fantasypros_projections_path: str
    fantasypros_rankings_path: str
    fantasypros_injuries_path: str
    fantasypros_news_path: str

    methodology_version: str


def load_config() -> AviConfig:
    sleeper_league_id = os.getenv("SLEEPER_LEAGUE_ID", "").strip()
    if sleeper_league_id and not sleeper_league_id.isdigit():
        raise RuntimeError("SLEEPER_LEAGUE_ID must contain numbers only.")

    start_week = _integer("TRANSACTION_START_WEEK", 0)
    end_week = _integer("TRANSACTION_END_WEEK", 18)
    if start_week < 0 or end_week < start_week:
        raise RuntimeError("Invalid transaction week range.")

    earliest = _integer("AVI_EARLIEST_SEASON", 2024)
    if earliest < 2000:
        raise RuntimeError("AVI_EARLIEST_SEASON must be a four-digit year.")

    return AviConfig(
        sleeper_league_id=sleeper_league_id,
        earliest_supported_season=earliest,
        transaction_start_week=start_week,
        transaction_end_week=end_week,
        expected_team_count=_integer("AVI_EXPECTED_TEAM_COUNT", 16),
        minimum_completed_trades=_integer("AVI_MINIMUM_COMPLETED_TRADES", 0),
        fantasypros_api_key=os.getenv("FANTASYPROS_API_KEY", "").strip(),
        fantasypros_base_url=os.getenv(
            "FANTASYPROS_BASE_URL", "https://api.fantasypros.com/v2"
        ).rstrip("/"),
        fantasypros_api_key_header=os.getenv(
            "FANTASYPROS_API_KEY_HEADER", "x-api-key"
        ).strip(),
        fantasypros_players_path=os.getenv("FANTASYPROS_PLAYERS_PATH", "").strip(),
        fantasypros_projections_path=os.getenv(
            "FANTASYPROS_PROJECTIONS_PATH", ""
        ).strip(),
        fantasypros_rankings_path=os.getenv("FANTASYPROS_RANKINGS_PATH", "").strip(),
        fantasypros_injuries_path=os.getenv("FANTASYPROS_INJURIES_PATH", "").strip(),
        fantasypros_news_path=os.getenv("FANTASYPROS_NEWS_PATH", "").strip(),
        methodology_version=os.getenv(
            "AVI_METHODOLOGY_VERSION", "current-approved"
        ).strip(),
    )
