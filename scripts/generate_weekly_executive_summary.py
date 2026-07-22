from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE = ROOT / "knowledge"
TEAMS = KNOWLEDGE / "teams"
OUTPUT = KNOWLEDGE / "franchise_summaries"
HISTORICAL_TRADES = KNOWLEDGE / "02_AVI_Historical_Trades.md"
MOUNTAIN = ZoneInfo("America/Denver")

FIELD_RE = re.compile(r"^- ([^:]+):\s*(.*)$")
LINEUP_RE = re.compile(r"^- (QB|RB|WR|TE|FLEX): (.+?) \| C-AVI: ([0-9.]+) \| D-AVI: ([0-9.]+)$")
PLAYER_RE = re.compile(r"^### PLAYER: (.+)$")
PICK_HEADING_RE = re.compile(r"^## PICK:\s*(.+?)(?:\s*\||$)")
TRADE_HEADING_RE = re.compile(r"^### TRADE:\s*(\S+)")
TRADE_TEAM_RE = re.compile(r"^####\s+(.+?)(?:\s+\(([^)]+)\))?\s*$")


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


def split_assets(value: str | None) -> list[str]:
    if not value or value.strip().casefold() == "none":
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


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


def parse_historical_trades() -> list[dict]:
    if not HISTORICAL_TRADES.exists():
        return []

    lines = HISTORICAL_TRADES.read_text(encoding="utf-8").splitlines()
    trades: list[dict] = []
    index = 0
    while index < len(lines):
        heading = TRADE_HEADING_RE.match(lines[index])
        if not heading:
            index += 1
            continue

        end = index + 1
        while end < len(lines) and not TRADE_HEADING_RE.match(lines[end]):
            end += 1
        block = lines[index:end]

        meta_lines: list[str] = []
        team_blocks: list[dict] = []
        cursor = 1
        while cursor < len(block) and not TRADE_TEAM_RE.match(block[cursor]):
            meta_lines.append(block[cursor])
            cursor += 1

        while cursor < len(block):
            team_heading = TRADE_TEAM_RE.match(block[cursor])
            if not team_heading:
                cursor += 1
                continue
            team_end = cursor + 1
            while team_end < len(block) and not TRADE_TEAM_RE.match(block[team_end]):
                team_end += 1
            team_fields = fields(block[cursor + 1 : team_end])
            team_blocks.append(
                {
                    "team_name": team_heading.group(1).strip(),
                    "owner": team_heading.group(2).strip() if team_heading.group(2) else None,
                    "players_received": split_assets(team_fields.get("Players received")),
                    "players_sent": split_assets(team_fields.get("Players sent")),
                    "picks_received": split_assets(team_fields.get("Picks received")),
                    "picks_sent": split_assets(team_fields.get("Picks sent")),
                }
            )
            cursor = team_end

        meta = fields(meta_lines)
        created_raw = meta.get("Created at UTC")
        try:
            created_at = datetime.fromisoformat(created_raw) if created_raw else None
        except ValueError:
            created_at = None

        trades.append(
            {
                "transaction_id": heading.group(1),
                "season": int(meta.get("Season", "0") or 0),
                "week": int(meta.get("Week", "0") or 0),
                "created_at": created_at,
                "teams": team_blocks,
            }
        )
        index = end

    return sorted(trades, key=lambda trade: trade["created_at"] or datetime.min, reverse=True)


def player_value(player: dict) -> tuple[float | None, float | None]:
    def number(key: str) -> float | None:
        raw = player.get(key)
        if raw in (None, "None", ""):
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    return number("Championship AVI (C-AVI, 0-100)"), number("Dynasty AVI (D-AVI, 0-100)")


def trade_relevance(trade: dict, side: dict, current_players: dict[str, dict]) -> float:
    score = 0.0
    for name in side["players_received"]:
        player = current_players.get(name.casefold())
        c_avi, d_avi = player_value(player) if player else (None, None)
        score += max(c_avi or 0, d_avi or 0, 35)
    score += 22 * len(side["players_sent"])
    score += 35 * sum("round 1" in pick.casefold() for pick in side["picks_received"] + side["picks_sent"])
    score += 10 * len(side["picks_received"] + side["picks_sent"])
    return score


