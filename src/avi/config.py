from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


def _int(
    name: str,
    default: int,
) -> int:
    raw = os.getenv(
        name,
        str(default),
    ).strip()

    try:
        return int(raw)
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
    regular_season_start_week: int
    fantasypros_api_key: str
    fantasypros_base_url: str
    fantasypros_api_key_header: str
    fantasypros_max_requests_per_run: int


def load_config() -> AviConfig:
    league_id = os.getenv(
        "SLEEPER_LEAGUE_ID",
        "",
    ).strip()

    if league_id and not league_id.isdigit():
        raise RuntimeError(
            "SLEEPER_LEAGUE_ID must contain numbers only."
        )

    scoring = os.getenv(
        "AVI_SCORING",
        "HALF",
    ).strip().upper()

    if scoring not in {
        "STD",
        "HALF",
        "PPR",
    }:
        raise RuntimeError(
            "AVI_SCORING must be STD, HALF, or PPR."
        )

    start = _int(
        "TRANSACTION_START_WEEK",
        0,
    )

    end = _int(
        "TRANSACTION_END_WEEK",
        18,
    )

    if start < 0 or end < start:
        raise RuntimeError(
            "Invalid transaction week range."
        )

    fantasypros_max_requests = _int(
        "FANTASYPROS_MAX_REQUESTS_PER_RUN",
        100,
    )

    if fantasypros_max_requests < 1:
        raise RuntimeError(
            "FANTASYPROS_MAX_REQUESTS_PER_RUN must be at least 1."
        )

    return AviConfig(
        sleeper_league_id=league_id,
        earliest_supported_season=_int(
            "AVI_EARLIEST_SEASON",
            2024,
        ),
        transaction_start_week=start,
        transaction_end_week=end,
        expected_team_count=_int(
            "AVI_EXPECTED_TEAM_COUNT",
            16,
        ),
        minimum_completed_trades=_int(
            "AVI_MINIMUM_COMPLETED_TRADES",
            61,
        ),
        avi_season=_int(
            "AVI_SEASON",
            2026,
        ),
        avi_scoring=scoring,
        methodology_version=os.getenv(
            "AVI_METHODOLOGY_VERSION",
            "2026.1",
        ).strip(),
        regular_season_start_week=_int(
            "AVI_REGULAR_SEASON_START_WEEK",
            1,
        ),
        fantasypros_api_key=os.getenv(
            "FANTASYPROS_API_KEY",
            "",
        ).strip(),
        fantasypros_base_url=os.getenv(
            "FANTASYPROS_BASE_URL",
            "https://api.fantasypros.com/public/v2/json",
        ).rstrip("/"),
        fantasypros_api_key_header=os.getenv(
            "FANTASYPROS_API_KEY_HEADER",
            "x-api-key",
        ).strip(),
        fantasypros_max_requests_per_run=(
            fantasypros_max_requests
        ),
    )