from __future__ import annotations

import json
import re
from datetime import datetime

import generate_weekly_executive_summary as generator

# These entries are a reversed/administrative transaction chain and must never
# appear in franchise executive summaries or rival-watch sections.
BLACKLISTED_TRANSACTION_IDS = {
    "1384427332722233344",  # related pick-only reversal
    "1384401342625226752",  # Mayfield/Brissett plus related picks
    "1384338064138043392",  # Mayfield/Brissett reversal
}

_original_latest_trade = generator.latest_trade
_original_split_assets = generator.split_assets
_original_parse_team = generator.parse_team
_original_build_summary = generator.build_summary
ORIGINAL_ROSTER_RE = re.compile(r"\(original roster\s+(\d+)\)", re.IGNORECASE)
PICK_YEAR_RE = re.compile(r"\b(20\d{2})\b")
PICK_D_AVI_RE = re.compile(r"\bD-AVI\s+([0-9]+(?:\.[0-9]+)?)\b", re.IGNORECASE)


def roster_name_map() -> dict[int, str]:
    mapping: dict[int, str] = {}
    for path in sorted(generator.TEAMS.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        identity = generator.fields(generator.section(lines, "## Team Identity"))
        if identity.get("Roster ID") and identity.get("Team name"):
            mapping[int(identity["Roster ID"])] = identity["Team name"]
    if len(mapping) != 16:
        raise RuntimeError(f"Expected 16 verified roster-to-franchise mappings, found {len(mapping)}")
    return mapping


ROSTER_NAMES = roster_name_map()


def replace_original_roster(value: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        roster_id = int(match.group(1))
        team_name = ROSTER_NAMES.get(roster_id)
        if not team_name:
            raise RuntimeError(f"No verified franchise name found for original roster {roster_id}")
        return f"({team_name})"

    return ORIGINAL_ROSTER_RE.sub(replacement, value)


def split_assets_with_team_names(value: str | None) -> list[str]:
    return [replace_original_roster(item) for item in _original_split_assets(value)]


def latest_non_blacklisted_trade(team: dict, ledger: list[dict], now):
    filtered_ledger = [
        trade
        for trade in ledger
        if trade.get("transaction_id") not in BLACKLISTED_TRANSACTION_IDS
    ]
    return _original_latest_trade(team, filtered_ledger, now)


def future_pick_davi(draft_assets: list[str], current_year: int) -> tuple[float, list[str]]:
    """Return verified D-AVI from picks after the current season only."""
    total = 0.0
    included: list[str] = []
    for asset in draft_assets:
        year_match = PICK_YEAR_RE.search(asset)
        davi_match = PICK_D_AVI_RE.search(asset)
        if not year_match or not davi_match:
            continue
        if int(year_match.group(1)) <= current_year:
            continue
        total += float(davi_match.group(1))
        included.append(asset)
    return round(total, 2), included


def parse_team_with_future_pick_davi(path):
    team = _original_parse_team(path)
    current_year = datetime.now(generator.MOUNTAIN).year
    pick_total, included_picks = future_pick_davi(team["draft_assets"], current_year)
    player_total = round(team["dynasty_score"], 2)
    team["player_dynasty_score"] = player_total
    team["future_pick_dynasty_score"] = pick_total
    team["future_pick_dynasty_assets"] = included_picks
    team["dynasty_score"] = round(player_total + pick_total, 2)
    return team


def apply_website_dynasty_ladder(teams: list[dict]) -> list[dict]:
    """Replicate the Power Rankings webpage's canonical D-AVI ladder.

    Website method:
      * canonical franchise D-AVI = full roster D-AVI + controlled 2027+ picks
      * dynasty ladder score = 65% canonical D-AVI + 35% C-AVI
      * a team cannot improve beyond half of its C-AVI rank
    """
    championship_order = sorted(
        teams,
        key=lambda team: (team["projected_score"], team["dynasty_score"], team["team_name"]),
        reverse=True,
    )
    for index, team in enumerate(championship_order, start=1):
        team["projected_rank"] = index
        team["minimum_dynasty_rank"] = max(1, (index + 1) // 2)
        team["dynasty_ladder_score"] = round(
            team["dynasty_score"] * 0.65 + team["projected_score"] * 0.35,
            1,
        )

    pending = sorted(
        teams,
        key=lambda team: (team["dynasty_ladder_score"], team["dynasty_score"], team["team_name"]),
        reverse=True,
    )
    placed: list[dict] = []
    for rank in range(1, len(teams) + 1):
        eligible_index = next(
            (index for index, team in enumerate(pending) if team["minimum_dynasty_rank"] <= rank),
            0,
        )
        team = pending.pop(eligible_index)
        team["dynasty_rank"] = rank
        placed.append(team)
    return placed


def build_summary_with_current_dynasty(team: dict, above: dict | None, below: dict | None, ledger: list[dict], now):
    summary = _original_build_summary(team, above, below, ledger, now)
    dynasty_rank = team["dynasty_rank"]
    player_total = team["player_dynasty_score"]
    pick_total = team["future_pick_dynasty_score"]
    canonical_davi = team["dynasty_score"]
    ladder_score = team["dynasty_ladder_score"]
    cavi_total = team["projected_score"]
    rank_floor = team["minimum_dynasty_rank"]

    pick_phrase = (
        f"{player_total:.2f} roster-player D-AVI plus {pick_total:.2f} from controlled {now.year + 1}+ picks"
        if pick_total > 0
        else f"{player_total:.2f} roster-player D-AVI with no verified {now.year + 1}+ pick value"
    )
    dynasty_body = (
        f"The Power Rankings D-AVI ladder places this franchise #{dynasty_rank} of 16 at {ladder_score:.1f}. "
        f"That exact webpage score blends 65% of the {canonical_davi:.2f} canonical franchise D-AVI "
        f"({pick_phrase}) with 35% of the {cavi_total:.2f} starting-lineup C-AVI. "
        f"The C-AVI placement guardrail sets a best-possible dynasty rank of #{rank_floor}."
    )

    summary["executive_summary"] += (
        f" On the website's D-AVI ladder, the franchise ranks #{dynasty_rank} of 16 "
        f"with a {ladder_score:.1f} dynasty power score."
    )
    summary["dynasty_power"] = {
        "rank": dynasty_rank,
        "league_size": 16,
        "score": ladder_score,
        "canonical_franchise_d_avi": canonical_davi,
        "player_d_avi": player_total,
        "future_pick_d_avi": pick_total,
        "starting_lineup_c_avi": cavi_total,
        "d_avi_weight": 0.65,
        "c_avi_weight": 0.35,
        "minimum_dynasty_rank": rank_floor,
        "included_future_picks": team["future_pick_dynasty_assets"],
        "current_year_picks_excluded": True,
        "method": "Power Rankings webpage D-AVI ladder: 65% canonical franchise D-AVI plus 35% starting-lineup C-AVI, with the championship-rank placement floor",
    }

    dynasty_section = {
        "id": "dynasty-position",
        "title": "D-AVI Power Ranking",
        "body": dynasty_body,
    }
    insert_at = next(
        (index + 1 for index, section in enumerate(summary["sections"]) if section.get("id") == "projected-power"),
        1,
    )
    summary["sections"].insert(insert_at, dynasty_section)
    summary["schema_version"] = max(7, int(summary.get("schema_version", 0)))
    return summary


def aligned_main() -> None:
    now = datetime.now(generator.MOUNTAIN)
    generator.OUTPUT.mkdir(parents=True, exist_ok=True)
    team_paths = sorted(generator.TEAMS.glob("*.md"))
    if len(team_paths) != 16:
        raise RuntimeError(f"Expected 16 team files in {generator.TEAMS}, found {len(team_paths)}")

    ledger = generator.parse_historical_trades()
    teams = [generator.parse_team(path) for path in team_paths]
    ranked = sorted(
        teams,
        key=lambda team: (team["projected_score"], team["dynasty_score"], team["team_name"]),
        reverse=True,
    )
    for index, team in enumerate(ranked, start=1):
        team["projected_rank"] = index

    apply_website_dynasty_ladder(teams)

    written: list[str] = []
    for index, team in enumerate(ranked):
        above = ranked[index - 1] if index > 0 else None
        below = ranked[index + 1] if index + 1 < len(ranked) else None
        summary = generator.build_summary(team, above, below, ledger, now)
        destination = generator.OUTPUT / f"{summary['franchise_id']}.json"
        destination.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        written.append(destination.name)

    manifest = {
        "schema_version": 4,
        "generated_at": now.isoformat(),
        "refresh_schedule": "Wednesdays at 11:00 AM America/Denver",
        "source_policy": "AVI-Core/knowledge only",
        "franchise_count": len(written),
        "projected_power_method": "Verified projected-starting-lineup C-AVI total",
        "dynasty_power_method": "Power Rankings webpage D-AVI ladder: 65% canonical franchise D-AVI + 35% starting-lineup C-AVI with championship-rank placement floor",
        "files": sorted(written),
    }
    (generator.OUTPUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(written)} website-aligned franchise summaries to {generator.OUTPUT.relative_to(generator.ROOT)}")


def validate_outputs() -> None:
    summaries = sorted(generator.OUTPUT.glob("*.json"))
    franchise_files = [path for path in summaries if path.name != "manifest.json"]
    if len(franchise_files) != 16:
        raise RuntimeError(f"Expected 16 franchise summaries, found {len(franchise_files)}")

    ranks: list[int] = []
    for path in summaries:
        text = path.read_text(encoding="utf-8")
        if "original roster" in text.casefold():
            raise RuntimeError(f"Untranslated original-roster reference remains in {path}")
        payload = json.loads(text)
        if path.name == "manifest.json":
            continue
        dynasty = payload.get("dynasty_power", {})
        canonical = round(float(dynasty.get("player_d_avi", 0)) + float(dynasty.get("future_pick_d_avi", 0)), 2)
        if round(float(dynasty.get("canonical_franchise_d_avi", -1)), 2) != canonical:
            raise RuntimeError(f"Canonical franchise D-AVI does not reconcile in {path}")
        expected_ladder = round(canonical * 0.65 + float(dynasty.get("starting_lineup_c_avi", 0)) * 0.35, 1)
        if round(float(dynasty.get("score", -1)), 1) != expected_ladder:
            raise RuntimeError(f"Website D-AVI ladder score does not reconcile in {path}")
        if int(dynasty.get("rank", 99)) < int(dynasty.get("minimum_dynasty_rank", 1)):
            raise RuntimeError(f"Dynasty placement floor violated in {path}")
        ranks.append(int(dynasty["rank"]))
        for pick in dynasty.get("included_future_picks", []):
            year_match = PICK_YEAR_RE.search(pick)
            if not year_match or int(year_match.group(1)) <= datetime.now(generator.MOUNTAIN).year:
                raise RuntimeError(f"Invalid current-year pick included in dynasty score for {path}: {pick}")

    if sorted(ranks) != list(range(1, 17)):
        raise RuntimeError(f"Dynasty ranks are not a complete 1-16 ladder: {sorted(ranks)}")


generator.split_assets = split_assets_with_team_names
generator.latest_trade = latest_non_blacklisted_trade
generator.parse_team = parse_team_with_future_pick_davi
generator.build_summary = build_summary_with_current_dynasty
generator.main = aligned_main


if __name__ == "__main__":
    generator.main()
    validate_outputs()
