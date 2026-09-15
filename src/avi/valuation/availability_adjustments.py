from __future__ import annotations

from pathlib import Path
from typing import Any

from avi.io import read_json, write_json
from avi.valuation.calculator import DAVIComponents, calculate_d_avi


AVI_PLAYERS_PATH = Path("data/processed/avi/avi_players.json")
AVI_MANIFEST_PATH = Path("data/processed/avi/manifest.json")
REGISTRY_PATH = Path("data/processed/identity/avi_player_registry.json")
SLEEPER_PLAYERS_PATH = Path("data/raw/sleeper/nfl_players.json")
FANTASYPROS_INJURIES_PATH = Path("data/raw/fantasypros/injuries.json")

FANTASY_CHAMPIONSHIP_END_WEEK = 17


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", " ").replace("-", " ")


def _registry_maps() -> tuple[dict[str, str], dict[str, str]]:
    registry = read_json(REGISTRY_PATH)
    if not isinstance(registry, list):
        raise RuntimeError("AVI registry must contain a list.")

    by_sleeper: dict[str, str] = {}
    by_fantasypros: dict[str, str] = {}
    for record in registry:
        if not isinstance(record, dict):
            continue
        avi_id = record.get("avi_id")
        source_ids = record.get("source_ids")
        if not avi_id or not isinstance(source_ids, dict):
            continue
        sleeper_id = source_ids.get("sleeper_id")
        fantasypros_id = source_ids.get("fantasypros_id")
        if sleeper_id is not None:
            by_sleeper[str(sleeper_id)] = str(avi_id)
        if fantasypros_id is not None:
            by_fantasypros[str(fantasypros_id)] = str(avi_id)
    return by_sleeper, by_fantasypros


def _load_injury_state() -> dict[str, dict[str, Any]]:
    """Merge Sleeper and FantasyPros injury/availability signals by AVI ID."""
    by_sleeper, by_fantasypros = _registry_maps()
    merged: dict[str, dict[str, Any]] = {}

    if SLEEPER_PLAYERS_PATH.exists():
        sleeper = read_json(SLEEPER_PLAYERS_PATH)
        if isinstance(sleeper, dict):
            for sleeper_id, record in sleeper.items():
                if not isinstance(record, dict):
                    continue
                avi_id = by_sleeper.get(str(sleeper_id))
                if not avi_id:
                    continue
                merged.setdefault(avi_id, {})["sleeper"] = {
                    "injury_status": record.get("injury_status"),
                    "status": record.get("status"),
                    "practice_participation": record.get("practice_participation"),
                    "news_updated": record.get("news_updated"),
                }

    if FANTASYPROS_INJURIES_PATH.exists():
        payload = read_json(FANTASYPROS_INJURIES_PATH)
        injuries = payload.get("injuries") if isinstance(payload, dict) else None
        if isinstance(injuries, list):
            for record in injuries:
                if not isinstance(record, dict):
                    continue
                player_id = record.get("player_id")
                avi_id = by_fantasypros.get(str(player_id)) if player_id is not None else None
                if not avi_id:
                    continue
                merged.setdefault(avi_id, {})["fantasypros"] = record

    return merged


def _status_text(state: dict[str, Any]) -> str:
    sleeper = state.get("sleeper") if isinstance(state.get("sleeper"), dict) else {}
    fantasypros = state.get("fantasypros") if isinstance(state.get("fantasypros"), dict) else {}
    pieces = [
        sleeper.get("injury_status"),
        sleeper.get("status"),
        fantasypros.get("status"),
        fantasypros.get("status_short"),
        fantasypros.get("injury_type"),
        fantasypros.get("practice_report_injury_type"),
    ]
    return " ".join(_norm(piece) for piece in pieces if piece)


def _comment_text(state: dict[str, Any]) -> str:
    fantasypros = state.get("fantasypros") if isinstance(state.get("fantasypros"), dict) else {}
    return _norm(fantasypros.get("comment"))


def _future_ir_weeks(state: dict[str, Any], current_week: int) -> float:
    fantasypros = state.get("fantasypros") if isinstance(state.get("fantasypros"), dict) else {}
    raw = fantasypros.get("ir_weeks")
    if not isinstance(raw, list):
        return 0.0
    weeks: set[int] = set()
    for value in raw:
        try:
            week = int(value)
        except (TypeError, ValueError):
            continue
        if current_week <= week <= FANTASY_CHAMPIONSHIP_END_WEEK:
            weeks.add(week)
    return float(len(weeks))


