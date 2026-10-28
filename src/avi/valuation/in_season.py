from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from avi.io import read_json, write_json
from avi.sleeper.valuation_sources import load_sleeper_weekly_points
from avi.valuation.calculator import CAVIComponents, DAVIComponents, calculate_c_avi, calculate_d_avi


AVI_PLAYERS_PATH = Path("data/processed/avi/avi_players.json")
AVI_MANIFEST_PATH = Path("data/processed/avi/manifest.json")
REGISTRY_PATH = Path("data/processed/identity/avi_player_registry.json")
PLAYER_POINTS_ROOT = Path("data/raw/fantasypros/player_points")

OFFENSIVE_POSITIONS = ("QB", "RB", "WR", "TE", "K")
SLEEPER_STATE_URL = "https://api.sleeper.app/v1/state/nfl"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
TARGET_SEASON = 2026

# C-AVI should compare fantasy-relevant players against other fantasy-relevant
# players, not against the entire NFL depth chart. These pools are intentionally
# wider than a 16-team starting lineup so productive bench/flex options still
# retain meaningful value without deep reserves inflating the top end.
FANTASY_RELEVANT_POOL = {
    "QB": 24,
    "RB": 48,
    "WR": 64,
    "TE": 24,
    "K": 16,
}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "AVI-Core/2026.3"})
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def _nfl_state() -> dict[str, Any]:
    return _get_json(SLEEPER_STATE_URL)


def _espn_week_complete(week: int) -> bool | None:
    """Return True only when ESPN shows every regular-season game final."""
    if week < 1 or week > 18:
        return False

    query = urlencode({"seasontype": 2, "week": week, "year": TARGET_SEASON})
    try:
        payload = _get_json(f"{ESPN_SCOREBOARD_URL}?{query}")
    except Exception:
        return None

    events = payload.get("events")
    if not isinstance(events, list) or len(events) < 12:
        return None

    completed = 0
    for event in events:
        if not isinstance(event, dict):
            return None
        status = event.get("status")
        status_type = status.get("type") if isinstance(status, dict) else None
        if not isinstance(status_type, dict):
            return None
        if status_type.get("completed") is True:
            completed += 1

    return completed == len(events)


def _registry_by_fantasypros_id() -> dict[str, dict[str, Any]]:
    payload = read_json(REGISTRY_PATH)
    if not isinstance(payload, list):
        raise RuntimeError("AVI registry must contain a list.")
    result: dict[str, dict[str, Any]] = {}
    for player in payload:
        if not isinstance(player, dict):
            continue
        source_ids = player.get("source_ids")
        if not isinstance(source_ids, dict):
            continue
        fpid = source_ids.get("fantasypros_id")
        if fpid is not None:
            result[str(fpid)] = player
    return result


def _load_current_points() -> tuple[dict[str, dict[str, Any]], int, int]:
    registry = _registry_by_fantasypros_id()
    by_avi: dict[str, dict[str, Any]] = {}
    max_week = 0
    mapped_records = 0

    for position in OFFENSIVE_POSITIONS:
        path = PLAYER_POINTS_ROOT / f"{position}.json"
        if not path.exists():
            continue
        payload = read_json(path)
        if not isinstance(payload, dict) or not isinstance(payload.get("players"), list):
            continue

        for record in payload["players"]:
            if not isinstance(record, dict):
                continue
            fpid = record.get("player_id")
            registry_player = registry.get(str(fpid)) if fpid is not None else None
            if not registry_player:
                continue

            parsed_weeks: dict[int, float] = {}
            weeks = record.get("weeks")
            if isinstance(weeks, dict):
                for raw_week, raw_value in weeks.items():
                    try:
                        week = int(raw_week)
                    except (TypeError, ValueError):
                        continue
                    value = _float(raw_value)
                    if value is None:
                        continue
                    parsed_weeks[week] = value
                    max_week = max(max_week, week)

            season_points = _float(record.get("points")) or 0.0
            games = _float(record.get("games")) or 0.0
            average = _float(record.get("average"))
            if average is None:
                average = season_points / games if games > 0 else 0.0

            avi_id = str(registry_player.get("avi_id"))
            by_avi[avi_id] = {
                "avi_id": avi_id,
                "position": str(registry_player.get("position") or position).upper(),
                "raw_points": average,
                "season_points": season_points,
                "games": games,
                "weekly_ceiling": max(parsed_weeks.values()) if parsed_weeks else 0.0,
                "weeks": parsed_weeks,
            }
            mapped_records += 1

    return by_avi, max_week, mapped_records


