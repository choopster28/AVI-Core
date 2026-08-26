from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_DIR = ROOT / "knowledge" / "franchise_summaries"
TEAMS_DIR = ROOT / "knowledge" / "teams"
SLEEPER_MANIFEST = ROOT / "data" / "raw" / "sleeper" / "manifest.json"
EXPECTED_FRANCHISE_COUNT = 16

PLAYER_RE = re.compile(r"^### PLAYER: (.+)$")
FIELD_RE = re.compile(r"^- ([^:]+):\s*(.*)$")


def active_league_dir() -> Path:
    manifest = json.loads(SLEEPER_MANIFEST.read_text(encoding="utf-8"))
    seasons = [
        row for row in manifest.get("season_results", [])
        if isinstance(row, dict) and row.get("league_id") and row.get("season") is not None
    ]
    if not seasons:
        raise RuntimeError("No current Sleeper league found in manifest")
    latest = max(seasons, key=lambda row: int(row["season"]))
    return ROOT / "data" / "raw" / "sleeper" / "leagues" / f"{latest['season']}_{latest['league_id']}"


def player_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    for path in sorted(TEAMS_DIR.glob("*.md")):
        current: dict[str, Any] | None = None
        inside = False
        for line in path.read_text(encoding="utf-8").splitlines():
            if line == "## Current Roster — All Player Cards":
                inside = True
                continue
            if inside and line.startswith("## "):
                break
            if not inside:
                continue
            heading = PLAYER_RE.match(line)
            if heading:
                if current and current.get("Player ID"):
                    catalog[str(current["Player ID"])] = current
                current = {"name": heading.group(1).strip()}
                continue
            if current:
                field = FIELD_RE.match(line)
                if field:
                    current[field.group(1).strip()] = field.group(2).strip()
        if current and current.get("Player ID"):
            catalog[str(current["Player ID"])] = current
    return catalog


def current_rosters() -> dict[int, list[str]]:
    payload = json.loads((active_league_dir() / "rosters.json").read_text(encoding="utf-8"))
    rosters: dict[int, list[str]] = {}
    for row in payload:
        rosters[int(row["roster_id"])] = [str(player_id) for player_id in row.get("players") or []]
    if len(rosters) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_FRANCHISE_COUNT} current rosters, found {len(rosters)}")
    return rosters


def section_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(section.get("id")): section
        for section in summary.get("sections", [])
        if isinstance(section, dict) and section.get("id")
    }


def main() -> None:
    files = sorted(path for path in SUMMARY_DIR.glob("*.json") if path.name != "manifest.json")
    if len(files) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(f"Expected {EXPECTED_FRANCHISE_COUNT} summaries, found {len(files)}")

    summaries = {int(payload["roster_id"]): (path, payload) for path in files for payload in [json.loads(path.read_text(encoding="utf-8"))]}
    by_name = {payload["franchise_name"]: payload for _, payload in summaries.values()}
    catalog = player_catalog()
    rosters = current_rosters()

    for roster_id, (path, summary) in summaries.items():
        sections = section_map(summary)
        current_players = [catalog[player_id] for player_id in rosters[roster_id] if player_id in catalog]
        active_offense = sum(
            1 for player in current_players
            if str(player.get("Category") or "") == "offense" and str(player.get("Status") or "") == "Active"
        )
        unavailable = [
            str(player.get("name") or "") for player in current_players
            if str(player.get("Category") or "") == "offense"
            and str(player.get("Status") or "") not in {"", "Active"}
        ]
        if "availability" in sections:
            sections["availability"]["body"] = (
                f"Current Sleeper ownership has {active_offense} active offensive players; "
                f"non-active: {', '.join(unavailable)}."
                if unavailable
                else f"All {active_offense} offensive players on the current Sleeper-owned roster are marked Active."
            )

        future_pick_value = float((summary.get("dynasty_power") or {}).get("future_pick_d_avi") or 0)
        if "draft-assets" in sections:
            sections["draft-assets"]["body"] = (
                f"Verified current future draft capital contributes {future_pick_value:.1f} D-AVI to the franchise's dynasty total."
                if future_pick_value > 0
                else "No verified future draft-capital D-AVI is currently assigned to this franchise."
            )

        projected = summary.get("projected_power") or {}
        below = projected.get("team_below")
        if not below:
            summary["rival_below"] = None
            if "rival-watch" in sections:
                sections["rival-watch"]["body"] = "This franchise is currently projected last, so there is no team immediately beneath it."
        else:
            below_summary = by_name.get(str(below.get("name") or ""))
            if not below_summary:
                raise RuntimeError(f"Could not resolve current team_below for {path}")
            latest_trade = below_summary.get("latest_trade")
            rival_summary = (
                str(latest_trade.get("summary") or "")
                if isinstance(latest_trade, dict) and latest_trade.get("summary")
                else f"No verified recent trade is currently surfaced for {below_summary['franchise_name']}."
            )
            rival = summary.get("rival_below")
            if not isinstance(rival, dict):
                rival = {}
                summary["rival_below"] = rival
            rival.update({
                "franchise_name": below_summary["franchise_name"],
                "projected_rank": int(below["rank"]),
                "projected_score": float(below["score"]),
                "latest_trade": latest_trade if isinstance(latest_trade, dict) else None,
                "latest_activity": latest_trade if isinstance(latest_trade, dict) else None,
                "summary": rival_summary,
            })
            if "rival-watch" in sections:
                sections["rival-watch"]["body"] = rival_summary

        source = summary.setdefault("source", {})
        source["policy"] = "AVI-Core current Sleeper ownership + AVI valuation data"
        source["roster_ownership_source"] = str((active_league_dir() / "rosters.json").relative_to(ROOT))

        advice_text = " ".join(
            [
                str(summary.get("executive_summary") or ""),
                " ".join(str(move) for move in summary.get("gap_closing_moves", [])),
                str((sections.get("lineup-pressure-point") or {}).get("body") or ""),
                str((sections.get("competitive-core") or {}).get("body") or ""),
            ]
        ).casefold()
        current_names = {str(player.get("name") or "").casefold() for player in current_players}
        latest = summary.get("latest_trade") or {}
        latest_text = str(latest.get("summary") or "")
        if latest_text:
            sent_match = re.search(r"\bsent\s+(.+?)(?:\.|$)", latest_text, re.IGNORECASE)
            if sent_match:
                for raw_name in re.split(r",|\band\b", sent_match.group(1)):
                    candidate = raw_name.strip().casefold()
                    if not candidate or candidate.startswith("20"):
                        continue
                    if candidate not in current_names and candidate in advice_text:
                        raise RuntimeError(f"Traded-away asset leaked into current advice for {path}: {raw_name.strip()}")

        path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print("Reconciled all franchise-summary sections to current roster ownership and current power neighbors.")


if __name__ == "__main__":
    main()
