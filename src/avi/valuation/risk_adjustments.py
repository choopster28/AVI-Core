from __future__ import annotations

from pathlib import Path
from typing import Any

from avi.io import read_json, write_json
from avi.valuation.scaling import clamp


AVI_PLAYERS_PATH = Path("data/processed/avi/avi_players.json")
RISK_ADJUSTMENTS_PATH = Path("data/manual/cavi_risk_adjustments.json")


def apply_cavi_risk_adjustments() -> dict[str, Any]:
    """Apply transparent, exceptional current-season risk adjustments.

    These adjustments exist for material championship-value risks that are not
    represented in the projection/ranking-only C-AVI inputs. They are applied
    after the base model runs and before downstream team/player reports are
    generated, so every consumer sees the same adjusted value.

    The operation is idempotent. If the same adjustment has already been
    applied, the stored pre-adjustment C-AVI is reused rather than subtracting
    the adjustment a second time.
    """
    if not AVI_PLAYERS_PATH.exists() or not RISK_ADJUSTMENTS_PATH.exists():
        return {"status": "skipped", "applied": []}

    players = read_json(AVI_PLAYERS_PATH)
    config = read_json(RISK_ADJUSTMENTS_PATH)
    if not isinstance(players, list) or not isinstance(config, dict):
        raise RuntimeError("Invalid C-AVI risk-adjustment inputs.")

    adjustments = config.get("players", [])
    if not isinstance(adjustments, list):
        raise RuntimeError("C-AVI risk-adjustment registry must contain a players list.")

    by_avi_id = {
        str(item.get("avi_id")): item
        for item in adjustments
        if isinstance(item, dict) and item.get("avi_id")
    }

    applied: list[dict[str, Any]] = []
    for player in players:
        if not isinstance(player, dict):
            continue
        adjustment = by_avi_id.get(str(player.get("avi_id")))
        if not adjustment:
            continue

        raw_adjustment = adjustment.get("c_avi_adjustment")
        components = player.setdefault("components", {})

        try:
            delta = float(raw_adjustment)
            current = float(player.get("c_avi"))
        except (TypeError, ValueError):
            raise RuntimeError(
                f"Invalid C-AVI risk adjustment for {player.get('canonical_name') or player.get('avi_id')}."
            )

        base = current
        if isinstance(components, dict):
            stored_base = components.get("base_c_avi_before_risk_adjustment")
            stored_delta = components.get("c_avi_risk_adjustment")
            try:
                if stored_base is not None and stored_delta is not None and float(stored_delta) == delta:
                    base = float(stored_base)
            except (TypeError, ValueError):
                base = current

        adjusted = round(clamp(base + delta), 1)
        player["c_avi"] = adjusted

        if isinstance(components, dict):
            components["base_c_avi_before_risk_adjustment"] = round(base, 1)
            components["c_avi_risk_adjustment"] = round(delta, 1)
            components["c_avi_risk_reason"] = adjustment.get("reason")

        player["c_avi_risk_adjustment"] = {
            "amount": round(delta, 1),
            "reason": adjustment.get("reason"),
            "review": adjustment.get("review"),
        }
        applied.append(
            {
                "avi_id": player.get("avi_id"),
                "player_name": player.get("canonical_name"),
                "base_c_avi": round(base, 1),
                "adjustment": round(delta, 1),
                "adjusted_c_avi": adjusted,
            }
        )

    write_json(AVI_PLAYERS_PATH, players)
    return {"status": "passed", "applied": applied}
