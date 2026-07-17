from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.io import read_json, write_json
from avi.league.loader import (
    find_current_league_file,
    load_league_structure,
)
from avi.reports.lineup import (
    ChampionshipLineup,
    build_championship_lineup,
)


AVI_PLAYERS_PATH = Path(
    "data/processed/avi/avi_players.json"
)

SLEEPER_PLAYERS_PATH = Path(
    "data/raw/sleeper/nfl_players.json"
)

OUTPUT_DIRECTORY = Path(
    "knowledge/teams"
)

MANIFEST_PATH = Path(
    "data/processed/reports/team_profiles_manifest.json"
)

OFFENSIVE_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
}

KICKER_POSITIONS = {
    "K",
}

IDP_POSITIONS = {
    "DL",
    "DE",
    "DT",
    "NT",
    "LB",
    "ILB",
    "OLB",
    "DB",
    "CB",
    "S",
    "FS",
    "SS",
}

POSITION_ORDER = {
    "QB": 1,
    "RB": 2,
    "WR": 3,
    "TE": 4,
    "K": 5,
    "DL": 6,
    "DE": 6,
    "DT": 6,
    "NT": 6,
    "LB": 7,
    "ILB": 7,
    "OLB": 7,
    "DB": 8,
    "CB": 8,
    "S": 8,
    "FS": 8,
    "SS": 8,
}


@dataclass(frozen=True)
class TeamPlayer:
    sleeper_id: str
    player_name: str
    position: str | None
    fantasy_positions: tuple[str, ...]
    nfl_team: str | None
    active: bool | None
    status: str | None
    age: float | None
    c_avi: float | None
    d_avi: float | None
    projected_ppr_points: float | None
    valuation_status: str
    category: str
    avi_record: dict[str, Any] | None
    sleeper_record: dict[str, Any]


@dataclass(frozen=True)
class TeamProfile:
    roster_id: int
    team_name: str
    owner_display_name: str
    owner_id: str
    division: int | None
    waiver_position: int | None
    keepers: tuple[str, ...]
    players: tuple[TeamPlayer, ...]
    avi_players: tuple[dict[str, Any], ...]
    championship_lineup: ChampionshipLineup
    championship_lineup_c_avi_sum: float
    championship_lineup_c_avi_avg: float
    offensive_roster_c_avi_sum: float
    offensive_roster_c_avi_avg: float
    offensive_roster_d_avi_sum: float
    offensive_roster_d_avi_avg: float


def safe_float(
    value: Any,
) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(
    value: Any,
) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def slugify_team_name(
    value: str,
) -> str:
    normalized = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        value.strip(),
    )

    normalized = normalized.strip("_")

    return normalized or "Unknown_Team"