def _fresh_completed_week_available(
    state: dict[str, Any],
    max_observed_week: int,
    mapped_records: int,
    current_week_complete: bool | None = None,
) -> tuple[bool, int]:
    season = int(state.get("season") or 0)
    season_type = str(state.get("season_type") or "").lower()
    current_week = int(state.get("week") or 0)

    if season != TARGET_SEASON or season_type not in {"regular", "post"} or current_week < 1:
        return False, 0
    if mapped_records < 40:
        return False, 0

    if season_type == "regular":
        if max_observed_week < 1 or max_observed_week > current_week:
            completed_through = max(current_week - 1, 0)
            return False, completed_through

        if max_observed_week <= current_week - 1:
            return True, max_observed_week

        if max_observed_week == current_week and current_week_complete is True:
            return True, current_week

        # FantasyPros can begin publishing Thursday/Sunday production before the
        # NFL week is complete. Do not disable the entire in-season model because
        # a partial current week exists; simply ignore that week and retain all
        # verified production through the prior completed week.
        completed_through = max(current_week - 1, 0)
        return completed_through >= 1, completed_through

    return max_observed_week >= 1, max_observed_week


def _completed_points(
    points: dict[str, dict[str, Any]], completed_through: int
) -> dict[str, dict[str, Any]]:
    """Trim the FantasyPros feed to verified completed weeks only."""
    result: dict[str, dict[str, Any]] = {}
    for avi_id, record in points.items():
        raw_weeks = record.get("weeks")
        weeks = raw_weeks if isinstance(raw_weeks, dict) else {}
        completed = {
            int(week): float(value)
            for week, value in weeks.items()
            if int(week) <= completed_through
        }
        season_points = sum(completed.values())
        games = len(completed)
        average = season_points / games if games else 0.0
        result[avi_id] = {
            **record,
            "weeks": completed,
            "raw_points": average,
            "season_points": season_points,
            "games": float(games),
            "weekly_ceiling": max(completed.values()) if completed else 0.0,
        }
    # Sleeper takes precedence independently for each completed player/week.
    # A missing Sleeper player/week retains the FantasyPros observation.
    registry = read_json(REGISTRY_PATH)
    sleeper_to_avi = {
        str(row["source_ids"]["sleeper_id"]): str(row["avi_id"])
        for row in registry
        if isinstance(row, dict) and isinstance(row.get("source_ids"), dict)
        and row["source_ids"].get("sleeper_id") is not None
    } if isinstance(registry, list) else {}
    sleeper_points = load_sleeper_weekly_points(completed_through)
    for sleeper_id, weekly in sleeper_points.items():
        avi_id = sleeper_to_avi.get(sleeper_id)
        if not avi_id or avi_id not in result:
            continue
        original = result[avi_id]
        merged = dict(original["weeks"])
        merged.update(weekly)
        original["weeks"] = merged
        original["season_points"] = sum(merged.values())
        original["games"] = float(len(merged))
        original["raw_points"] = original["season_points"] / len(merged) if merged else 0.0
        original["weekly_ceiling"] = max(merged.values()) if merged else 0.0
        original["production_source"] = "sleeper" if len(weekly) == len(merged) else "mixed_sleeper_fantasypros"
    for original in result.values():
        original.setdefault("production_source", "fantasypros")
    return result


