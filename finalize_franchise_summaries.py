from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SUMMARY_DIR = ROOT / "knowledge" / "franchise_summaries"
TEAMS_DIR = ROOT / "knowledge" / "teams"
PICK_VALUES_PATH = ROOT / "data" / "processed" / "reports" / "draft_pick_values.json"
HISTORICAL_TRADES_PATH = ROOT / "data" / "processed" / "reports" / "historical_trades.json"
MANIFEST_PATH = ROOT / "data" / "raw" / "sleeper" / "manifest.json"
CURRENT_SEASON = 2026
EXPECTED_FRANCHISE_COUNT = 16

BLACKLISTED_TRANSACTION_IDS = {
    "1384427332722233344",
    "1384401342625226752",
    "1384338064138043392",
}

NO_PICK_RECOMMENDATION_RE = re.compile(
    r"no owned pick card|no verified.*pick|"
    r"no franchise-owned pick card|"
    r"avoid assuming unavailable draft leverage",
    re.IGNORECASE,
)

FIELD_RE = re.compile(r"^- ([^:]+):\s*(.*)$")
PLAYER_RE = re.compile(r"^### PLAYER: (.+)$")
POWER_SLOTS = ("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX")


def number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def round_to_tenth(value: float) -> float:
    return round(value * 10) / 10


def first_round_pick_value(slot: int) -> float:
    if slot <= 4:
        return round_to_tenth(91 - (slot - 1) * 1.2)
    if slot <= 11:
        return round_to_tenth(87.4 - (slot - 4) * 1.7)
    return round_to_tenth(75.5 - (slot - 11) * 2)


def first_round_average_value() -> float:
    return round_to_tenth(
        sum(first_round_pick_value(slot) for slot in range(1, 17)) / 16
    )


def projected_draft_pick_value(season: int, round_value: int) -> float:
    if round_value == 1:
        return first_round_average_value()
    base = {2: 54.0, 3: 34.0}.get(round_value, 22.0)
    years_out = max(0, season - CURRENT_SEASON)
    return min(95.0, max(8.0, round_to_tenth(base - years_out * 6)))


def active_league_dir() -> Path:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    seasons = [
        row for row in manifest.get("season_results", [])
        if row.get("league_id") and isinstance(row.get("season"), int)
    ]
    if not seasons:
        raise RuntimeError("Sleeper manifest does not contain a current league")
    latest = max(seasons, key=lambda row: int(row["season"]))
    return (
        ROOT
        / "data"
        / "raw"
        / "sleeper"
        / "leagues"
        / f"{latest['season']}_{latest['league_id']}"
    )


def active_traded_picks_path() -> Path | None:
    path = active_league_dir() / "traded_picks.json"
    return path if path.is_file() else None


def load_live_pick_owners() -> dict[tuple[int, int, int], int]:
    path = active_traded_picks_path()
    if not path:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    owners: dict[tuple[int, int, int], int] = {}
    for pick in payload if isinstance(payload, list) else []:
        if not isinstance(pick, dict):
            continue
        try:
            key = (
                int(pick["season"]),
                int(pick["round"]),
                int(pick["roster_id"]),
            )
            owners[key] = int(pick["owner_id"])
        except (KeyError, TypeError, ValueError):
            continue
    return owners


