from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AviConfig:
    league_id: str
    season: int
    transaction_start_week: int
    transaction_end_week: int


def load_config() -> AviConfig:
    league_id = os.getenv("SLEEPER_LEAGUE_ID", "").strip()

    if not league_id:
        raise RuntimeError(
            "SLEEPER_LEAGUE_ID is not set."
        )

    if not league_id.isdigit():
        raise RuntimeError(
            "SLEEPER_LEAGUE_ID must contain numbers only."
        )

    try:
        season = int(os.getenv("AVI_SEASON", "2026"))
        start_week = int(
            os.getenv("TRANSACTION_START_WEEK", "0")
        )
        end_week = int(
            os.getenv("TRANSACTION_END_WEEK", "18")
        )
    except ValueError as exc:
        raise RuntimeError(
            "Season and transaction weeks must be integers."
        ) from exc

    if start_week < 0:
        raise RuntimeError(
            "TRANSACTION_START_WEEK cannot be negative."
        )

    if end_week < start_week:
        raise RuntimeError(
            "TRANSACTION_END_WEEK cannot be before the start week."
        )

    return AviConfig(
        league_id=league_id,
        season=season,
        transaction_start_week=start_week,
        transaction_end_week=end_week,
    )