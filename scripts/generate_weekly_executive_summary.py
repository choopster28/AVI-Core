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
UTC = ZoneInfo("UTC")

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


def number(value: object, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "", "None") else default
    except (TypeError, ValueError):
        return default


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
                parts = [pick_label]
                if c_avi and c_avi != "None":
                    parts.append(f"C-AVI {c_avi}")
                if d_avi and d_avi != "None":
                    parts.append(f"D-AVI {d_avi}")
                asset = " | ".join(parts)
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
            team_blocks.append({
                "team_name": team_heading.group(1).strip(),
                "owner": team_heading.group(2).strip() if team_heading.group(2) else None,
                "players_received": split_assets(team_fields.get("Players received")),
                "players_sent": split_assets(team_fields.get("Players sent")),
                "picks_received": split_assets(team_fields.get("Picks received")),
                "picks_sent": split_assets(team_fields.get("Picks sent")),
            })
            cursor = team_end
        meta = fields(meta_lines)
        created_raw = meta.get("Created at UTC")
        try:
            created_at = datetime.fromisoformat(created_raw) if created_raw else None
        except ValueError:
            created_at = None
        trades.append({
            "transaction_id": heading.group(1),
            "season": int(meta.get("Season", "0") or 0),
            "week": int(meta.get("Week", "0") or 0),
            "created_at": created_at,
            "teams": team_blocks,
        })
        index = end
    return sorted(trades, key=lambda trade: trade["created_at"] or datetime.min.replace(tzinfo=UTC), reverse=True)


def parse_team(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    identity = fields(section(lines, "## Team Identity"))
    counts = fields(section(lines, "## Roster Counts"))
    scores = fields(section(lines, "## Raw Team Score Inputs, Not Static Rankings"))
    if not identity.get("Team name") or not identity.get("Roster ID"):
        raise ValueError(f"Missing required Team Identity fields in {path}")

    lineup: list[dict] = []
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

    players: list[dict] = []
    current: dict | None = None
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
    draft_assets, draft_sources = extract_draft_assets(identity["Team name"], identity.get("Owner display name"), roster_id)
    lineup_avg = number(scores.get("championship_lineup_c_avi_avg"))
    roster_d_avg = number(scores.get("offensive_roster_d_avi_avg"))
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
        "projected_score": lineup_avg,
        "dynasty_score": roster_d_avg,
    }


def trade_side(trade: dict, team: dict) -> dict | None:
    team_key = team["team_name"].casefold()
    owner_key = (team.get("owner") or "").casefold()
    return next((entry for entry in trade["teams"] if entry["team_name"].casefold() == team_key or (owner_key and (entry.get("owner") or "").casefold() == owner_key)), None)


def latest_trade(team: dict, ledger: list[dict], now: datetime) -> dict | None:
    cutoff = now.astimezone(UTC) - timedelta(days=365)
    current_players = {player["name"].casefold(): player for player in team["players"]}
    lineup_by_name = {item["player"].casefold(): item for item in team["lineup"]}
    for trade in ledger:
        if trade["created_at"] and trade["created_at"] < cutoff:
            continue
        side = trade_side(trade, team)
        if not side:
            continue
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

        effects: list[str] = []
        for name in side["players_received"]:
            player = current_players.get(name.casefold())
            if not player:
                continue
            lineup = lineup_by_name.get(name.casefold())
            c_avi = number(player.get("Championship AVI (C-AVI, 0-100)"), -1)
            d_avi = number(player.get("Dynasty AVI (D-AVI, 0-100)"), -1)
            role = f"the current {lineup['slot']} starter" if lineup else "on the current roster"
            values = []
            if c_avi >= 0:
                values.append(f"{c_avi:.1f} C-AVI")
            if d_avi >= 0:
                values.append(f"{d_avi:.1f} D-AVI")
            effects.append(f"{name} is now {role}" + (f" at {' and '.join(values)}" if values else ""))
        if side["picks_sent"]:
            effects.append(f"The deal sent out {len(side['picks_sent'])} draft asset{'s' if len(side['picks_sent']) != 1 else ''}, reducing future flexibility")
        if side["picks_received"]:
            effects.append(f"The deal added {len(side['picks_received'])} draft asset{'s' if len(side['picks_received']) != 1 else ''}")
        impact = "; ".join(effects) + "." if effects else "The ledger verifies the exchange, but the current files do not support a stronger impact conclusion."
        return {
            "transaction_id": trade["transaction_id"],
            "created_at": trade["created_at"].isoformat() if trade["created_at"] else None,
            "counterparties": counterparties,
            "players_received": side["players_received"],
            "players_sent": side["players_sent"],
            "picks_received": side["picks_received"],
            "picks_sent": side["picks_sent"],
            "summary": f"{opening} {impact}",
        }
    return None