def _expected_missed_weeks(state: dict[str, Any], current_week: int) -> tuple[float, str]:
    """Estimate future missed fantasy weeks from explicit availability signals.

    This deliberately avoids trying to infer missed time from the projection
    itself. The projection is allowed to move independently; the downstream cap
    only acts when the current C-AVI still exceeds the maximum contribution that
    the verified availability window can support.
    """
    remaining = max(FANTASY_CHAMPIONSHIP_END_WEEK - current_week + 1, 0)
    if remaining <= 0:
        return 0.0, "season_complete"

    status = _status_text(state)
    comment = _comment_text(state)
    ir_weeks = _future_ir_weeks(state, current_week)

    if any(phrase in comment for phrase in ("season ending", "season-ending", "out for season", "remainder of the season", "miss the rest of the season")):
        return float(remaining), "season_ending"

    status_tokens = set(status.split())
    hard_ir = (
        "injured reserve" in status
        or "reserve injured" in status
        or "ir" in status_tokens
        or "pup" in status_tokens
        or "nfi" in status_tokens
    )
    if hard_ir:
        return min(float(remaining), max(4.0, ir_weeks)), "injured_reserve"

    if "out" in status_tokens or "out" in status:
        return min(1.0, float(remaining)), "out"

    fantasypros = state.get("fantasypros") if isinstance(state.get("fantasypros"), dict) else {}
    probability = _float(fantasypros.get("probability_of_playing"))
    if probability is not None:
        if probability > 1.0:
            probability /= 100.0
        probability = max(0.0, min(1.0, probability))

    if "doubtful" in status:
        missed = 1.0 - probability if probability is not None else 0.75
        return min(float(remaining), max(0.5, missed)), "doubtful"

    if "questionable" in status:
        missed = 1.0 - probability if probability is not None else 0.20
        return min(float(remaining), max(0.0, missed)), "questionable"

    if "probable" in status:
        missed = 1.0 - probability if probability is not None else 0.05
        return min(float(remaining), max(0.0, missed)), "probable"

    return 0.0, "healthy_or_no_actionable_designation"


def _availability_ceiling(current_week: int, expected_missed_weeks: float) -> float:
    remaining = max(FANTASY_CHAMPIONSHIP_END_WEEK - current_week + 1, 0)
    if remaining <= 0:
        return 100.0
    missed = max(0.0, min(float(remaining), float(expected_missed_weeks)))
    return round(100.0 * (remaining - missed) / remaining, 1)


def _apply_projection_aware_cap(current_cavi: float, ceiling: float) -> tuple[float, float]:
    """Return final C-AVI and delta without double-counting projection changes.

    The injury layer is a ceiling, not a multiplier. If projections/rankings have
    already reduced C-AVI below the availability ceiling, this layer applies no
    additional penalty. It only closes the residual gap when a stale/high
    projection still implies more championship contribution than the player can
    physically provide during the remaining fantasy horizon.
    """
    final = round(min(float(current_cavi), float(ceiling)), 1)
    return final, round(final - float(current_cavi), 1)


