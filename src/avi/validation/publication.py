from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.io import read_json, write_json
from avi.valuation.availability_adjustments import _load_injury_state, _expected_missed_weeks


MIN_REGISTRY_PLAYERS = 300
MIN_AVI_PLAYERS = 300
EXPECTED_TEAM_COUNT = 16


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def validate_publication() -> dict[str, Any]:
    """Block publication unless the complete canonical AVI snapshot is coherent."""
    failures: list[str] = []
    now = datetime.now(UTC)

    registry = read_json(Path("data/processed/identity/avi_player_registry.json"))
    avi_players = read_json(Path("data/processed/avi/avi_players.json"))
    avi_manifest = read_json(Path("data/processed/avi/manifest.json"))
    team_manifest = read_json(Path("data/processed/reports/team_profiles_manifest.json"))
    lookup = read_json(Path("data/processed/reports/player_lookup.json"))

    registry_count = len(registry) if isinstance(registry, list) else 0
    avi_count = len(avi_players) if isinstance(avi_players, list) else 0
    lookup_count = 0
    if isinstance(lookup, dict):
        lookup_count = len(lookup.get("rostered_players", [])) + len(lookup.get("available_players", []))

    if registry_count < MIN_REGISTRY_PLAYERS:
        failures.append(f"AVI registry collapsed: {registry_count} < {MIN_REGISTRY_PLAYERS} players.")
    if avi_count < MIN_AVI_PLAYERS:
        failures.append(f"AVI player output collapsed: {avi_count} < {MIN_AVI_PLAYERS} players.")
    if registry_count != avi_count:
        failures.append(f"Registry/AVI player count mismatch: {registry_count} vs {avi_count}.")
    if lookup_count < MIN_AVI_PLAYERS:
        failures.append(f"Player lookup is incomplete: {lookup_count} < {MIN_AVI_PLAYERS} players.")

    record_counts = avi_manifest.get("record_counts", {}) if isinstance(avi_manifest, dict) else {}
    if record_counts.get("calculated_players") != avi_count:
        failures.append("AVI manifest calculated-player count does not match avi_players.json.")
    if avi_manifest.get("status") != "passed":
        failures.append("AVI manifest status is not passed.")
    if "in_season_transition" not in avi_manifest:
        failures.append("AVI manifest is missing in-season transition metadata.")

    generated_at = _parse_timestamp(avi_manifest.get("generated_at_utc"))
    if generated_at is None:
        failures.append("AVI manifest is missing a valid generation timestamp.")
    elif (now - generated_at).total_seconds() > 6 * 60 * 60:
        failures.append(
            f"AVI manifest is stale for this run: generated {generated_at.isoformat()}."
        )

    if team_manifest.get("status") != "passed":
        failures.append("Team profile manifest status is not passed.")
    if team_manifest.get("team_count") != EXPECTED_TEAM_COUNT:
        failures.append(
            f"Team profile count is {team_manifest.get('team_count')}, expected {EXPECTED_TEAM_COUNT}."
        )
    generated_files = team_manifest.get("generated_files", [])
    if not isinstance(generated_files, list) or len(generated_files) != EXPECTED_TEAM_COUNT:
        failures.append("Team profile manifest does not contain exactly 16 generated team files.")

    # Do not silently publish a nonzero current-season value for a verified
    # season-ending absence. Validate by source-linked identity, never by name.
    confirmations = read_json(Path("data/manual/season_ending_injury_confirmations_2026.json"))
    reported = [entry for entry in confirmations.get("reports", []) if isinstance(entry, dict) and entry.get("season_ending") is True] if isinstance(confirmations, dict) and confirmations.get("season") == 2026 else []
    if reported and isinstance(avi_players, list):
        states = _load_injury_state()
        by_id = {str(player.get("avi_id")): player for player in avi_players if isinstance(player, dict)}
        matched = [avi_id for avi_id, state in states.items() if state.get("season_ending_confirmation")]
        if len(matched) < len(reported):
            failures.append("Season-ending confirmation could not be matched to canonical AVI identities.")
        transition = avi_manifest.get("in_season_transition", {}) if isinstance(avi_manifest, dict) else {}
        current_week = int(transition.get("nfl_week") or 0)
        for avi_id in matched:
            state = states[avi_id]
            _, reason = _expected_missed_weeks(state, current_week)
            if reason != "season_ending":
                continue  # An explicitly cleared player can resume normal valuation.
            player = by_id.get(avi_id)
            if not player or float(player.get("c_avi") or 0.0) != 0.0:
                failures.append(f"Verified season-ending player {avi_id} has nonzero or missing C-AVI.")

    result = {
        "status": "failed" if failures else "passed",
        "checked_at_utc": now.isoformat(),
        "failures": failures,
        "counts": {
            "registry_players": registry_count,
            "avi_players": avi_count,
            "player_lookup": lookup_count,
            "team_profiles": team_manifest.get("team_count"),
        },
        "avi_generated_at_utc": avi_manifest.get("generated_at_utc"),
        "in_season_transition": avi_manifest.get("in_season_transition"),
    }

    write_json(Path("data/processed/validation/publication.json"), result)
    if failures:
        raise RuntimeError(" | ".join(failures))
    return result