def load_future_pick_totals() -> dict[int, float]:
    """Mirror Autobots HQ's 2027+ ownership reconstruction and valuation."""
    values = json.loads(PICK_VALUES_PATH.read_text(encoding="utf-8"))
    historical = json.loads(HISTORICAL_TRADES_PATH.read_text(encoding="utf-8"))
    raw = [row for row in values.get("picks", []) if isinstance(row, dict)]
    live_owners = load_live_pick_owners()

    roster_ids: set[int] = set()
    future_seasons: set[int] = set()
    max_round = 0
    for pick in raw:
        try:
            season = int(pick.get("season") or 0)
            round_value = int(pick.get("round") or 0)
        except (TypeError, ValueError):
            continue
        max_round = max(max_round, round_value)
        for field in ("original_roster_id", "current_owner_roster_id"):
            try:
                roster_ids.add(int(pick.get(field)))
            except (TypeError, ValueError):
                pass
        if (
            pick.get("validation_status") == "future_order_tbd"
            or str(pick.get("current_owner_team") or "").strip().casefold() == "tbd"
        ):
            future_seasons.add(season)

    if len(roster_ids) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_FRANCHISE_COUNT} roster ids, found {len(roster_ids)}"
        )

    rounds_per_season = max(max_round, 10)
    ledger: dict[tuple[int, int, int], int] = {}
    for season in future_seasons:
        if season <= CURRENT_SEASON:
            continue
        for round_value in range(1, rounds_per_season + 1):
            for original_id in roster_ids:
                ledger[(season, round_value, original_id)] = original_id

    for trade in historical.get("trades", []):
        if not isinstance(trade, dict):
            continue
        if str(trade.get("transaction_id") or "") in BLACKLISTED_TRANSACTION_IDS:
            continue
        for team in trade.get("teams", []):
            if not isinstance(team, dict):
                continue
            try:
                receiver_id = int(team.get("roster_id"))
            except (TypeError, ValueError):
                continue
            if receiver_id not in roster_ids:
                continue
            for pick in team.get("picks_received", []):
                if not isinstance(pick, dict):
                    continue
                try:
                    key = (
                        int(pick.get("season")),
                        int(pick.get("round")),
                        int(pick.get("original_roster_id")),
                    )
                except (TypeError, ValueError):
                    continue
                if key in ledger:
                    ledger[key] = receiver_id

    for key, owner_id in live_owners.items():
        if key in ledger and owner_id in roster_ids:
            ledger[key] = owner_id

    totals = {roster_id: 0.0 for roster_id in roster_ids}
    for (season, round_value, _original_id), owner_id in ledger.items():
        totals[owner_id] += projected_draft_pick_value(season, round_value)

    return {roster_id: round(total, 2) for roster_id, total in totals.items()}


def parse_team_player_catalog() -> dict[str, dict[str, Any]]:
    """Build one valuation card per Sleeper player id from all 16 team files."""
    catalog: dict[str, dict[str, Any]] = {}
    for path in sorted(TEAMS_DIR.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        current: dict[str, Any] | None = None
        in_players = False
        for line in lines:
            if line == "## Current Roster — All Player Cards":
                in_players = True
                continue
            if in_players and line.startswith("## "):
                break
            if not in_players:
                continue
            match = PLAYER_RE.match(line)
            if match:
                if current and current.get("Player ID"):
                    catalog[str(current["Player ID"])] = current
                current = {"name": match.group(1).strip()}
                continue
            if current:
                field = FIELD_RE.match(line)
                if field:
                    current[field.group(1).strip()] = field.group(2).strip()
        if current and current.get("Player ID"):
            catalog[str(current["Player ID"])] = current
    return catalog


def load_live_rosters() -> dict[int, list[str]]:
    path = active_league_dir() / "rosters.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[int, list[str]] = {}
    for roster in payload if isinstance(payload, list) else []:
        if not isinstance(roster, dict):
            continue
        try:
            roster_id = int(roster["roster_id"])
        except (KeyError, TypeError, ValueError):
            continue
        result[roster_id] = [str(player_id) for player_id in (roster.get("players") or [])]
    if len(result) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_FRANCHISE_COUNT} live Sleeper rosters, found {len(result)}"
        )
    return result


def player_cavi(player: dict[str, Any]) -> float:
    return number(player.get("Championship AVI (C-AVI, 0-100)"))


def player_davi(player: dict[str, Any]) -> float:
    return number(player.get("Dynasty AVI (D-AVI, 0-100)"))


def player_position(player: dict[str, Any]) -> str:
    return str(player.get("Position") or "").strip()


def eligible(player: dict[str, Any], slot: str) -> bool:
    position = player_position(player)
    return position in {"RB", "WR", "TE"} if slot == "FLEX" else position == slot