def _rank_scores(records: dict[str, dict[str, Any]], field_name: str) -> dict[str, float]:
    """Rank a metric within each position's fantasy-relevant pool."""
    by_position: dict[str, list[tuple[str, float]]] = {}
    for avi_id, record in records.items():
        position = str(record.get("position") or "").upper()
        value = _float(record.get(field_name))
        if position not in FANTASY_RELEVANT_POOL or value is None:
            continue
        by_position.setdefault(position, []).append((avi_id, float(value)))

    result: dict[str, float] = {}
    for position, entries in by_position.items():
        entries.sort(key=lambda item: item[1], reverse=True)
        pool_size = min(FANTASY_RELEVANT_POOL[position], len(entries))
        if pool_size <= 1:
            for avi_id, _ in entries:
                result[avi_id] = 100.0 if pool_size == 1 else 0.0
            continue

        index = 0
        while index < len(entries):
            value = entries[index][1]
            end = index
            while end + 1 < len(entries) and entries[end + 1][1] == value:
                end += 1
            average_rank = ((index + 1) + (end + 1)) / 2.0
            score = 0.0 if average_rank > pool_size else 100.0 * (pool_size - average_rank) / (pool_size - 1)
            score = round(max(0.0, min(100.0, score)), 1)
            for tied_index in range(index, end + 1):
                result[entries[tied_index][0]] = score
            index = end + 1

    return result


