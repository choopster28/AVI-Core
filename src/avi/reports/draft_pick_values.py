from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.io import read_json, write_json
from avi.league.loader import find_current_league_file
from avi.valuation.picks import MAX_DRAFT_ROUNDS, TEAMS_PER_ROUND, draft_pick_value


MARKDOWN_OUTPUT_PATH = Path("knowledge/01_AVI_Draft_Pick_Values_0_100.md")
JSON_OUTPUT_PATH = Path("data/processed/reports/draft_pick_values.json")
ACTIVE_DRAFT_SEASONS = (2027, 2028)


def load_current_league_data() -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    league_directory = find_current_league_file().parent
    league = read_json(league_directory / "league.json")
    rosters = read_json(league_directory / "rosters.json")
    users = read_json(league_directory / "users.json")
    traded_picks = read_json(league_directory / "traded_picks.json")

    if not isinstance(league, dict):
        raise RuntimeError("Current Sleeper league.json must contain a JSON object.")
    if not isinstance(rosters, list):
        raise RuntimeError("Current Sleeper rosters.json must contain a JSON list.")
    if not isinstance(users, list):
        raise RuntimeError("Current Sleeper users.json must contain a JSON list.")
    if not isinstance(traded_picks, list):
        raise RuntimeError("Current Sleeper traded_picks.json must contain a JSON list.")

    return league, rosters, users, traded_picks


def build_user_lookup(users: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(user["user_id"]): user
        for user in users
        if isinstance(user, dict) and user.get("user_id") is not None
    }


