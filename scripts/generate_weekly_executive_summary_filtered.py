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
    """Return verified D-AVI from picks after the current season only.

    The team-level D-AVI model intentionally excludes current-year picks because
    those assets are already represented by drafted/current player values. This
    prevents double counting while allowing 2027+ firsts and seconds (and the
    small value already assigned to later rounds) to affect dynasty standing.
    """
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


def build_summary_with_current_dynasty(team: dict, above: dict | None, below: dict | None, ledger: list[dict], now):
    summary = _original_build_summary(team, above, below, ledger, now)
    dynasty_rank = team["dynasty_rank"]
    player_total = team["player_dynasty_score"]
    pick_total = team["future_pick_dynasty_score"]
    combined = team["dynasty_score"]

    if pick_total > 0:
        dynasty_body = (
            f"Dynasty rank #{dynasty_rank} of 16 with {combined:.2f} verified D-AVI: "
            f"{player_total:.2f} from rostered players plus {pick_total:.2f} from controlled "
            f"{now.year + 1}+ draft picks. Current-year picks are excluded to prevent double counting."
        )
    else:
        dynasty_body = (
            f"Dynasty rank #{dynasty_rank} of 16 with {combined:.2f} verified roster D-AVI. "
            f"No controlled {now.year + 1}+ pick D-AVI was found, so the dynasty position receives "
            "no future-draft-capital boost."
        )

    summary["executive_summary"] += f" The updated dynasty profile ranks #{dynasty_rank} of 16 at {combined:.2f} total D-AVI."
    summary["dynasty_power"] = {
        "rank": dynasty_rank,
        "league_size": 16,
        "score": combined,
        "player_d_avi": player_total,
        "future_pick_d_avi": pick_total,
        "included_future_picks": team["future_pick_dynasty_assets"],
        "current_year_picks_excluded": True,
        "method": f"Verified rostered-player D-AVI plus controlled {now.year + 1}+ draft-pick D-AVI; current-year picks excluded",
    }

    dynasty_section = {
        "id": "dynasty-position",
        "title": "Dynasty Position",
        "body": dynasty_body,
    }
    insert_at = next(
        (index + 1 for index, section in enumerate(summary["sections"]) if section.get("id") == "projected-power"),
        1,
    )
    summary["sections"].insert(insert_at, dynasty_section)
    summary["schema_version"] = max(6, int(summary.get("schema_version", 0)))
    return summary


def validate_outputs() -> None:
    summaries = sorted(generator.OUTPUT.glob("*.json"))
    franchise_files = [path for path in summaries if path.name != "manifest.json"]
    if len(franchise_files) != 16:
        raise RuntimeError(f"Expected 16 franchise summaries, found {len(franchise_files)}")

    for path in summaries:
        text = path.read_text(encoding="utf-8")
        if "original roster" in text.casefold():
            raise RuntimeError(f"Untranslated original-roster reference remains in {path}")
        payload = json.loads(text)
        if path.name == "manifest.json":
            continue
        dynasty = payload.get("dynasty_power", {})
        expected = round(float(dynasty.get("player_d_avi", 0)) + float(dynasty.get("future_pick_d_avi", 0)), 2)
        if round(float(dynasty.get("score", -1)), 2) != expected:
            raise RuntimeError(f"Dynasty score does not reconcile in {path}")
        for pick in dynasty.get("included_future_picks", []):
            year_match = PICK_YEAR_RE.search(pick)
            if not year_match or int(year_match.group(1)) <= datetime.now(generator.MOUNTAIN).year:
                raise RuntimeError(f"Invalid current-year pick included in dynasty score for {path}: {pick}")


generator.split_assets = split_assets_with_team_names
generator.latest_trade = latest_non_blacklisted_trade
generator.parse_team = parse_team_with_future_pick_davi
generator.build_summary = build_summary_with_current_dynasty


if __name__ == "__main__":
    generator.main()
    validate_outputs()