def _player_point_components(points: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Blend PPR/game and season production inside a fantasy-relevant pool."""
    ppg = _rank_scores(points, "raw_points")
    total = _rank_scores(points, "season_points")
    result: dict[str, float] = {}
    for avi_id in points:
        ppg_score = ppg.get(avi_id, 0.0)
        total_score = total.get(avi_id, 0.0)
        result[avi_id] = round(0.70 * ppg_score + 0.30 * total_score, 1)
    return result


def _weekly_ceiling_components(points: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Score demonstrated weekly ceiling inside the fantasy-relevant pool."""
    return _rank_scores(points, "weekly_ceiling")


def apply_in_season_transition() -> dict[str, Any]:
    """Transition C-AVI globally from preseason to the approved in-season mix."""
    if not AVI_PLAYERS_PATH.exists() or not AVI_MANIFEST_PATH.exists() or not REGISTRY_PATH.exists():
        return {"status": "skipped", "reason": "required AVI files unavailable"}

    state = _nfl_state()
    points, max_week, mapped_records = _load_current_points()

    current_week_complete: bool | None = None
    current_week = int(state.get("week") or 0)
    season_type = str(state.get("season_type") or "").lower()
    if season_type == "regular" and max_week == current_week and current_week >= 1:
        current_week_complete = _espn_week_complete(current_week)

    active, completed_through = _fresh_completed_week_available(
        state,
        max_week,
        mapped_records,
        current_week_complete=current_week_complete,
    )
    manifest = read_json(AVI_MANIFEST_PATH)
    if not isinstance(manifest, dict):
        raise RuntimeError("AVI manifest must contain an object.")

    manifest["in_season_transition"] = {
        "status": "active" if active else "waiting_for_completed_current_season_points",
        "nfl_season": state.get("season"),
        "nfl_season_type": state.get("season_type"),
        "nfl_week": state.get("week"),
        "completed_through_week": completed_through,
        "fantasypros_max_observed_week": max_week,
        "mapped_player_point_records": mapped_records,
        "current_week_schedule_complete": current_week_complete,
        "completion_sources": ["Sleeper NFL state", "ESPN NFL scoreboard"],
        "production_source_priority": ["sleeper", "fantasypros"],
        "activation_policy": "Use every verified completed 2026 week. If FantasyPros has begun publishing an incomplete current week, ignore that partial week rather than reverting C-AVI to preseason values.",
    }

    if not active:
        write_json(AVI_MANIFEST_PATH, manifest)
        return {"status": "waiting", **manifest["in_season_transition"]}

    players = read_json(AVI_PLAYERS_PATH)
    if not isinstance(players, list):
        raise RuntimeError("AVI players file must contain a list.")

    completed_points = _completed_points(points, completed_through)
    point_components = _player_point_components(completed_points)
    weekly_ceiling_components = _weekly_ceiling_components(completed_points)
    changed = 0
    for player in players:
        if not isinstance(player, dict):
            continue
        position = str(player.get("position") or "").upper()
        if position not in OFFENSIVE_POSITIONS:
            continue
        components = player.get("components")
        if not isinstance(components, dict):
            continue

        avi_id = str(player.get("avi_id"))
        actual_component = point_components.get(avi_id, 0.0)
        projection = _float(components.get("projection"))
        context = _float(components.get("league_context"))
        market = _float(components.get("public_market"))
        existing_upside = _float(components.get("elite_upside"))
        upside = weekly_ceiling_components.get(avi_id, existing_upside if existing_upside is not None else 0.0)
        if None in {projection, context, market}:
            continue

        new_cavi = calculate_c_avi(
            CAVIComponents(
                player_points=actual_component,
                projections=float(projection),
                league_context=float(context),
                public_market=float(market),
                elite_upside=float(upside),
            ),
            player_points_active=True,
        )
        player["c_avi"] = new_cavi
        components["player_points"] = actual_component
        point_record = completed_points.get(avi_id)
        components["elite_upside"] = upside
        player.setdefault("data_sources", {})["production"] = point_record.get("production_source", "fantasypros") if point_record else "unavailable"
        player["in_season_player_points"] = {
            "ppr_points_per_game": round(float(point_record["raw_points"]), 2) if point_record else 0.0,
            "season_points": round(float(point_record.get("season_points") or 0.0), 2) if point_record else 0.0,
            "games": int(float(point_record["games"])) if point_record else 0,
            "component_score": actual_component,
            "weekly_ceiling_points": round(float(point_record.get("weekly_ceiling") or 0.0), 2) if point_record else 0.0,
            "weekly_ceiling_component": upside,
            "completed_through_week": completed_through,
            "source": point_record.get("production_source", "fantasypros") if point_record else "unavailable",
        }

        d_components = {
            "dynasty_market": _float(components.get("dynasty_market")),
            "age_career_horizon": _float(components.get("age_career_horizon")),
            "long_term_security": _float(components.get("long_term_security")),
            "position_liquidity": _float(components.get("position_liquidity")),
            "health_outlook": _float(components.get("health_outlook")),
            "long_term_ceiling": _float(components.get("long_term_ceiling")),
        }
        player["d_avi"] = calculate_d_avi(
            DAVIComponents(
                dynasty_market=d_components["dynasty_market"],
                age_career_horizon=d_components["age_career_horizon"],
                long_term_security=d_components["long_term_security"],
                position_liquidity=d_components["position_liquidity"],
                current_c_avi=new_cavi,
                health_outlook=d_components["health_outlook"],
                long_term_ceiling=d_components["long_term_ceiling"],
            )
        )
        player["season_phase"] = "regular_season"
        player["methodology_status"] = "active_2026_3_in_season"
        changed += 1

    manifest["season_phase"] = "regular_season"
    manifest["player_points_active"] = True
    manifest["methodology_status"] = "active_2026_3_in_season"
    manifest["methodology_version"] = "2026.3"
    manifest["c_avi_weights"] = {
        "player_points": 0.40,
        "projections": 0.25,
        "league_context": 0.10,
        "public_market": 0.15,
        "elite_upside": 0.10,
    }
    manifest["production_component_policy"] = {
        "player_points": "70% PPR points/game rank + 30% season-points rank within a fantasy-relevant positional pool",
        "weekly_ceiling": "best completed-week PPR rank within the same fantasy-relevant positional pool",
        "fantasy_relevant_pool": FANTASY_RELEVANT_POOL,
    }

    write_json(AVI_PLAYERS_PATH, players)
    write_json(AVI_MANIFEST_PATH, manifest)
    return {
        "status": "passed",
        "players_recalculated": changed,
        "completed_through_week": completed_through,
        "weights": manifest["c_avi_weights"],
    }