def load_current_sleeper_directory() -> tuple[
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    league_path = find_current_league_file()
    league_directory = league_path.parent

    league = read_json(
        league_directory / "league.json"
    )

    rosters = read_json(
        league_directory / "rosters.json"
    )

    users = read_json(
        league_directory / "users.json"
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

    return league, rosters, users


def load_avi_players() -> list[dict[str, Any]]:
    if not AVI_PLAYERS_PATH.exists():
        raise RuntimeError(
            "AVI player output is missing. "
            "Run calculate-avi first."
        )

    payload = read_json(
        AVI_PLAYERS_PATH
    )

    if not isinstance(payload, list):
        raise RuntimeError(
            "avi_players.json must contain a JSON list."
        )

    return [
        record
        for record in payload
        if isinstance(record, dict)
    ]


def load_sleeper_players() -> dict[str, dict[str, Any]]:
    if not SLEEPER_PLAYERS_PATH.exists():
        raise RuntimeError(
            "Sleeper NFL player directory is missing."
        )

    payload = read_json(
        SLEEPER_PLAYERS_PATH
    )

    if not isinstance(payload, dict):
        raise RuntimeError(
            "nfl_players.json must contain a JSON object."
        )

    return {
        str(player_id): record
        for player_id, record in payload.items()
        if isinstance(record, dict)
    }


def build_avi_by_sleeper_id(
    avi_players: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    for player in avi_players:
        source_ids = player.get(
            "source_ids",
            {},
        )

        if not isinstance(source_ids, dict):
            continue

        sleeper_id = source_ids.get(
            "sleeper_id"
        )

        if sleeper_id is None:
            continue

        lookup[str(sleeper_id)] = player

    return lookup


def build_user_lookup(
    users: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(user.get("user_id")): user
        for user in users
        if isinstance(user, dict)
        and user.get("user_id") is not None
    }


def normalize_position(
    value: Any,
) -> str | None:
    if value is None:
        return None

    position = str(value).strip().upper()

    if not position:
        return None

    aliases = {
        "FB": "RB",
        "DE": "DL",
        "DT": "DL",
        "NT": "DL",
        "ILB": "LB",
        "OLB": "LB",
        "CB": "DB",
        "S": "DB",
        "FS": "DB",
        "SS": "DB",
    }

    return aliases.get(
        position,
        position,
    )


def player_category(
    position: str | None,
) -> str:
    if position in OFFENSIVE_POSITIONS:
        return "offense"

    if position in KICKER_POSITIONS:
        return "kicker"

    if position in IDP_POSITIONS:
        return "idp"

    return "other"


def extract_projection_points(
    avi_record: dict[str, Any] | None,
) -> float | None:
    if not avi_record:
        return None

    projection = avi_record.get(
        "projection",
        {},
    )

    if not isinstance(projection, dict):
        return None

    return safe_float(
        projection.get(
            "raw_points"
        )
    )


def build_team_player(
    *,
    sleeper_id: str,
    sleeper_record: dict[str, Any],
    avi_record: dict[str, Any] | None,
) -> TeamPlayer:
    raw_position = sleeper_record.get(
        "position"
    )

    position = normalize_position(
        raw_position
    )

    full_name = (
        sleeper_record.get("full_name")
        or sleeper_record.get("search_full_name")
        or " ".join(
            part
            for part in (
                sleeper_record.get("first_name"),
                sleeper_record.get("last_name"),
            )
            if part
        )
        or f"Unknown Player {sleeper_id}"
    )

    fantasy_positions_raw = sleeper_record.get(
        "fantasy_positions",
        [],
    )

    if isinstance(
        fantasy_positions_raw,
        list,
    ):
        fantasy_positions = tuple(
            str(item)
            for item in fantasy_positions_raw
        )
    else:
        fantasy_positions = tuple()

    if avi_record is not None:
        c_avi = safe_float(
            avi_record.get("c_avi")
        )

        d_avi = safe_float(
            avi_record.get("d_avi")
        )

        valuation_status = str(
            avi_record.get(
                "methodology_status",
                avi_record.get(
                    "status",
                    "CALCULATED",
                ),
            )
        ).upper()
    else:
        c_avi = None
        d_avi = None

        if (
            position in KICKER_POSITIONS
            or position in IDP_POSITIONS
        ):
            valuation_status = (
                "EXCLUDED_FROM_AVI"
            )
        else:
            valuation_status = (
                "NOT_IN_AVI_OUTPUT"
            )

    return TeamPlayer(
        sleeper_id=str(sleeper_id),
        player_name=str(full_name),
        position=position,
        fantasy_positions=(
            fantasy_positions
        ),
        nfl_team=(
            str(
                sleeper_record.get(
                    "team"
                )
            )
            if sleeper_record.get(
                "team"
            )
            is not None
            else None
        ),
        active=sleeper_record.get(
            "active"
        ),
        status=(
            str(
                sleeper_record.get(
                    "status"
                )
            )
            if sleeper_record.get(
                "status"
            )
            is not None
            else None
        ),
        age=safe_float(
            sleeper_record.get(
                "age"
            )
        ),
        c_avi=c_avi,
        d_avi=d_avi,
        projected_ppr_points=(
            extract_projection_points(
                avi_record
            )
        ),
        valuation_status=(
            valuation_status
        ),
        category=player_category(
            position
        ),
        avi_record=avi_record,
        sleeper_record=sleeper_record,
    )


def sort_team_players(
    players: list[TeamPlayer],
) -> list[TeamPlayer]:
    return sorted(
        players,
        key=lambda player: (
            POSITION_ORDER.get(
                player.position or "",
                99,
            ),
            -(
                player.c_avi
                if player.c_avi is not None
                else -1.0
            ),
            player.player_name,
        ),
    )


def calculate_offensive_totals(
    players: list[TeamPlayer],
) -> tuple[
    float,
    float,
    float,
    float,
]:
    offensive = [
        player
        for player in players
        if player.position
        in OFFENSIVE_POSITIONS
    ]

    c_values = [
        player.c_avi
        for player in offensive
        if player.c_avi is not None
    ]

    d_values = [
        player.d_avi
        for player in offensive
        if player.d_avi is not None
    ]

    c_sum = round(
        sum(c_values),
        1,
    )

    d_sum = round(
        sum(d_values),
        1,
    )

    c_average = round(
        c_sum / len(c_values),
        2,
    ) if c_values else 0.0

    d_average = round(
        d_sum / len(d_values),
        2,
    ) if d_values else 0.0

    return (
        c_sum,
        c_average,
        d_sum,
        d_average,
    )


def build_team_profile(
    *,
    roster: dict[str, Any],
    users_by_id: dict[str, dict[str, Any]],
    sleeper_players: dict[str, dict[str, Any]],
    avi_by_sleeper_id: dict[
        str,
        dict[str, Any],
    ],
    starter_counts: dict[str, int],
) -> TeamProfile:
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

    user_metadata = user.get(
        "metadata",
        {},
    )

    if not isinstance(
        user_metadata,
        dict,
    ):
        user_metadata = {}

    team_name = (
        user_metadata.get("team_name")
        or user.get("display_name")
        or f"Roster {roster_id}"
    )

    player_ids = roster.get(
        "players",
        [],
    )

    if not isinstance(player_ids, list):
        player_ids = []

    team_players: list[
        TeamPlayer
    ] = []

    team_avi_players: list[
        dict[str, Any]
    ] = []

    for sleeper_id_raw in player_ids:
        sleeper_id = str(
            sleeper_id_raw
        )

        sleeper_record = (
            sleeper_players.get(
                sleeper_id,
                {
                    "player_id": sleeper_id,
                    "full_name": (
                        f"Unknown Player "
                        f"{sleeper_id}"
                    ),
                },
            )
        )

        avi_record = (
            avi_by_sleeper_id.get(
                sleeper_id
            )
        )

        team_players.append(
            build_team_player(
                sleeper_id=sleeper_id,
                sleeper_record=(
                    sleeper_record
                ),
                avi_record=avi_record,
            )
        )

        if avi_record is not None:
            team_avi_players.append(
                avi_record
            )

    team_players = sort_team_players(
        team_players
    )

    championship_lineup = (
        build_championship_lineup(
            players=team_avi_players,
            starter_counts=starter_counts,
        )
    )

    (
        offensive_c_sum,
        offensive_c_average,
        offensive_d_sum,
        offensive_d_average,
    ) = calculate_offensive_totals(
        team_players
    )

    settings = roster.get(
        "settings",
        {},
    )

    if not isinstance(settings, dict):
        settings = {}

    keepers_raw = roster.get(
        "keepers",
        [],
    )

    if not isinstance(keepers_raw, list):
        keepers_raw = []

    return TeamProfile(
        roster_id=roster_id,
        team_name=str(team_name),
        owner_display_name=str(
            user.get(
                "display_name",
                "Unknown Owner",
            )
        ),
        owner_id=owner_id,
        division=safe_int(
            settings.get(
                "division"
            )
        ),
        waiver_position=safe_int(
            settings.get(
                "waiver_position"
            )
        ),
        keepers=tuple(
            str(player_id)
            for player_id in keepers_raw
        ),
        players=tuple(
            team_players
        ),
        avi_players=tuple(
            team_avi_players
        ),
        championship_lineup=(
            championship_lineup
        ),
        championship_lineup_c_avi_sum=(
            championship_lineup.c_avi_sum
        ),
        championship_lineup_c_avi_avg=(
            championship_lineup.c_avi_average
        ),
        offensive_roster_c_avi_sum=(
            offensive_c_sum
        ),
        offensive_roster_c_avi_avg=(
            offensive_c_average
        ),
        offensive_roster_d_avi_sum=(
            offensive_d_sum
        ),
        offensive_roster_d_avi_avg=(
            offensive_d_average
        ),
    )


def display_value(
    value: Any,
) -> str:
    if value is None:
        return "None"

    if isinstance(value, float):
        return f"{value:.1f}"

    return str(value)


def render_player_card(
    player: TeamPlayer,
    profile: TeamProfile,
) -> str:
    fantasy_positions = list(
        player.fantasy_positions
    )

    lines = [
        f"### PLAYER: {player.player_name}",
        f"- Player name: {player.player_name}",
        f"- Player ID: {player.sleeper_id}",
        (
            "- Current owner team: "
            f"{profile.team_name}"
        ),
        (
            "- Current owner roster ID: "
            f"{profile.roster_id}"
        ),
        (
            "- Position: "
            f"{player.position}"
        ),
        (
            "- Fantasy positions: "
            f"{fantasy_positions}"
        ),
        (
            "- NFL team: "
            f"{player.nfl_team}"
        ),
        (
            "- Active: "
            f"{player.active}"
        ),
        (
            "- Status: "
            f"{player.status}"
        ),
        (
            "- Age: "
            f"{display_value(player.age)}"
        ),
        (
            "- Championship AVI "
            "(C-AVI, 0-100): "
            f"{display_value(player.c_avi)}"
        ),
        (
            "- Dynasty AVI "
            "(D-AVI, 0-100): "
            f"{display_value(player.d_avi)}"
        ),
        (
            "- Projected PPR points: "
            f"{display_value(
                player.projected_ppr_points
            )}"
        ),
        (
            "- Category: "
            f"{player.category}"
        ),
        (
            "- Valuation status: "
            f"{player.valuation_status}"
        ),
    ]

    return "\n".join(lines)


def render_team_profile(
    profile: TeamProfile,
    *,
    updated_date: str,
) -> str:
    offense_count = sum(
        1
        for player in profile.players
        if player.category == "offense"
    )

    kicker_count = sum(
        1
        for player in profile.players
        if player.category == "kicker"
    )

    idp_count = sum(
        1
        for player in profile.players
        if player.category == "idp"
    )

    other_count = sum(
        1
        for player in profile.players
        if player.category == "other"
    )

    lines = [
        f"# TEAM: {profile.team_name}",
        "",
        (
            "Retrieval purpose: authoritative current roster, "
            "player cards, team assets, and raw team-score inputs "
            "for this franchise only. League-wide rankings must "
            "be generated live."
        ),
        "",
        "## Team Identity",
        f"- Team name: {profile.team_name}",
        f"- Roster ID: {profile.roster_id}",
        (
            "- Owner display name: "
            f"{profile.owner_display_name}"
        ),
        f"- Owner ID: {profile.owner_id}",
        f"- Division: {profile.division}",
        (
            "- Waiver position: "
            f"{profile.waiver_position}"
        ),
        (
            "- Last updated from Sleeper exports: "
            f"{updated_date}"
        ),
        (
            "- AVI value source: AVI automated model — "
            "FantasyPros projections + FantasyPros rankings + "
            "Autobots league context"
        ),
        "",
        "## Roster Counts",
        (
            "- total_players: "
            f"{len(profile.players)}"
        ),
        f"- offense: {offense_count}",
        f"- kickers: {kicker_count}",
        f"- idp: {idp_count}",
        f"- other: {other_count}",
        (
            "- keepers: "
            f"{len(profile.keepers)}"
        ),
        "",
        "## Raw Team Score Inputs, Not Static Rankings",
        (
            "- championship_lineup_c_avi_sum: "
            f"{profile.championship_lineup_c_avi_sum}"
        ),
        (
            "- championship_lineup_c_avi_avg: "
            f"{profile.championship_lineup_c_avi_avg:.2f}"
        ),
        (
            "- offensive_roster_c_avi_sum: "
            f"{profile.offensive_roster_c_avi_sum}"
        ),
        (
            "- offensive_roster_c_avi_avg: "
            f"{profile.offensive_roster_c_avi_avg:.2f}"
        ),
        (
            "- offensive_roster_d_avi_sum: "
            f"{profile.offensive_roster_d_avi_sum}"
        ),
        (
            "- offensive_roster_d_avi_avg: "
            f"{profile.offensive_roster_d_avi_avg:.2f}"
        ),
        (
            "- note: Scores are data supports for live analysis; "
            "rankings should still be generated in-chat."
        ),
        "",
        "## Championship Lineup Used For Raw C-AVI Input",
    ]

    for slot in (
        profile.championship_lineup.slots
    ):
        player = slot.player

        lines.append(
            f"- {slot.slot}: "
            f"{player.get('canonical_name')} "
            f"| C-AVI: {player.get('c_avi')} "
            f"| D-AVI: {player.get('d_avi')}"
        )

    lines.extend(
        [
            "",
            "## Current Roster — All Player Cards",
            (
                "Every player card repeats owner and roster ID "
                "so retrieval can verify ownership independently."
            ),
            "",
        ]
    )

    for player in profile.players:
        lines.append(
            render_player_card(
                player,
                profile,
            )
        )
        lines.append("")

    lines.extend(
        [
            "## Current Draft Pick Assets",
            (
                "- Draft-pick ownership will be attached by the "
                "automated draft-pick report generator."
            ),
            "",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def build_team_profiles() -> dict[str, Any]:
    league_payload, rosters, users = (
        load_current_sleeper_directory()
    )

    league_structure = (
        load_league_structure()
    )

    sleeper_players = (
        load_sleeper_players()
    )

    avi_players = load_avi_players()

    avi_by_sleeper_id = (
        build_avi_by_sleeper_id(
            avi_players
        )
    )

    users_by_id = build_user_lookup(
        users
    )

    profiles: list[
        TeamProfile
    ] = []

    for roster in rosters:
        if not isinstance(roster, dict):
            continue

        profiles.append(
            build_team_profile(
                roster=roster,
                users_by_id=users_by_id,
                sleeper_players=(
                    sleeper_players
                ),
                avi_by_sleeper_id=(
                    avi_by_sleeper_id
                ),
                starter_counts=(
                    league_structure.starter_counts
                ),
            )
        )

    profiles.sort(
        key=lambda profile: (
            profile.roster_id
        )
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    generated_files: list[str] = []

    updated_date = datetime.now(
        UTC
    ).date().isoformat()

    for profile in profiles:
        filename = (
            f"{profile.roster_id:02d}_"
            f"{slugify_team_name(profile.team_name)}"
            ".md"
        )

        output_path = (
            OUTPUT_DIRECTORY
            / filename
        )

        output_path.write_text(
            render_team_profile(
                profile,
                updated_date=updated_date,
            ),
            encoding="utf-8",
        )

        generated_files.append(
            str(output_path)
        )

        print(
            f"Generated: {output_path}"
        )

    manifest = {
        "generated_at_utc": (
            datetime.now(
                UTC
            ).isoformat()
        ),
        "league_id": league_payload.get(
            "league_id"
        ),
        "season": league_payload.get(
            "season"
        ),
        "team_count": len(
            profiles
        ),
        "generated_files": (
            generated_files
        ),
        "status": (
            "passed"
            if len(profiles)
            == league_structure.team_count
            else "failed"
        ),
    }

    write_json(
        MANIFEST_PATH,
        manifest,
    )

    print()
    print("=" * 60)
    print("AVI TEAM PROFILE GENERATION COMPLETE")
    print("=" * 60)
    print(
        f"Team profiles generated: "
        f"{len(profiles)}"
    )

    return manifest