def build_roster_identity_map(
    rosters: list[dict[str, Any]],
    users_by_id: dict[str, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for roster in rosters:
        if not isinstance(roster, dict) or roster.get("roster_id") is None:
            continue
        roster_id = int(roster["roster_id"])
        owner_id = str(roster.get("owner_id", ""))
        user = users_by_id.get(owner_id, {})
        metadata = user.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        team_name = str(
            metadata.get("team_name")
            or user.get("display_name")
            or f"Roster {roster_id}"
        ).strip()
        result[roster_id] = {
            "roster_id": roster_id,
            "owner_id": owner_id,
            "owner_display_name": str(user.get("display_name", "Unknown Owner")),
            "team_name": team_name,
        }

    expected = set(range(1, TEAMS_PER_ROUND + 1))
    if set(result) != expected:
        raise RuntimeError(
            f"Expected roster IDs 1-{TEAMS_PER_ROUND}; found {sorted(result)}"
        )
    return result


def build_current_owner_map(
    traded_picks: list[dict[str, Any]],
) -> dict[tuple[int, int, int], int]:
    """Map (season, round, original roster) -> current owner roster."""
    owner_map: dict[tuple[int, int, int], int] = {}
    active = set(ACTIVE_DRAFT_SEASONS)

    for record in traded_picks:
        if not isinstance(record, dict):
            continue
        try:
            season = int(record.get("season", 0))
            round_number = int(record.get("round", 0))
            original_roster_id = int(record.get("roster_id", 0))
            current_owner_id = int(record.get("owner_id", original_roster_id))
        except (TypeError, ValueError):
            continue

        if season not in active:
            continue
        if not (1 <= round_number <= MAX_DRAFT_ROUNDS):
            continue
        if not (1 <= original_roster_id <= TEAMS_PER_ROUND):
            continue
        if not (1 <= current_owner_id <= TEAMS_PER_ROUND):
            continue

        owner_map[(season, round_number, original_roster_id)] = current_owner_id

    return owner_map


def pick_category(value: float) -> str:
    if value >= 90.0:
        return "Elite Franchise Asset"
    if value >= 80.0:
        return "Blue-Chip Starter"
    if value >= 70.0:
        return "Premium Starter"
    if value >= 50.0:
        return "Useful Starter / High-Value Depth"
    if value >= 35.0:
        return "Rosterable Depth / Upside Stash"
    if value >= 20.0:
        return "Speculative Stash"
    if value > 0.0:
        return "Replacement / Watch List"
    return "No Current AVI"


def projected_round_value(round_number: int) -> float:
    values = [
        draft_pick_value(round_number=round_number, slot=slot)
        for slot in range(1, TEAMS_PER_ROUND + 1)
    ]
    return round(sum(values) / len(values), 1)


def build_active_picks(
    *,
    roster_identity_map: dict[int, dict[str, Any]],
    current_owner_map: dict[tuple[int, int, int], int],
) -> list[dict[str, Any]]:
    picks: list[dict[str, Any]] = []

    for season in ACTIVE_DRAFT_SEASONS:
        for round_number in range(1, MAX_DRAFT_ROUNDS + 1):
            value = projected_round_value(round_number)
            for original_roster_id in range(1, TEAMS_PER_ROUND + 1):
                current_owner_id = current_owner_map.get(
                    (season, round_number, original_roster_id),
                    original_roster_id,
                )
                original_identity = roster_identity_map[original_roster_id]
                current_identity = roster_identity_map[current_owner_id]
                original_team = str(original_identity["team_name"])
                current_team = str(current_identity["team_name"])

                picks.append(
                    {
                        "pick_id": f"{season}_{round_number:02d}_orig{original_roster_id}",
                        "pick_label": f"{season} Round {round_number} ({original_team})",
                        "season": season,
                        "round": round_number,
                        "slot": 0,
                        "original_team": original_team,
                        "original_roster_id": original_roster_id,
                        "current_owner_team": current_team,
                        "current_owner_roster_id": current_owner_id,
                        "draft_pick_avi": value,
                        "avi_category": pick_category(value),
                        "validation_status": "future_order_tbd",
                    }
                )

    return picks


def build_draft_pick_values() -> dict[str, Any]:
    league, rosters, users, traded_picks = load_current_league_data()
    users_by_id = build_user_lookup(users)
    roster_identity_map = build_roster_identity_map(rosters, users_by_id)
    current_owner_map = build_current_owner_map(traded_picks)
    picks = build_active_picks(
        roster_identity_map=roster_identity_map,
        current_owner_map=current_owner_map,
    )

    picks.sort(
        key=lambda record: (
            int(record["season"]),
            int(record["round"]),
            int(record["original_roster_id"]),
        )
    )

    payload = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "league_id": league.get("league_id"),
        "active_draft_season_start": min(ACTIVE_DRAFT_SEASONS),
        "future_draft_seasons": list(ACTIVE_DRAFT_SEASONS),
        "max_rounds": MAX_DRAFT_ROUNDS,
        "teams_per_round": TEAMS_PER_ROUND,
        "pick_count": len(picks),
        "ownership_source": "Sleeper traded_picks + native original ownership",
        "picks": picks,
    }
    write_json(JSON_OUTPUT_PATH, payload)

    lines = [
        "# AVI DRAFT PICK VALUES",
        "",
        "Retrieval purpose: official AVI values and verified ownership for active future draft capital.",
        "",
        f"- Active draft capital begins with {min(ACTIVE_DRAFT_SEASONS)}.",
        "- Every franchise natively owns its own future pick unless Sleeper traded_picks assigns it elsewhere.",
        "- Current ownership is rebuilt directly from the latest Sleeper traded_picks export.",
        "- Future draft order is not assigned; slot remains TBD and AVI uses the round-average value.",
        f"- League draft depth is {MAX_DRAFT_ROUNDS} rounds.",
        "",
    ]

    for pick in picks:
        lines.extend(
            [
                f"## PICK: {pick['pick_label']} | {pick['pick_id']}",
                f"- Season: {pick['season']}",
                f"- Round: {pick['round']}",
                "- Slot: TBD",
                f"- Original team: {pick['original_team']}",
                f"- Original roster ID: {pick['original_roster_id']}",
                f"- Current owner team: {pick['current_owner_team']}",
                f"- Current owner roster ID: {pick['current_owner_roster_id']}",
                f"- Draft Pick AVI: {pick['draft_pick_avi']}",
                f"- AVI category: {pick['avi_category']}",
                "- Validation status: future_order_tbd",
                "",
            ]
        )

    MARKDOWN_OUTPUT_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT_PATH} and {MARKDOWN_OUTPUT_PATH} with {len(picks)} active picks")
    return payload
