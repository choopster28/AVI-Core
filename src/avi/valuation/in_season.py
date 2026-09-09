from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
import json

from avi.io import read_json, write_json
from avi.valuation.calculator import CAVIComponents, DAVIComponents, calculate_c_avi, calculate_d_avi
from avi.valuation.scaling import percentile_score


AVI_PLAYERS_PATH = Path("data/processed/avi/avi_players.json")
AVI_MANIFEST_PATH = Path("data/processed/avi/manifest.json")
REGISTRY_PATH = Path("data/processed/identity/avi_player_registry.json")
PLAYER_POINTS_ROOT = Path("data/raw/fantasypros/player_points")

OFFENSIVE_POSITIONS = ("QB", "RB", "WR", "TE", "K")
SLEEPER_STATE_URL = "https://api.sleeper.app/v1/state/nfl"
TARGET_SEASON = 2026


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _nfl_state() -> dict[str, Any]:
    request = Request(SLEEPER_STATE_URL, headers={"User-Agent": "AVI-Core/2026.2"})
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


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

            weeks = record.get("weeks")
            if isinstance(weeks, dict):
                for raw_week in weeks:
                    try:
                        max_week = max(max_week, int(raw_week))
                    except (TypeError, ValueError):
                        pass

            points = _float(record.get("points"))
            games = _float(record.get("games"))
            if points is None:
                points = 0.0
            if games is None:
                games = 0.0

            avi_id = str(registry_player.get("avi_id"))
            by_avi[avi_id] = {
                "avi_id": avi_id,
                "position": str(registry_player.get("position") or position).upper(),
                "raw_points": points,
                "games": games,
            }
            mapped_records += 1

    return by_avi, max_week, mapped_records


def _fresh_completed_week_available(state: dict[str, Any], max_observed_week: int, mapped_records: int) -> tuple[bool, int]:
    season = int(state.get("season") or 0)
    season_type = str(state.get("season_type") or "").lower()
    current_week = int(state.get("week") or 0)

    if season != TARGET_SEASON or season_type not in {"regular", "post"} or current_week < 1:
        return False, 0

    # Do not activate on a tiny/partial response. The AVI registry normally maps
    # hundreds of offensive players, so this threshold is intentionally modest.
    if mapped_records < 40:
        return False, 0

    if season_type == "regular":
        # Only consume completed weeks. During Week 1 there are no completed 2026
        # games yet. A stale prior-season payload with weeks through 17/18 also fails
        # this test rather than being mistaken for current production.
        completed_through = current_week - 1
        fresh = completed_through >= 1 and 1 <= max_observed_week <= completed_through
        return fresh, completed_through

    # Postseason: all regular-season weeks are complete.
    return max_observed_week >= 1, max_observed_week


def _player_point_components(points: dict[str, dict[str, Any]]) -> dict[str, float]:
    fields: dict[str, list[float]] = {}
    for record in points.values():
        fields.setdefault(record["position"], []).append(float(record["raw_points"]))

    result: dict[str, float] = {}
    for avi_id, record in points.items():
        field = fields.get(record["position"], [])
        if field:
            result[avi_id] = round(percentile_score(float(record["raw_points"]), field), 1)
    return result


def apply_in_season_transition() -> dict[str, Any]:
    """Transition C-AVI globally from preseason to the approved in-season mix.

    The base 2026.2 model already defines the in-season C-AVI weights as 10%
    actual player points, 40% refreshed projections, 10% league context, 30%
    public market, and 10% elite upside. This postprocessor activates that mix
    only after a completed current-season week is verifiably present in the
    FantasyPros player-points feed.
    """
    if not AVI_PLAYERS_PATH.exists() or not AVI_MANIFEST_PATH.exists() or not REGISTRY_PATH.exists():
        return {"status": "skipped", "reason": "required AVI files unavailable"}

    state = _nfl_state()
    points, max_week, mapped_records = _load_current_points()
    active, completed_through = _fresh_completed_week_available(state, max_week, mapped_records)
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
        "activation_policy": "Use only verified completed 2026 regular-season weeks; stale or partial player-points feeds do not activate the transition.",
    }

    if not active:
        write_json(AVI_MANIFEST_PATH, manifest)
        return {"status": "waiting", **manifest["in_season_transition"]}

    players = read_json(AVI_PLAYERS_PATH)
    if not isinstance(players, list):
        raise RuntimeError("AVI players file must contain a list.")

    point_components = _player_point_components(points)
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
        upside = _float(components.get("elite_upside"))
        if None in {projection, context, market, upside}:
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
        point_record = points.get(avi_id)
        player["in_season_player_points"] = {
            "raw_points": round(float(point_record["raw_points"]), 2) if point_record else 0.0,
            "games": int(float(point_record["games"])) if point_record else 0,
            "component_score": actual_component,
            "completed_through_week": completed_through,
            "source": "FantasyPros current-season player points",
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
        player["methodology_status"] = "active_2026_2_in_season"
        changed += 1

    manifest["season_phase"] = "regular_season"
    manifest["player_points_active"] = True
    manifest["methodology_status"] = "active_2026_2_in_season"
    manifest["c_avi_weights"] = {
        "player_points": 0.10,
        "projections": 0.40,
        "league_context": 0.10,
        "public_market": 0.30,
        "elite_upside": 0.10,
    }

    write_json(AVI_PLAYERS_PATH, players)
    write_json(AVI_MANIFEST_PATH, manifest)
    return {
        "status": "passed",
        "players_recalculated": changed,
        "completed_through_week": completed_through,
        "weights": manifest["c_avi_weights"],
    }
