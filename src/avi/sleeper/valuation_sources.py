"""Sleeper-first source ingestion with field-level FantasyPros fallback.

Sleeper's stats/projections endpoints are not part of the stable public league API.
Never fail the daily update when they disappear or return an unexpected shape.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import requests

from avi.io import read_json, write_json

RAW = Path("data/raw/sleeper")
BASE = "https://api.sleeper.app/v1"
POSITIONS = {"QB", "RB", "WR", "TE", "K"}
SEASON = 2026


def _valid_points(value: Any) -> float | None:
    try:
        result = float(value)
        return result if -30 <= result <= 800 else None
    except (TypeError, ValueError):
        return None


def _extract_map(payload: Any) -> dict[str, dict[str, Any]]:
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), dict):
            payload = payload["data"]
        return {str(k): v for k, v in payload.items() if isinstance(v, dict)}
    if isinstance(payload, list):
        return {
            str(row.get("player_id")): row
            for row in payload
            if isinstance(row, dict) and row.get("player_id") is not None
        }
    return {}


def _points(record: dict[str, Any]) -> float | None:
    stats = record.get("stats")
    values = stats if isinstance(stats, dict) else record
    for key in ("pts_ppr", "points_ppr"):
        if key in values:
            return _valid_points(values[key])
    return None


def _fetch(session: requests.Session, url: str) -> dict[str, dict[str, Any]]:
    response = session.get(url, timeout=15)
    response.raise_for_status()
    payload = _extract_map(response.json())
    if len(payload) < 40:
        raise ValueError(f"Implausibly small Sleeper feed ({len(payload)} records)")
    return payload


def update_sleeper_valuation_sources() -> dict[str, Any]:
    """Cache usable Sleeper feeds; absent feeds explicitly leave FantasyPros in control."""
    session = requests.Session()
    status: dict[str, Any] = {"status": "passed", "season": SEASON, "feeds": {}}
    # Do not make eighteen unnecessary HTTP requests during early season.
    # NFL state is the same canonical clock used by the in-season transition.
    try:
        state = session.get(f"{BASE}/state/nfl", timeout=15)
        state.raise_for_status()
        week = int(state.json().get("week") or 1)
        current_week = max(1, min(18, week))
    except (requests.RequestException, ValueError, TypeError, AttributeError):
        current_week = 18  # conservative coverage when league clock is unavailable
    for kind in ("stats", "projections"):
        weeks = range(1, current_week + 1) if kind == "stats" else (None,)
        for week in weeks:
            key = f"{kind}_week_{week}" if week is not None else "projections_season"
            url = f"{BASE}/{kind}/nfl/regular/{SEASON}"
            if week is not None:
                url += f"/{week}"
            try:
                payload = _fetch(session, url)
                valid = sum(
                    1 for value in payload.values() if _points(value) is not None
                )
                if valid < 40:
                    raise ValueError(f"Too few usable PPR values: {valid}")
                write_json(RAW / "valuation" / f"{key}.json", {
                    "fetched_at_utc": datetime.now(UTC).isoformat(),
                    "season": SEASON, "week": week, "players": payload,
                })
                status["feeds"][key] = {"status": "sleeper", "valid_players": valid}
            except (requests.RequestException, ValueError, TypeError) as exc:
                # Remove outdated snapshots for failed fetches: unavailable Sleeper
                # input must not accidentally outrank fresh FantasyPros input.
                path = RAW / "valuation" / f"{key}.json"
                path.unlink(missing_ok=True)
                status["feeds"][key] = {
                    "status": "fantasypros_fallback", "reason": type(exc).__name__,
                }
    write_json(RAW / "valuation" / "manifest.json", status)
    return status


def load_sleeper_weekly_points(completed_through: int) -> dict[str, dict[int, float]]:
    """Only return weeks with explicit non-null Sleeper PPR values."""
    by_id: dict[str, dict[int, float]] = {}
    for week in range(1, completed_through + 1):
        path = RAW / "valuation" / f"stats_week_{week}.json"
        if not path.exists():
            continue
        data = read_json(path)
        if not isinstance(data, dict) or data.get("season") != SEASON or data.get("week") != week:
            continue
        for sleeper_id, record in _extract_map(data.get("players")).items():
            points = _points(record)
            if points is not None:
                by_id.setdefault(sleeper_id, {})[week] = points
    return by_id


def load_sleeper_season_projections() -> dict[str, float]:
    path = RAW / "valuation" / "projections_season.json"
    if not path.exists():
        return {}
    data = read_json(path)
    if not isinstance(data, dict) or data.get("season") != SEASON:
        return {}
    return {
        sleeper_id: points
        for sleeper_id, record in _extract_map(data.get("players")).items()
        if (points := _points(record)) is not None and points >= 0
    }