def canonical_lineup(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used: set[str] = set()
    lineup: list[dict[str, Any]] = []
    for slot in POWER_SLOTS:
        candidates = [
            player for player in players
            if str(player.get("Player ID") or "") not in used
            and eligible(player, slot)
            and player_cavi(player) > 0
        ]
        candidates.sort(key=lambda player: (player_cavi(player), player_davi(player)), reverse=True)
        if not candidates:
            continue
        player = candidates[0]
        player_id = str(player.get("Player ID") or "")
        used.add(player_id)
        lineup.append({
            "slot": slot,
            "player": str(player.get("name") or player.get("Player name") or "Unknown"),
            "player_id": player_id,
            "c_avi": round(player_cavi(player), 1),
            "d_avi": round(player_davi(player), 1),
        })
    return lineup


def live_team_facts() -> dict[int, dict[str, Any]]:
    catalog = parse_team_player_catalog()
    live_rosters = load_live_rosters()
    facts: dict[int, dict[str, Any]] = {}
    for roster_id, player_ids in live_rosters.items():
        players = [catalog[player_id] for player_id in player_ids if player_id in catalog]
        lineup = canonical_lineup(players)
        if len(lineup) != len(POWER_SLOTS):
            raise RuntimeError(
                f"Roster {roster_id} produced only {len(lineup)} canonical offensive starters"
            )
        facts[roster_id] = {
            "players": players,
            "player_ids": set(player_ids),
            "lineup": lineup,
            "projected_score": round(sum(item["c_avi"] for item in lineup), 2),
            "player_d_avi": round(sum(player_davi(player) for player in players), 2),
        }
    return facts


def remove_disallowed_pick_language(summary: dict[str, Any]) -> None:
    moves = [
        move
        for move in summary.get("gap_closing_moves", [])
        if not NO_PICK_RECOMMENDATION_RE.search(str(move))
    ]
    summary["gap_closing_moves"] = moves
    for section in summary.get("sections", []):
        if section.get("id") == "close-the-gap":
            section["items"] = moves
            section["body"] = " ".join(moves)
        elif section.get("id") == "draft-assets":
            body = str(section.get("body") or "")
            if NO_PICK_RECOMMENDATION_RE.search(body):
                section["body"] = (
                    "Draft capital is included only when verified by the canonical "
                    "draft-pick ledger."
                )


def section_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(section.get("id")): section
        for section in summary.get("sections", [])
        if isinstance(section, dict) and section.get("id")
    }