def apply_injury_availability_adjustments() -> dict[str, Any]:
    if not AVI_PLAYERS_PATH.exists() or not AVI_MANIFEST_PATH.exists() or not REGISTRY_PATH.exists():
        return {"status": "skipped", "reason": "required AVI files unavailable"}

    manifest = read_json(AVI_MANIFEST_PATH)
    players = read_json(AVI_PLAYERS_PATH)
    if not isinstance(manifest, dict) or not isinstance(players, list):
        raise RuntimeError("Invalid AVI availability-adjustment inputs.")

    transition = manifest.get("in_season_transition")
    transition = transition if isinstance(transition, dict) else {}
    try:
        current_week = int(transition.get("nfl_week") or 0)
    except (TypeError, ValueError):
        current_week = 0

    if manifest.get("season_phase") != "regular_season" or current_week < 1:
        manifest["injury_availability_adjustments"] = {
            "status": "inactive",
            "reason": "regular-season availability window is not active",
            "policy": "Projection-aware C-AVI ceiling; never multiply an already injury-adjusted projection.",
        }
        write_json(AVI_MANIFEST_PATH, manifest)
        return {"status": "inactive", "current_week": current_week}

    states = _load_injury_state()
    applied: list[dict[str, Any]] = []
    evaluated = 0

    for player in players:
        if not isinstance(player, dict):
            continue
        avi_id = str(player.get("avi_id") or "")
        state = states.get(avi_id)
        if not state:
            player.pop("c_avi_availability_adjustment", None)
            continue

        try:
            base_cavi = float(player.get("c_avi"))
        except (TypeError, ValueError):
            continue

        expected_missed, reason_code = _expected_missed_weeks(state, current_week)
        evaluated += 1
        if expected_missed <= 0:
            player.pop("c_avi_availability_adjustment", None)
            continue

        ceiling = _availability_ceiling(current_week, expected_missed)
        final_cavi, delta = _apply_projection_aware_cap(base_cavi, ceiling)
        status_text = _status_text(state).strip()

        adjustment = {
            "base_c_avi": round(base_cavi, 1),
            "availability_ceiling": ceiling,
            "amount": delta,
            "adjusted_c_avi": final_cavi,
            "expected_missed_weeks": round(expected_missed, 2),
            "current_week": current_week,
            "championship_horizon_end_week": FANTASY_CHAMPIONSHIP_END_WEEK,
            "reason_code": reason_code,
            "status": status_text,
            "projection_aware": True,
            "policy": "C-AVI is capped only when it remains above the maximum contribution implied by verified availability. If updated projections/rankings already move C-AVI below the cap, no additional injury penalty is applied.",
        }
        player["c_avi_availability_adjustment"] = adjustment
        if delta < 0:
            player["c_avi"] = final_cavi
            components = player.get("components")
            if isinstance(components, dict):
                components["base_c_avi_before_availability_adjustment"] = round(base_cavi, 1)
                components["c_avi_availability_adjustment"] = delta
                components["c_avi_availability_ceiling"] = ceiling
            applied.append({
                "avi_id": avi_id,
                "player_name": player.get("canonical_name"),
                "base_c_avi": round(base_cavi, 1),
                "adjustment": delta,
                "adjusted_c_avi": final_cavi,
                "availability_ceiling": ceiling,
                "expected_missed_weeks": round(expected_missed, 2),
                "reason_code": reason_code,
            })

    manifest["injury_availability_adjustments"] = {
        "status": "active",
        "current_week": current_week,
        "championship_horizon_end_week": FANTASY_CHAMPIONSHIP_END_WEEK,
        "players_evaluated": evaluated,
        "players_capped": len(applied),
        "policy": "Projection-aware C-AVI ceiling. Updated projections/rankings get first chance to price the injury; the availability layer only caps residual overstatement and therefore does not multiply an already reduced projection.",
        "sources": ["Sleeper NFL player injury status", "FantasyPros injuries"],
    }

    write_json(AVI_PLAYERS_PATH, players)
    write_json(AVI_MANIFEST_PATH, manifest)
    return {"status": "passed", "evaluated": evaluated, "applied": applied}


def recalculate_davi_from_final_cavi() -> dict[str, Any]:
    """Recalculate D-AVI after all C-AVI availability/risk adjustments.

    D-AVI only gives current C-AVI a 10% weight, so normal short-term injuries
    have a deliberately smaller dynasty effect while the championship index can
    react materially to current availability.
    """
    if not AVI_PLAYERS_PATH.exists():
        return {"status": "skipped", "reason": "AVI players unavailable"}

    players = read_json(AVI_PLAYERS_PATH)
    if not isinstance(players, list):
        raise RuntimeError("AVI players file must contain a list.")

    changed = 0
    for player in players:
        if not isinstance(player, dict):
            continue
        components = player.get("components")
        if not isinstance(components, dict):
            continue
        current_cavi = _float(player.get("c_avi"))
        if current_cavi is None:
            continue

        d = {
            "dynasty_market": _float(components.get("dynasty_market")),
            "age_career_horizon": _float(components.get("age_career_horizon")),
            "long_term_security": _float(components.get("long_term_security")),
            "position_liquidity": _float(components.get("position_liquidity")),
            "health_outlook": _float(components.get("health_outlook")),
            "long_term_ceiling": _float(components.get("long_term_ceiling")),
        }
        new_davi = calculate_d_avi(
            DAVIComponents(
                dynasty_market=d["dynasty_market"],
                age_career_horizon=d["age_career_horizon"],
                long_term_security=d["long_term_security"],
                position_liquidity=d["position_liquidity"],
                current_c_avi=current_cavi,
                health_outlook=d["health_outlook"],
                long_term_ceiling=d["long_term_ceiling"],
            )
        )
        if player.get("d_avi") != new_davi:
            player["d_avi"] = new_davi
            changed += 1

    write_json(AVI_PLAYERS_PATH, players)
    return {"status": "passed", "players_recalculated": changed}