def recent_trade_impacts(team: dict, now: datetime, ledger: list[dict]) -> list[dict]:
    team_key = team["team_name"].casefold()
    owner_key = (team.get("owner") or "").casefold()
    current_players = {player["name"].casefold(): player for player in team["players"]}
    lineup_by_name = {item["player"].casefold(): item for item in team["lineup"]}
    candidates: list[tuple[float, dict, dict]] = []
    cutoff = now.astimezone(ZoneInfo("UTC")) - timedelta(days=180)

    for trade in ledger:
        if trade["created_at"] and trade["created_at"] < cutoff:
            continue
        side = next(
            (
                entry
                for entry in trade["teams"]
                if entry["team_name"].casefold() == team_key
                or (owner_key and (entry.get("owner") or "").casefold() == owner_key)
            ),
            None,
        )
        if not side:
            continue
        candidates.append((trade_relevance(trade, side, current_players), trade, side))

    selected = sorted(
        candidates,
        key=lambda item: (item[0], item[1]["created_at"] or datetime.min),
        reverse=True,
    )[:3]
    selected.sort(key=lambda item: item[1]["created_at"] or datetime.min, reverse=True)

    impacts: list[dict] = []
    for _, trade, side in selected:
        counterparties = [entry["team_name"] for entry in trade["teams"] if entry is not side]
        date_label = trade["created_at"].astimezone(MOUNTAIN).strftime("%B %-d") if trade["created_at"] else "Date unavailable"
        acquired = side["players_received"] + side["picks_received"]
        sent = side["players_sent"] + side["picks_sent"]

        opening = f"On {date_label}, {team['team_name']}"
        if counterparties:
            opening += f" traded with {', '.join(counterparties)}"
        if acquired:
            opening += f" and acquired {', '.join(acquired)}"
        if sent:
            opening += f" while sending {', '.join(sent)}"
        opening += "."

        current_incoming: list[str] = []
        for name in side["players_received"]:
            player = current_players.get(name.casefold())
            if not player:
                continue
            c_avi, d_avi = player_value(player)
            lineup = lineup_by_name.get(name.casefold())
            value_bits = []
            if c_avi is not None:
                value_bits.append(f"{c_avi:.1f} C-AVI")
            if d_avi is not None:
                value_bits.append(f"{d_avi:.1f} D-AVI")
            role = f"the verified {lineup['slot']} starter" if lineup else "on the current roster"
            current_incoming.append(f"{name} is now {role}" + (f" at {' and '.join(value_bits)}" if value_bits else ""))

        impact_parts: list[str] = []
        if current_incoming:
            impact_parts.append("; ".join(current_incoming) + ".")
        if side["picks_sent"]:
            impact_parts.append(f"The transaction moved out {len(side['picks_sent'])} draft asset{'s' if len(side['picks_sent']) != 1 else ''}, which reduces the franchise's remaining draft flexibility relative to keeping those picks.")
        if side["picks_received"]:
            impact_parts.append(f"It added {len(side['picks_received'])} draft asset{'s' if len(side['picks_received']) != 1 else ''} to the franchise's asset base at the time of the deal.")
        if not impact_parts:
            impact_parts.append("The current knowledge files verify the asset exchange but do not provide enough current valuation detail for a stronger impact conclusion.")

        impacts.append(
            {
                "transaction_id": trade["transaction_id"],
                "created_at": trade["created_at"].isoformat() if trade["created_at"] else None,
                "counterparties": counterparties,
                "players_received": side["players_received"],
                "players_sent": side["players_sent"],
                "picks_received": side["picks_received"],
                "picks_sent": side["picks_sent"],
                "summary": opening + " " + " ".join(impact_parts),
            }
        )

    return impacts


def parse_team(path: Path, ledger: list[dict], now: datetime) -> dict:
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

    team = {
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
    team["recent_trades"] = recent_trade_impacts(team, now, ledger)
    return team


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
    trade_body = (
        " ".join(trade["summary"] for trade in team["recent_trades"])
        if team["recent_trades"]
        else "No recent franchise trade met the relevance threshold in the authoritative historical trade ledger."
    )

    source_files = [team["source_file"], *team["draft_sources"]]
    if team["recent_trades"]:
        source_files.append(str(HISTORICAL_TRADES.relative_to(ROOT)))

    return {
        "schema_version": 3,
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
        "recent_trades": team["recent_trades"],
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
                "id": "recent-trade-impact",
                "title": "Recent Trade Impact",
                "body": trade_body,
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
            "files": list(dict.fromkeys(source_files)),
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

    ledger = parse_historical_trades()
    written = []
    for path in team_paths:
        team = parse_team(path, ledger, now)
        summary = preseason_summary(team, now) if now.month < 9 else regular_season_summary(team, now)
        destination = OUTPUT / f"{summary['franchise_id']}.json"
        destination.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        written.append(destination.name)

    manifest = {
        "schema_version": 2,
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
