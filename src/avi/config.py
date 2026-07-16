from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def read_integer(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()

    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(
            f"{name} must be an integer."
        ) from exc


@dataclass(frozen=True)
class AviConfig:
    sleeper_league_id: str
    earliest_supported_season: int
    transaction_start_week: int
    transaction_end_week: int
    expected_team_count: int
    minimum_completed_trades: int

    avi_season: int
    avi_scoring: str
    methodology_version: str

    fantasypros_api_key: str
    fantasypros_base_url: str
    fantasypros_api_key_header: str


def load_config() -> AviConfig:
    sleeper_league_id = os.getenv(
        "SLEEPER_LEAGUE_ID",
        "",
    ).strip()

    if sleeper_league_id and not sleeper_league_id.isdigit():
        raise RuntimeError(
            "SLEEPER_LEAGUE_ID must contain numbers only."
        )

    transaction_start_week = read_integer(
        "TRANSACTION_START_WEEK",
        0,
    )

    transaction_end_week = read_integer(
        "TRANSACTION_END_WEEK",
        18,
    )

    if transaction_start_week < 0:
        raise RuntimeError(
            "TRANSACTION_START_WEEK cannot be negative."
        )

    if transaction_end_week < transaction_start_week:
        raise RuntimeError(
            "TRANSACTION_END_WEEK cannot be before "
            "TRANSACTION_START_WEEK."
        )

    earliest_supported_season = read_integer(
        "AVI_EARLIEST_SEASON",
        2024,
    )

    if earliest_supported_season < 2000:
        raise RuntimeError(
            "AVI_EARLIEST_SEASON must be a four-digit year."
        )

    avi_scoring = os.getenv(
        "AVI_SCORING",
        "HALF",
    ).strip().upper()

    valid_scoring_values = {
        "STD",
        "HALF",
        "PPR",
    }

    if avi_scoring not in valid_scoring_values:
        raise RuntimeError(
            "AVI_SCORING must be STD, HALF, or PPR."
        )

    return AviConfig(
        sleeper_league_id=sleeper_league_id,
        earliest_supported_season=earliest_supported_season,
        transaction_start_week=transaction_start_week,
        transaction_end_week=transaction_end_week,
        expected_team_count=read_integer(
            "AVI_EXPECTED_TEAM_COUNT",
            16,
        ),
        minimum_completed_trades=read_integer(
            "AVI_MINIMUM_COMPLETED_TRADES",
            61,
        ),
        avi_season=read_integer(
            "AVI_SEASON",
            2026,
        ),
        avi_scoring=avi_scoring,
        methodology_version=os.getenv(
            "AVI_METHODOLOGY_VERSION",
            "2026.1",
        ).strip(),
        fantasypros_api_key=os.getenv(
            "FANTASYPROS_API_KEY",
            "",
        ).strip(),
        fantasypros_base_url=os.getenv(
            "FANTASYPROS_BASE_URL",
            "https://api.fantasypros.com/public/v2",
        ).rstrip("/"),
        fantasypros_api_key_header=os.getenv(
            "FANTASYPROS_API_KEY_HEADER",
            "x-api-key",
        ).strip(),
    )