def weak_point(team: dict) -> dict:
    return min(team["lineup"], key=lambda item: item["c_avi"])


def gap_actions(team: dict, above: dict | None) -> list[str]:
    pressure = weak_point(team)
    actions: list[str] = []
    if above:
        score_gap = max(0.0, above["projected_score"] - team["projected_score"])
        above_floor = weak_point(above)
        target = max(pressure["c_avi"] + score_gap * 8, above_floor["c_avi"])
        actions.append(
            f"Raise the {pressure['slot']} slot above {pressure['player']}'s {pressure['c_avi']:.1f} C-AVI baseline; a replacement near {target:.1f} C-AVI would directly attack the {score_gap:.2f}-point projected gap to {above['team_name']}."
        )
    else:
        actions.append(f"Protect the league-leading projection and avoid replacing {pressure['player']} unless the incoming option clearly exceeds {pressure['c_avi']:.1f} C-AVI.")
    if team["draft_assets"]:
        actions.append("Use draft capital as a targeted sweetener for a verified starting-lineup upgrade, not for additional bench depth.")
    else:
        actions.append("Because no owned pick card is verified, prioritize player-for-player consolidation and avoid assuming unavailable draft leverage.")
    return actions[:2]


def rival_snapshot(team: dict | None, ledger: list[dict], now: datetime) -> dict | None:
    if not team:
        return None
    trade = latest_trade(team, ledger, now)
    return {
        "franchise_name": team["team_name"],
        "projected_rank": team["projected_rank"],
        "projected_score": team["projected_score"],
        "latest_trade": trade,
        "summary": trade["summary"] if trade else f"No trade for {team['team_name']} was found in the last 365 days of the authoritative ledger.",
    }