def refresh_live_summary_fields(
    rows: list[tuple[Path, dict[str, Any]]],
    live: dict[int, dict[str, Any]],
) -> None:
    by_roster = {int(summary["roster_id"]): summary for _, summary in rows}
    ranking = sorted(
        by_roster,
        key=lambda roster_id: (
            live[roster_id]["projected_score"],
            live[roster_id]["player_d_avi"],
            str(by_roster[roster_id].get("franchise_name") or ""),
        ),
        reverse=True,
    )

    for rank, roster_id in enumerate(ranking, start=1):
        summary = by_roster[roster_id]
        facts = live[roster_id]
        lineup = sorted(facts["lineup"], key=lambda item: item["c_avi"], reverse=True)
        anchors = lineup[:3]
        pressure = min(facts["lineup"], key=lambda item: item["c_avi"])
        index = ranking.index(roster_id)
        above_id = ranking[index - 1] if index > 0 else None
        below_id = ranking[index + 1] if index + 1 < len(ranking) else None
        above_summary = by_roster.get(above_id) if above_id else None
        below_summary = by_roster.get(below_id) if below_id else None
        above_score = live[above_id]["projected_score"] if above_id else None
        below_score = live[below_id]["projected_score"] if below_id else None
        score = facts["projected_score"]
        gap = max(0.0, (above_score or score) - score)

        actions: list[str] = []
        if above_id and above_summary:
            target = min(100.0, pressure["c_avi"] + gap)
            actions.append(
                f"Raise the {pressure['slot']} slot above {pressure['player']}'s "
                f"{pressure['c_avi']:.1f} C-AVI baseline; a replacement near "
                f"{target:.1f} C-AVI would directly attack the {gap:.2f}-point "
                f"projected gap to {above_summary['franchise_name']}."
            )
        else:
            actions.append(
                f"Protect the league-leading projection and avoid replacing "
                f"{pressure['player']} unless the incoming option clearly exceeds "
                f"{pressure['c_avi']:.1f} C-AVI."
            )

        summary["schema_version"] = max(int(summary.get("schema_version") or 0), 10)
        summary["executive_summary"] = (
            f"{summary['franchise_name']} is projected #{rank} of 16 with a "
            f"{score:.2f} projected-starting-lineup C-AVI total, led by "
            f"{anchors[0]['player']}, {anchors[1]['player']}, and {anchors[2]['player']}. "
            f"The immediate priority is improving the {pressure['slot']} slot "
            "without weakening that core."
        )
        summary["projected_power"] = {
            "rank": rank,
            "league_size": EXPECTED_FRANCHISE_COUNT,
            "score": score,
            "team_above": (
                {
                    "name": above_summary["franchise_name"],
                    "rank": rank - 1,
                    "score": above_score,
                    "gap": gap,
                }
                if above_summary and above_score is not None
                else None
            ),
            "team_below": (
                {
                    "name": below_summary["franchise_name"],
                    "rank": rank + 1,
                    "score": below_score,
                    "gap": max(0.0, score - (below_score or score)),
                }
                if below_summary and below_score is not None
                else None
            ),
            "method": (
                "Canonical Autobots HQ 2026 Power ladder: sum of the best verified "
                "1QB/2RB/2WR/1TE/2FLEX lineup from current Sleeper roster ownership"
            ),
        }
        summary["gap_closing_moves"] = actions

        sections = section_map(summary)
        rank_body = f"Projected #{rank} of 16 at {score:.2f} lineup C-AVI."
        if above_summary and above_score is not None:
            rank_body += (
                f" {above_summary['franchise_name']} is immediately above at "
                f"{above_score:.2f}, a gap of {gap:.2f}."
            )
        if below_summary and below_score is not None:
            rank_body += (
                f" {below_summary['franchise_name']} is immediately behind at "
                f"{below_score:.2f}."
            )
        if "projected-power" in sections:
            sections["projected-power"]["body"] = rank_body
        if "competitive-core" in sections:
            sections["competitive-core"]["body"] = (
                f"The three highest C-AVI starters are {anchors[0]['player']} "
                f"({anchors[0]['c_avi']:.1f}), {anchors[1]['player']} "
                f"({anchors[1]['c_avi']:.1f}), and {anchors[2]['player']} "
                f"({anchors[2]['c_avi']:.1f})."
            )
        if "close-the-gap" in sections:
            sections["close-the-gap"]["items"] = actions
            sections["close-the-gap"]["body"] = " ".join(actions)
        if "lineup-pressure-point" in sections:
            sections["lineup-pressure-point"]["body"] = (
                f"{pressure['player']} is the lowest C-AVI starter in the current "
                f"verified Sleeper-owned lineup at {pressure['c_avi']:.1f}. Any "
                "acquisition should clear that exact lineup threshold."
            )

        rival = summary.get("rival_below")
        if below_summary is None:
            summary["rival_below"] = None
            if "rival-watch" in sections:
                sections["rival-watch"]["body"] = (
                    "This franchise is currently projected last, so there is no "
                    "team immediately beneath it."
                )
        elif isinstance(rival, dict):
            rival["franchise_name"] = below_summary["franchise_name"]
            rival["projected_rank"] = rank + 1
            rival["projected_score"] = below_score

        source = summary.setdefault("source", {})
        source["roster_ownership_source"] = str(
            (active_league_dir() / "rosters.json").relative_to(ROOT)
        )
        source["power_rank_source"] = "live Sleeper roster ownership + current AVI player cards"


def validate_rival(summary: dict[str, Any], path: Path) -> None:
    projected = summary.get("projected_power") or {}
    team_below = projected.get("team_below")
    rival = summary.get("rival_below")
    if team_below is None:
        if rival is not None:
            raise RuntimeError(f"Unexpected Rival Watch in {path}")
        return
    if not rival:
        raise RuntimeError(f"Missing Rival Watch in {path}")
    if rival.get("franchise_name") != team_below.get("name"):
        raise RuntimeError(f"Rival Watch franchise mismatch in {path}")
    if rival.get("projected_rank") != team_below.get("rank"):
        raise RuntimeError(f"Rival Watch rank mismatch in {path}")
    if "latest_activity" not in rival:
        raise RuntimeError(f"Rival Watch activity missing in {path}")


