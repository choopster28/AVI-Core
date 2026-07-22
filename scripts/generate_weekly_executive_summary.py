from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
TEAMS = KNOWLEDGE / "teams"
OUTPUT = KNOWLEDGE / "franchise_summaries"
MOUNTAIN = ZoneInfo("America/Denver")

FIELD_RE = re.compile(r"^- ([^:]+):\s*(.*)$")
LINEUP_RE = re.compile(
    r"^- (QB|RB|WR|TE|FLEX): (.+?) \| C-AVI: ([0-9.]+) \| D-AVI: ([0-9.]+)$"
)
PLAYER_RE = re.compile(r"^### PLAYER: (.+)$")


def slugify(value: str) -> str:
    value = value.lower().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def section(lines: list[str], heading: str) -> list[str]:
    try:
        start = lines.index(heading) + 1
    except ValueError:
        return []
    out: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        out.append(line)
    return out


def parse_fields(lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in lines:
        match = FIELD_RE.match(line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def parse_team(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    identity = parse_fields(section(lines, "## Team Identity"))
    counts = parse_fields(section(lines, "## Roster Counts"))
    scores = parse_fields(section(lines, "## Raw Team Score Inputs, Not Static Rankings"))
    picks = [line[2:].strip() for line in section(lines, "## Current Draft Pick Assets") if line.startswith("- ")]

    lineup = []
    for line in section(lines, "## Championship Lineup Used For Raw C-AVI Input"):
        match = LINEUP_RE.match(line)
        if match:
            lineup.append(
                {
                    "slot": match.group(1),
                    "player": match.group(2),
                    "c_avi": float(match.group(3)),
                    "d_avi": float(match.group(4)),
                }
            )

    players = []
    current: dict | None = None
    for line in section(lines, "## Current Roster — All Player Cards"):
        player_match = PLAYER_RE.match(line)
        if player_match:
            if current:
                players.append(current)
            current = {"name": player_match.group(1)}
            continue
        if current:
            field_match = FIELD_RE.match(line)
            if field_match:
                current[field_match.group(1).strip()] = field_match.group(2).strip()
    if current:
        players.append(current)

    if not identity.get("Team name") or not identity.get("Roster ID"):
        raise ValueError(f"Missing required Team Identity fields in {path}")
    if not lineup:
        raise ValueError(f"Missing championship lineup in {path}")

    return {
        "source_file": str(path.relative_to(ROOT)),
        "team_name": identity["Team name"],
        "roster_id": int(identity["Roster ID"]),
        "owner": identity.get("Owner display name"),
        "division": identity.get("Division"),
        "waiver_position": identity.get("Waiver position"),
        "source_updated": identity.get("Last updated from Sleeper exports"),
        "counts": counts,
        "scores": scores,
        "lineup": lineup,
        "players": players,
        "picks": picks,
    }


def preseason_summary(team: dict, now: datetime) -> dict:
    lineup = team["lineup"]
    sorted_lineup = sorted(lineup, key=lambda item: item["c_avi"], reverse=True)
    anchors = sorted_lineup[:3]
    pressure = min(lineup, key=lambda item: item["c_avi"])
    anchor_names = ", ".join(item["player"] for item in anchors[:-1]) + f", and {anchors[-1]['player']}"
    depth_count = max(int(team["counts"].get("offense", "0")) - len(lineup), 0)
    lineup_avg = float(team["scores"].get("championship_lineup_c_avi_avg", "0"))
    roster_d_avg = float(team["scores"].get("offensive_roster_d_avi_avg", "0"))

    active_players = [
        player for player in team["players"]
        if player.get("Status") == "Active" and player.get("Category") == "offense"
    ]
    unavailable = [
        player["name"] for player in team["players"]
        if player.get("Status") not in (None, "Active")
    ]

    if unavailable:
        health_body = (
            f"The source file flags {', '.join(unavailable)} outside Active status. "
            "Those availability records should drive contingency planning until the next knowledge refresh changes them."
        )
    else:
        health_body = (
            f"All {len(active_players)} offensive players in the current team file are marked Active. "
            "There is no knowledge-backed reason for an emergency replacement move this week."
        )

    pick_detail = "; ".join(team["picks"])
    if not pick_detail or "will be attached" in pick_detail.lower():
        pick_body = (
            "The team file does not yet contain attached draft-pick ownership. "
            "No pick recommendation is published because the approved knowledge source does not verify one."
        )
    else:
        pick_body = f"Verified draft assets in the team file: {pick_detail}."

    return {
        "schema_version": 2,
        "franchise_id": slugify(team["team_name"]),
        "franchise_name": team["team_name"],
        "roster_id": team["roster_id"],
        "owner_display_name": team["owner"],
        "season_phase": "preseason",
        "reporting_period": now.strftime("Week of %B %-d, %Y"),
        "generated_at": now.isoformat(),
        "refresh_schedule": "Wednesdays at 11:00 AM America/Denver",
        "headline": f"{team['team_name']}: Preseason Front Office Brief",
        "executive_summary": (
            f"{team['team_name']} carries a championship-lineup C-AVI average of {lineup_avg:.2f}, "
            f"led by {anchor_names}. The immediate preseason decision is not broad roster turnover; "
            f"it is whether the {pressure['slot']} slot currently occupied by {pressure['player']} "
            f"({pressure['c_avi']:.1f} C-AVI) can be improved without weakening the verified core."
        ),
        "sections": [
            {
                "id": "competitive-core",
                "title": "Competitive Core",
                "body": (
                    f"The three highest C-AVI starters are {anchors[0]['player']} ({anchors[0]['c_avi']:.1f}), "
                    f"{anchors[1]['player']} ({anchors[1]['c_avi']:.1f}), and {anchors[2]['player']} "
                    f"({anchors[2]['c_avi']:.1f}). That concentration gives {team['team_name']} a defined top-end identity."
                ),
            },
            {
                "id": "lineup-pressure-point",
                "title": "Lineup Pressure Point",
                "body": (
                    f"Among the eight verified championship-lineup slots, {pressure['player']} is the lowest C-AVI starter "
                    f"at {pressure['c_avi']:.1f}. Any preseason acquisition should be measured against that exact lineup threshold, "
                    "not against the bottom of the bench."
                ),
            },
            {
                "id": "depth-and-flexibility",
                "title": "Depth and Flexibility",
                "body": (
                    f"The team file contains {team['counts'].get('offense', '0')} offensive players, leaving {depth_count} "
                    f"offensive players outside the modeled starting eight. The offensive roster D-AVI average is {roster_d_avg:.2f}, "
                    "which should be used to judge whether consolidation improves the lineup more than it reduces flexibility."
                ),
            },
            {"id": "availability", "title": "Availability", "body": health_body},
            {"id": "draft-assets", "title": "Draft Assets", "body": pick_body},
        ],
        "source": {
            "policy": "AVI-Core/knowledge only",
            "files": [team["source_file"]],
            "source_last_updated": team["source_updated"],
            "external_sources_used": False,
            "conversation_context_used": False,
        },
    }


def regular_season_summary(team: dict, now: datetime) -> dict:
    summary = preseason_summary(team, now)
    summary["season_phase"] = "regular_season"
    summary["headline"] = f"{team['team_name']}: Weekly Franchise Brief"
    summary["sections"].extend(
        [
            {
                "id": "matchup-recap",
                "title": "Matchup Recap",
                "body": "Not published: the approved team file does not contain a completed weekly matchup section.",
            },
            {
                "id": "standings",
                "title": "Standings and Playoff Position",
                "body": "Not published: the approved team file does not contain current standings data.",
            },
        ]
    )
    return summary


def main() -> None:
    now = datetime.now(MOUNTAIN)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    team_paths = sorted(TEAMS.glob("*.md"))
    if len(team_paths) != 16:
        raise RuntimeError(f"Expected 16 team files in {TEAMS}, found {len(team_paths)}")

    written = []
    for path in team_paths:
        team = parse_team(path)
        summary = preseason_summary(team, now) if now.month < 9 else regular_season_summary(team, now)
        destination = OUTPUT / f"{summary['franchise_id']}.json"
        destination.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        written.append(destination.name)

    manifest = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "refresh_schedule": "Wednesdays at 11:00 AM America/Denver",
        "source_policy": "AVI-Core/knowledge only",
        "franchise_count": len(written),
        "files": written,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(written)} franchise summaries to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