def build_summary(team: dict, above: dict | None, below: dict | None, ledger: list[dict], now: datetime) -> dict:
    lineup = sorted(team["lineup"], key=lambda item: item["c_avi"], reverse=True)
    anchors = lineup[:3]
    pressure = weak_point(team)
    unavailable = [player["name"] for player in team["players"] if player.get("Status") not in (None, "Active")]
    active_count = sum(1 for player in team["players"] if player.get("Status") == "Active" and player.get("Category") == "offense")
    own_trade = latest_trade(team, ledger, now)
    below_snapshot = rival_snapshot(below, ledger, now)
    above_gap = max(0.0, above["projected_score"] - team["projected_score"]) if above else 0.0
    actions = gap_actions(team, above)
    draft_body = "Verified draft assets: " + "; ".join(team["draft_assets"]) + "." if team["draft_assets"] else "No franchise-owned pick card was found in the approved draft-pick knowledge file."
    health_body = f"The current team file flags {', '.join(unavailable)} outside Active status." if unavailable else f"All {active_count} offensive players in the current team file are marked Active."
    rank_body = f"Projected #{team['projected_rank']} of 16 at {team['projected_score']:.2f} lineup C-AVI."
    if above:
        rank_body += f" {above['team_name']} is immediately above at {above['projected_score']:.2f}, a gap of {above_gap:.2f}."
    if below:
        rank_body += f" {below['team_name']} is immediately behind at {below['projected_score']:.2f}."

    sections = [
        {"id": "projected-power", "title": "Projected Power Position", "body": rank_body},
        {"id": "competitive-core", "title": "Competitive Core", "body": f"The three highest C-AVI starters are {anchors[0]['player']} ({anchors[0]['c_avi']:.1f}), {anchors[1]['player']} ({anchors[1]['c_avi']:.1f}), and {anchors[2]['player']} ({anchors[2]['c_avi']:.1f})."},
        {"id": "latest-trade-impact", "title": "Latest Trade Impact", "body": own_trade["summary"] if own_trade else "No franchise trade was found in the last 365 days of the authoritative historical ledger."},
        {"id": "close-the-gap", "title": "Moves to Close the Gap", "body": " ".join(actions), "items": actions},
        {"id": "rival-watch", "title": "Rival Watch", "body": below_snapshot["summary"] if below_snapshot else "This franchise is currently projected last, so there is no team immediately beneath it."},
        {"id": "lineup-pressure-point", "title": "Lineup Pressure Point", "body": f"{pressure['player']} is the lowest C-AVI starter in the verified championship lineup at {pressure['c_avi']:.1f}. Any acquisition should clear that exact lineup threshold."},
        {"id": "availability", "title": "Availability", "body": health_body},
        {"id": "draft-assets", "title": "Draft Assets", "body": draft_body},
    ]

    source_files = [team["source_file"], *team["draft_sources"]]
    if own_trade or (below_snapshot and below_snapshot["latest_trade"]):
        source_files.append(str(HISTORICAL_TRADES.relative_to(ROOT)))

    phase = "preseason" if now.month < 9 else "regular_season"
    if phase == "regular_season":
        sections.extend([
            {"id": "matchup-recap", "title": "Matchup Recap", "body": "Not published: no completed weekly matchup section exists in the approved knowledge files."},
            {"id": "standings", "title": "Standings and Playoff Position", "body": "Not published: no current standings section exists in the approved knowledge files."},
        ])

    return {
        "schema_version": 4,
        "franchise_id": slugify(team["team_name"]),
        "franchise_name": team["team_name"],
        "roster_id": team["roster_id"],
        "owner_display_name": team["owner"],
        "season_phase": phase,
        "reporting_period": now.strftime("Week of %B %-d, %Y"),
        "generated_at": now.isoformat(),
        "refresh_schedule": "Wednesdays at 11:00 AM America/Denver",
        "headline": f"{team['team_name']}: {'Preseason' if phase == 'preseason' else 'Weekly'} Front Office Brief",
        "executive_summary": f"{team['team_name']} is projected #{team['projected_rank']} of 16 with a {team['projected_score']:.2f} championship-lineup C-AVI average, led by {anchors[0]['player']}, {anchors[1]['player']}, and {anchors[2]['player']}. The immediate priority is improving the {pressure['slot']} slot without weakening that core.",
        "projected_power": {
            "rank": team["projected_rank"],
            "league_size": 16,
            "score": team["projected_score"],
            "team_above": {"name": above["team_name"], "rank": above["projected_rank"], "score": above["projected_score"], "gap": above_gap} if above else None,
            "team_below": {"name": below["team_name"], "rank": below["projected_rank"], "score": below["projected_score"], "gap": max(0.0, team["projected_score"] - below["projected_score"])} if below else None,
            "method": "Verified championship-lineup C-AVI average from all 16 AVI-Core knowledge team files",
        },
        "latest_trade": own_trade,
        "gap_closing_moves": actions,
        "rival_below": below_snapshot,
        "sections": sections,
        "source": {
            "policy": "AVI-Core/knowledge only",
            "files": list(dict.fromkeys(source_files)),
            "source_last_updated": team["source_updated"],
            "external_sources_used": False,
            "conversation_context_used": False,
        },
    }


def main() -> None:
    now = datetime.now(MOUNTAIN)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    team_paths = sorted(TEAMS.glob("*.md"))
    if len(team_paths) != 16:
        raise RuntimeError(f"Expected 16 team files in {TEAMS}, found {len(team_paths)}")

    ledger = parse_historical_trades()
    teams = [parse_team(path) for path in team_paths]
    ranked = sorted(teams, key=lambda team: (team["projected_score"], team["dynasty_score"], team["team_name"]), reverse=True)
    for index, team in enumerate(ranked, start=1):
        team["projected_rank"] = index

    written: list[str] = []
    for index, team in enumerate(ranked):
        above = ranked[index - 1] if index > 0 else None
        below = ranked[index + 1] if index + 1 < len(ranked) else None
        summary = build_summary(team, above, below, ledger, now)
        destination = OUTPUT / f"{summary['franchise_id']}.json"
        destination.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        written.append(destination.name)

    manifest = {
        "schema_version": 3,
        "generated_at": now.isoformat(),
        "refresh_schedule": "Wednesdays at 11:00 AM America/Denver",
        "source_policy": "AVI-Core/knowledge only",
        "franchise_count": len(written),
        "projected_power_method": "Verified championship-lineup C-AVI average",
        "files": sorted(written),
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(written)} rival-aware franchise summaries to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