def validate_live_references(summary: dict[str, Any], live: dict[int, dict[str, Any]], path: Path) -> None:
    roster_id = int(summary["roster_id"])
    current_names = {
        str(player.get("name") or player.get("Player name") or "").casefold()
        for player in live[roster_id]["players"]
    }
    lineup_names = {item["player"].casefold() for item in live[roster_id]["lineup"]}
    sections = section_map(summary)
    pressure_body = str((sections.get("lineup-pressure-point") or {}).get("body") or "")
    core_body = str((sections.get("competitive-core") or {}).get("body") or "")
    moves = " ".join(str(move) for move in summary.get("gap_closing_moves", []))

    for body, label in ((pressure_body, "pressure point"), (core_body, "competitive core"), (moves, "gap-closing moves")):
        for name in lineup_names:
            if name and name in body.casefold():
                break
        else:
            if body:
                raise RuntimeError(f"{label} does not reference a current starter in {path}")

    latest_trade = summary.get("latest_trade") or {}
    sent_names: list[str] = []
    transaction_id = str(latest_trade.get("transaction_id") or "")
    if transaction_id and HISTORICAL_TRADES_PATH.is_file():
        historical = json.loads(HISTORICAL_TRADES_PATH.read_text(encoding="utf-8"))
        for trade in historical.get("trades", []):
            if str(trade.get("transaction_id") or "") != transaction_id:
                continue
            for team in trade.get("teams", []):
                if int(team.get("roster_id") or -1) == roster_id:
                    sent_names.extend(
                        str(player.get("name") if isinstance(player, dict) else player)
                        for player in team.get("players_sent", [])
                    )
            break
    advice_text = f"{moves} {pressure_body}".casefold()
    for name in sent_names:
        if name and name.casefold() not in current_names and name.casefold() in advice_text:
            raise RuntimeError(
                f"Traded-away player {name} leaked into current advice in {path}"
            )


def main() -> None:
    future_pick_totals = load_future_pick_totals()
    live = live_team_facts()
    paths = sorted(
        path for path in SUMMARY_DIR.glob("*.json")
        if path.name != "manifest.json"
    )
    if len(paths) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_FRANCHISE_COUNT} summaries, found {len(paths)}"
        )

    rows: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        summary = json.loads(path.read_text(encoding="utf-8"))
        roster_id = int(summary["roster_id"])
        future_pick_d_avi = future_pick_totals.get(roster_id, 0.0)
        player_d_avi = live[roster_id]["player_d_avi"]
        total = round(player_d_avi + future_pick_d_avi, 2)

        summary["schema_version"] = max(int(summary.get("schema_version") or 0), 10)
        summary["dynasty_power"] = {
            "rank": 0,
            "league_size": EXPECTED_FRANCHISE_COUNT,
            "score": total,
            "player_d_avi": round(player_d_avi, 2),
            "future_pick_d_avi": round(future_pick_d_avi, 2),
            "method": (
                "Canonical Autobots HQ D-AVI ladder: current Sleeper-owned roster "
                "D-AVI plus reconstructed live 2027+ ownership valued with the "
                "shared projected draft-pick curve"
            ),
        }
        remove_disallowed_pick_language(summary)
        rows.append((path, summary))

    refresh_live_summary_fields(rows, live)

    ranked = sorted(
        rows,
        key=lambda item: (
            number(item[1]["dynasty_power"]["score"]),
            number((item[1].get("projected_power") or {}).get("score")),
            str(item[1].get("franchise_name") or ""),
        ),
        reverse=True,
    )
    for rank, (_, summary) in enumerate(ranked, start=1):
        summary["dynasty_power"]["rank"] = rank

    for path, summary in rows:
        validate_rival(summary, path)
        validate_live_references(summary, live, path)
        path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    manifest_path = SUMMARY_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = max(int(manifest.get("schema_version") or 0), 10)
    manifest["projected_power_method"] = (
        "Canonical Autobots HQ 2026 Power ladder using current Sleeper roster "
        "ownership and the best 1QB/2RB/2WR/1TE/2FLEX C-AVI lineup"
    )
    manifest["dynasty_power_method"] = (
        "Current Sleeper-owned roster D-AVI plus reconstructed live 2027+ "
        "ownership valued with the canonical projected draft-pick curve"
    )
    manifest["roster_ownership_source"] = str(
        (active_league_dir() / "rosters.json").relative_to(ROOT)
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(
        "Finalized 16 summaries against live Sleeper ownership, canonical "
        "Autobots HQ power rankings, and current-lineup advice."
    )


if __name__ == "__main__":
    main()
