from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.io import read_json, write_json
from avi.league.loader import find_current_league_file
from avi.valuation.picks import (
    MAX_DRAFT_ROUNDS,
    TEAMS_PER_ROUND,
    draft_pick_value,
)


MARKDOWN_OUTPUT_PATH = Path(
    "knowledge/01_AVI_Draft_Pick_Values_0_100.md"
)

JSON_OUTPUT_PATH = Path(
    "data/processed/reports/draft_pick_values.json"
)

CURRENT_DRAFT_SEASON = 2026

FUTURE_DRAFT_SEASONS = (
    2027,
    2028,
)


def load_current_league_data() -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    league_directory = (
        find_current_league_file().parent
    )

    league = read_json(
        league_directory / "league.json"
    )

    rosters = read_json(
        league_directory / "rosters.json"
    )

    users = read_json(
        league_directory / "users.json"
    )

    traded_picks = read_json(
        league_directory / "traded_picks.json"
    )

    drafts = read_json(
        league_directory / "drafts.json"
    )

    if not isinstance(league, dict):
        raise RuntimeError(
            "Current Sleeper league.json must contain a JSON object."
        )

    if not isinstance(rosters, list):
        raise RuntimeError(
            "Current Sleeper rosters.json must contain a JSON list."
        )

    if not isinstance(users, list):
        raise RuntimeError(
            "Current Sleeper users.json must contain a JSON list."
        )

    if not isinstance(traded_picks, list):
        raise RuntimeError(
            "Current Sleeper traded_picks.json must contain a JSON list."
        )

    if not isinstance(drafts, list):
        raise RuntimeError(
            "Current Sleeper drafts.json must contain a JSON list."
        )

    return (
        league,
        rosters,
        users,
        traded_picks,
        drafts,
    )


def build_user_lookup(
    users: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(user["user_id"]): user
        for user in users
        if isinstance(user, dict)
        and user.get("user_id") is not None
    }


