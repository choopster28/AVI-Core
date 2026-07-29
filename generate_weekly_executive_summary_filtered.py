from __future__ import annotations

import json
import re
from pathlib import Path

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
ORIGINAL_ROSTER_RE = re.compile(r"\(original roster\s+(\d+)\)", re.IGNORECASE)


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


def validate_outputs() -> None:
    summaries = sorted(generator.OUTPUT.glob("*.json"))
    franchise_files = [path for path in summaries if path.name != "manifest.json"]
    if len(franchise_files) != 16:
        raise RuntimeError(f"Expected 16 franchise summaries, found {len(franchise_files)}")

    for path in summaries:
        text = path.read_text(encoding="utf-8")
        if "original roster" in text.casefold():
            raise RuntimeError(f"Untranslated original-roster reference remains in {path}")
        json.loads(text)


generator.split_assets = split_assets_with_team_names
generator.latest_trade = latest_non_blacklisted_trade


if __name__ == "__main__":
    generator.main()
    validate_outputs()
