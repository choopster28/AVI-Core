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
LINEUP_RE = re.compile(r"^- (QB|RB|WR|TE|FLEX): (.+?) \| C-AVI: ([0-9.]+) \| D-AVI: ([0-9.]+)$")
PLAYER_RE = re.compile(r"^### PLAYER: (.+)$")
PICK_HEADING_RE = re.compile(r"^## PICK:\s*(.+?)(?:\s*\||$)")


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower().replace("'", "")).strip("-")


def section(lines: list[str], heading: str) -> list[str]:
    try:
        start = lines.index(heading) + 1
    except ValueError:
        return []
    output: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        output.append(line)
    return output


def fields(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in lines:
        match = FIELD_RE.match(line)
        if match:
            result[match.group(1).strip()] = match.group(2).strip()
    return result


def approved_support_files() -> list[Path]:
    return sorted(
        path
        for path in KNOWLEDGE.rglob("*")
        if path.is_file()
        and TEAMS not in path.parents
        and OUTPUT not in path.parents
        and path.suffix.lower() in {".md", ".txt"}
    )


def extract_draft_assets(team_name: str, owner: str | None, roster_id: int) -> tuple[list[str], list[str]]:
    assets: list[str] = []
    sources: list[str] = []
    owner_markers = {
        team_name.casefold(),
        f"current owner team: {team_name}".casefold(),
        f"current owner roster id: {roster_id}".casefold(),
        f"owner roster id: {roster_id}".casefold(),
    }
    if owner:
        owner_markers.add(owner.casefold())

    for path in approved_support_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue

        matched_file = False
        index = 0
        while index < len(lines):
            heading = PICK_HEADING_RE.match(lines[index])
            if not heading:
                index += 1
                continue

            end = index + 1
            while end < len(lines) and not PICK_HEADING_RE.match(lines[end]):
                end += 1
            block = lines[index:end]
            block_text = "\n".join(block).casefold()

            if any(marker in block_text for marker in owner_markers):
                pick_label = heading.group(1).strip()
                card_fields = fields(block[1:])
                c_avi = card_fields.get("Championship AVI (C-AVI, 0-100)") or card_fields.get("C-AVI")
                d_avi = card_fields.get("Dynasty AVI (D-AVI, 0-100)") or card_fields.get("D-AVI")
                value_parts = [pick_label]
                if c_avi and c_avi != "None":
                    value_parts.append(f"C-AVI {c_avi}")
                if d_avi and d_avi != "None":
                    value_parts.append(f"D-AVI {d_avi}")
                asset = " | ".join(value_parts)
                if asset not in assets:
                    assets.append(asset)
                    matched_file = True

            index = end

        if matched_file:
            sources.append(str(path.relative_to(ROOT)))

    return assets, sources


def parse_team(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    identity = fields(section(lines, "## Team Identity"))
    counts = fields(section(lines, "## Roster Counts"))
    scores = fields(section(lines, "## Raw Team Score Inputs, Not Static Rankings"))

    if not identity.get("Team name") or not identity.get("Roster ID"):
        raise ValueError(f"Missing required Team Identity fields in {path}")

    lineup = []
    for line in section(lines, "## Championship Lineup Used For Raw C-AVI Input"):
        match = LINEUP_RE.match(line)
        if match:
            lineup.append({
                "slot": match.group(1),
                "player": match.group(2),
                "c_avi": float(match.group(3)),
                "d_avi": float(match.group(4)),
            })
    if not lineup:
        raise ValueError(f"Missing championship lineup in {path}")

    players = []
    current = None
    for line in section(lines, "## Current Roster — All Player Cards"):
        player_match = PLAYER_RE.match(line)
        if player_match:
            if current:
                players.append(current)
            current = {"name": player_match.group(1)}
        elif current:
            field_match = FIELD_RE.match(line)
            if field_match:
                current[field_match.group(1).strip()] = field_match.group(2).strip()
    if current:
        players.append(current)

    roster_id = int(identity["Roster ID"])
    draft_assets, draft_sources = extract_draft_assets(
        identity["Team name"], identity.get("Owner display name"), roster_id
    )

    return {
        "source_file": str(path.relative_to(ROOT)),
        "team_name": identity["Team name"],
        "roster_id": roster_id,
        "owner": identity.get("Owner display name"),
        "source_updated": identity.get("Last updated from Sleeper exports"),
        "counts": counts,
        "scores": scores,
        "lineup": lineup,
        "players": players,
        "draft_assets": draft_assets,
        "draft_sources": draft_sources,
    }


def preseason_summary(team: dict, now: datetime) -> dict:
    lineup = team["lineup"]
    sorted_lineup = sorted(lineup, key=lambda item: item["c_avi"], reverse=True)
    anchors = sorted_lineup[:3]
    pressure = min(lineup, key=lambda item: item["c_avi"])
    anchor_names = ", ".join(item["player"] for item in anchors[:-1]) + f", and {anchors[-1]['player']}"
    lineup_avg = float(team["scores"].get("championship_lineup_c_avi_avg", "0"))
    roster_d_avg = float(team["scores"].get("offensive_roster_d_avi_avg", "0"))
    offense_count = int(team["counts"].get("offense", "0"))
    depth_count = max(offense_count - len(lineup), 0)

    unavailable = [
        player["name"] for player in team["players"]
        if player.get("Status") not in (None, "Active")
    ]
    active_count = sum(
        1 for player in team["players"]
        if player.get("Status") == "Active" and player.get("Category") == "offense"
    )
    health_body = (
        f"The current team file flags {', '.join(unavailable)} outside Active status."
        if unavailable
        else f"All {active_count} offensive players in the current team file are marked Active."
    )

    draft_body = (
        "Verified draft assets: " + "; ".join(team["draft_assets"]) + "."
        if team["draft_assets"]
        else "No franchise-owned pick card was found in the approved draft-pick knowledge file."
    )

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
            f"led by {anchor_names}. The clearest lineup pressure point is the {pressure['slot']} slot "
            f"held by {pressure['player']} at {pressure['c_avi']:.1f} C-AVI."
        ),
        "sections": [
            {
                "id": "competitive-core",
                "title": "Competitive Core",
                "body": (
                    f"The three highest C-AVI starters are {anchors[0]['player']} ({anchors[0]['c_avi']:.1f}), "
                    f"{anchors[1]['player']} ({anchors[1]['c_avi']:.1f}), and {anchors[2]['player']} "
                    f"({anchors[2]['c_avi']:.1f})."
                ),
            },
            {
                "id": "lineup-pressure-point",
                "title": "Lineup Pressure Point",
                "body": (
                    f"{pressure['player']} is the lowest C-AVI starter in the verified championship lineup at "
                    f"{pressure['c_avi']:.1f}. Any acquisition should clear that lineup threshold."
                ),
            },
            {
                "id": "depth-and-flexibility",
                "title": "Depth and Flexibility",
                "body": (
                    f"The team file contains {offense_count} offensive players, with {depth_count} outside the modeled "
                    f"starting eight. The offensive roster D-AVI average is {roster_d_avg:.2f}."
                ),
            },
            {"id": "availability", "title": "Availability", "body": health_body},
            {"id": "draft-assets", "title": "Draft Assets", "body": draft_body},
        ],
        "source": {
            "policy": "AVI-Core/knowledge only",
            "files": [team["source_file"], *team["draft_sources"]],
            "source_last_updated": team["source_updated"],
            "external_sources_used": False,
            "conversation_context_used": False,
        },
    }


def regular_season_summary(team: dict, now: datetime) -> dict:
    summary = preseason_summary(team, now)
    summary["season_phase"] = "regular_season"
    summary["headline"] = f"{team['team_name']}: Weekly Franchise Brief"
    summary["sections"].extend([
        {
            "id": "matchup-recap",
            "title": "Matchup Recap",
            "body": "Not published: no completed weekly matchup section exists in the approved knowledge files.",
        },
        {
            "id": "standings",
            "title": "Standings and Playoff Position",
            "body": "Not published: no current standings section exists in the approved knowledge files.",
        },
    ])
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