def build_roster_identity_map(
    rosters: list[dict[str, Any]],
    users_by_id: dict[str, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}

    for roster in rosters:
        if not isinstance(roster, dict):
            continue

        roster_id = int(
            roster.get("roster_id")
        )

        owner_id = str(
            roster.get("owner_id", "")
        )

        user = users_by_id.get(
            owner_id,
            {},
        )

        metadata = user.get(
            "metadata",
            {},
        )

        if not isinstance(metadata, dict):
            metadata = {}

        team_name = str(
            metadata.get("team_name")
            or user.get("display_name")
            or f"Roster {roster_id}"
        )

        result[roster_id] = {
            "roster_id": roster_id,
            "owner_id": owner_id,
            "owner_display_name": str(
                user.get(
                    "display_name",
                    "Unknown Owner",
                )
            ),
            "team_name": team_name,
        }

    return result


def load_current_draft_order(
    drafts: list[dict[str, Any]],
) -> dict[str, int]:
    current_draft: dict[str, Any] | None = None

    for draft in drafts:
        if not isinstance(draft, dict):
            continue

        if str(
            draft.get("season")
        ) != str(
            CURRENT_DRAFT_SEASON
        ):
            continue

        current_draft = draft
        break

    if current_draft is None:
        raise RuntimeError(
            f"No {CURRENT_DRAFT_SEASON} draft record found."
        )

    draft_order = current_draft.get(
        "draft_order"
    )

    if not isinstance(draft_order, dict):
        raise RuntimeError(
            f"{CURRENT_DRAFT_SEASON} draft_order is missing."
        )

    normalized: dict[str, int] = {}

    for owner_id, slot in draft_order.items():
        normalized[str(owner_id)] = int(slot)

    if len(normalized) != TEAMS_PER_ROUND:
        raise RuntimeError(
            f"{CURRENT_DRAFT_SEASON} draft order must contain "
            f"{TEAMS_PER_ROUND} teams."
        )

    return normalized


def build_slot_to_original_roster_map(
    *,
    roster_identity_map: dict[
        int,
        dict[str, Any],
    ],
    draft_order_by_owner_id: dict[
        str,
        int,
    ],
) -> dict[int, int]:
    slot_to_roster: dict[int, int] = {}

    for roster_id, identity in (
        roster_identity_map.items()
    ):
        owner_id = str(
            identity["owner_id"]
        )

        slot = draft_order_by_owner_id.get(
            owner_id
        )

        if slot is None:
            raise RuntimeError(
                "Draft order is missing owner "
                f"{owner_id} for roster {roster_id}."
            )

        if slot in slot_to_roster:
            raise RuntimeError(
                f"Duplicate draft slot detected: {slot}"
            )

        slot_to_roster[slot] = roster_id

    expected_slots = set(
        range(
            1,
            TEAMS_PER_ROUND + 1,
        )
    )

    if set(slot_to_roster) != expected_slots:
        raise RuntimeError(
            "Draft order does not contain every slot "
            f"from 1 through {TEAMS_PER_ROUND}."
        )

    return slot_to_roster


def build_current_pick_owner_map(
    traded_picks: list[dict[str, Any]],
) -> dict[
    tuple[int, int],
    int,
]:
    """
    Map:
        (round_number, original_roster_id)
        -> current_owner_roster_id

    Only the 2026 draft uses established franchise ownership.
    Future-year ownership remains TBD.
    """
    current_owner_map: dict[
        tuple[int, int],
        int,
    ] = {}

    for record in traded_picks:
        if not isinstance(record, dict):
            continue

        season = int(
            record.get("season", 0)
        )

        if season != CURRENT_DRAFT_SEASON:
            continue

        round_number = int(
            record.get("round", 0)
        )

        original_roster_id = int(
            record.get("roster_id", 0)
        )

        current_owner_id = int(
            record.get(
                "owner_id",
                original_roster_id,
            )
        )

        if (
            round_number < 1
            or round_number > MAX_DRAFT_ROUNDS
        ):
            continue

        if not (
            1
            <= original_roster_id
            <= TEAMS_PER_ROUND
        ):
            continue

        if not (
            1
            <= current_owner_id
            <= TEAMS_PER_ROUND
        ):
            continue

        current_owner_map[
            (
                round_number,
                original_roster_id,
            )
        ] = current_owner_id

    return current_owner_map


def pick_category(
    value: float,
) -> str:
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


def build_current_season_picks(
    *,
    roster_identity_map: dict[
        int,
        dict[str, Any],
    ],
    slot_to_original_roster: dict[
        int,
        int,
    ],
    current_owner_map: dict[
        tuple[int, int],
        int,
    ],
) -> list[dict[str, Any]]:
    picks: list[dict[str, Any]] = []

    for round_number in range(
        1,
        MAX_DRAFT_ROUNDS + 1,
    ):
        for slot in range(
            1,
            TEAMS_PER_ROUND + 1,
        ):
            original_roster_id = (
                slot_to_original_roster[
                    slot
                ]
            )

            current_owner_id = (
                current_owner_map.get(
                    (
                        round_number,
                        original_roster_id,
                    ),
                    original_roster_id,
                )
            )

            original_identity = (
                roster_identity_map[
                    original_roster_id
                ]
            )

            current_identity = (
                roster_identity_map[
                    current_owner_id
                ]
            )

            value = draft_pick_value(
                round_number=round_number,
                slot=slot,
            )

            picks.append(
                {
                    "pick_id": (
                        f"{CURRENT_DRAFT_SEASON}_"
                        f"{round_number:02d}_"
                        f"{slot:02d}"
                    ),
                    "pick_label": (
                        f"{CURRENT_DRAFT_SEASON} "
                        f"{round_number}."
                        f"{slot:02d}"
                    ),
                    "season": CURRENT_DRAFT_SEASON,
                    "round": round_number,
                    "slot": slot,
                    "original_team": (
                        original_identity[
                            "team_name"
                        ]
                    ),
                    "original_roster_id": (
                        original_roster_id
                    ),
                    "current_owner_team": (
                        current_identity[
                            "team_name"
                        ]
                    ),
                    "current_owner_roster_id": (
                        current_owner_id
                    ),
                    "draft_pick_avi": value,
                    "avi_category": (
                        pick_category(value)
                    ),
                    "validation_status": (
                        "verified_current_draft_order"
                    ),
                }
            )

    return picks


def build_future_season_picks() -> list[
    dict[str, Any]
]:
    picks: list[dict[str, Any]] = []

    for season in FUTURE_DRAFT_SEASONS:
        for round_number in range(
            1,
            MAX_DRAFT_ROUNDS + 1,
        ):
            for slot in range(
                1,
                TEAMS_PER_ROUND + 1,
            ):
                value = draft_pick_value(
                    round_number=round_number,
                    slot=slot,
                )

                picks.append(
                    {
                        "pick_id": (
                            f"{season}_"
                            f"{round_number:02d}_"
                            f"{slot:02d}"
                        ),
                        "pick_label": (
                            f"{season} "
                            f"{round_number}."
                            f"{slot:02d}"
                        ),
                        "season": season,
                        "round": round_number,
                        "slot": slot,
                        "original_team": "TBD",
                        "original_roster_id": None,
                        "current_owner_team": "TBD",
                        "current_owner_roster_id": None,
                        "draft_pick_avi": value,
                        "avi_category": (
                            pick_category(value)
                        ),
                        "validation_status": (
                            "future_order_tbd"
                        ),
                    }
                )

    return picks


def build_draft_pick_values() -> dict[str, Any]:
    (
        league,
        rosters,
        users,
        traded_picks,
        drafts,
    ) = load_current_league_data()

    users_by_id = build_user_lookup(
        users
    )

    roster_identity_map = (
        build_roster_identity_map(
            rosters,
            users_by_id,
        )
    )

    draft_order_by_owner_id = (
        load_current_draft_order(
            drafts
        )
    )

    slot_to_original_roster = (
        build_slot_to_original_roster_map(
            roster_identity_map=(
                roster_identity_map
            ),
            draft_order_by_owner_id=(
                draft_order_by_owner_id
            ),
        )
    )

    current_owner_map = (
        build_current_pick_owner_map(
            traded_picks
        )
    )

    picks = build_current_season_picks(
        roster_identity_map=(
            roster_identity_map
        ),
        slot_to_original_roster=(
            slot_to_original_roster
        ),
        current_owner_map=(
            current_owner_map
        ),
    )

    picks.extend(
        build_future_season_picks()
    )

    picks.sort(
        key=lambda record: (
            int(record["season"]),
            int(record["round"]),
            int(record["slot"]),
        )
    )

    payload = {
        "generated_at_utc": (
            datetime.now(
                UTC
            ).isoformat()
        ),
        "league_id": league.get(
            "league_id"
        ),
        "current_draft_season": (
            CURRENT_DRAFT_SEASON
        ),
        "future_draft_seasons": list(
            FUTURE_DRAFT_SEASONS
        ),
        "max_rounds": (
            MAX_DRAFT_ROUNDS
        ),
        "teams_per_round": (
            TEAMS_PER_ROUND
        ),
        "pick_count": len(
            picks
        ),
        "curve": {
            "starting_value": 95.0,
            "depreciation_per_pick": 1.2,
            "minimum_value": 0.0,
        },
        "picks": picks,
    }

    write_json(
        JSON_OUTPUT_PATH,
        payload,
    )

    lines = [
        "# AVI DRAFT PICK VALUES",
        "",
        (
            "Retrieval purpose: official draft-pick AVI values "
            "and verified current-year ownership."
        ),
        "",
        (
            f"- {CURRENT_DRAFT_SEASON} slots are assigned from "
            "the current Sleeper draft order."
        ),
        (
            f"- {CURRENT_DRAFT_SEASON} ownership is rebuilt from "
            "the current Sleeper traded_picks export."
        ),
        (
            "- Future-year original teams and current owners remain "
            "TBD until that season's draft order is established."
        ),
        (
            "- Pick AVI resets to 95.0 at 1.01 for each draft year."
        ),
        (
            "- Every subsequent pick depreciates by 1.2."
        ),
        (
            "- Draft-pick AVI is floored at 0.0."
        ),
        (
            "- Rounds above the configured 10-round league depth "
            "are excluded."
        ),
        "",
    ]

    for pick in picks:
        lines.extend(
            [
                (
                    "## PICK: "
                    f"{pick['pick_label']} "
                    f"| {pick['pick_id']}"
                ),
                (
                    "- Pick label: "
                    f"{pick['pick_label']}"
                ),
                (
                    "- Season: "
                    f"{pick['season']}"
                ),
                (
                    "- Round: "
                    f"{pick['round']}"
                ),
                (
                    "- Slot: "
                    f"{pick['slot']}"
                ),
                (
                    "- Original team: "
                    f"{pick['original_team']}"
                ),
                (
                    "- Original roster ID: "
                    f"{pick['original_roster_id']}"
                ),
                (
                    "- Current owner team: "
                    f"{pick['current_owner_team']}"
                ),
                (
                    "- Current owner roster ID: "
                    f"{pick['current_owner_roster_id']}"
                ),
                (
                    "- Draft Pick AVI: "
                    f"{pick['draft_pick_avi']}"
                ),
                (
                    "- AVI category: "
                    f"{pick['avi_category']}"
                ),
                (
                    "- Validation status: "
                    f"{pick['validation_status']}"
                ),
                "",
            ]
        )

    MARKDOWN_OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    MARKDOWN_OUTPUT_PATH.write_text(
        "\n".join(lines).rstrip() + "\n",
        encoding="utf-8",
    )

    print(
        f"Generated: "
        f"{MARKDOWN_OUTPUT_PATH}"
    )

    print(
        f"Draft picks generated: "
        f"{len(picks)}"
    )

    return payload