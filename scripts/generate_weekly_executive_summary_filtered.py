from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.request import Request, urlopen

import generate_weekly_executive_summary as generator

# These entries are a reversed/administrative transaction chain and must never
# appear in franchise executive summaries or rival-watch sections.
BLACKLISTED_TRANSACTION_IDS = {
    "1384427332722233344",  # related pick-only reversal
    "1384401342625226752",  # Mayfield/Brissett plus related picks
    "1384338064138043392",  # Mayfield/Brissett reversal
}

POWER_RANKINGS_URL = "https://autobots.football/api/power-rankings"

_original_latest_trade = generator.latest_trade
_original_split_assets = generator.split_assets
_original_parse_team = generator.parse_team
_original_build_summary = generator.build_summary
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


def normalize_franchise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold().replace("’", "").replace("'", "")).strip()


def load_website_power_rankings() -> dict[str, dict]:
    request = Request(
        f"{POWER_RANKINGS_URL}?v={int(datetime.now().timestamp())}",
        headers={"Cache-Control": "no-cache", "User-Agent": "AVI-Core weekly summary generator"},
    )
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)

    dynasty = payload.get("dynasty")
    if not isinstance(dynasty, list) or len(dynasty) != 16:
        raise RuntimeError("Website power-ranking endpoint did not return all 16 dynasty teams")

    mapped: dict[str, dict] = {}
    ranks: set[int] = set()
    for row in dynasty:
        name = str(row.get("franchise_name") or "").strip()
        rank = int(row.get("rank") or 0)
        score = float(row.get("score") or 0)
        if not name or rank < 1 or rank > 16:
            raise RuntimeError(f"Invalid website dynasty row: {row}")
        key = normalize_franchise(name)
        if key in mapped:
            raise RuntimeError(f"Duplicate website dynasty franchise: {name}")
        mapped[key] = {"rank": rank, "score": score, "franchise_name": name}
        ranks.add(rank)

    if ranks != set(range(1, 17)):
        raise RuntimeError(f"Website dynasty ranks are incomplete or duplicated: {sorted(ranks)}")
    return mapped


WEBSITE_DYNASTY = load_website_power_rankings()


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


def parse_team_with_website_dynasty(path):
    team = _original_parse_team(path)
    website = WEBSITE_DYNASTY.get(normalize_franchise(team["team_name"]))
    if not website:
        raise RuntimeError(f"No website D-AVI ladder row found for {team['team_name']}")

    team["website_dynasty_rank"] = website["rank"]
    team["website_dynasty_score"] = website["score"]
    return team


def build_summary_with_website_dynasty(team: dict, above: dict | None, below: dict | None, ledger: list[dict], now):
    summary = _original_build_summary(team, above, below, ledger, now)
    dynasty_rank = int(team["website_dynasty_rank"])
    dynasty_score = float(team["website_dynasty_score"])

    # Remove any previous generator-added dynasty sentence before appending the
    # authoritative Power Rankings webpage result.
    summary["executive_summary"] = re.sub(
        r"\s+The updated dynasty profile ranks #[^.]+\.",
        "",
        summary["executive_summary"],
    ).rstrip()
    summary["executive_summary"] += (
        f" On the Power Rankings webpage's D-AVI ladder, the franchise ranks "
        f"#{dynasty_rank} of 16 with a {dynasty_score:.1f} team D-AVI score."
    )

    summary["dynasty_power"] = {
        "rank": dynasty_rank,
        "league_size": 16,
        "score": dynasty_score,
        "method": "Exact rank and team D-AVI score from the live Autobots HQ Power Rankings webpage ladder",
        "source_url": POWER_RANKINGS_URL,
    }

    dynasty_section = {
        "id": "dynasty-position",
        "title": "D-AVI Power Ranking",
        "body": (
            f"The live Power Rankings webpage places {team['team_name']} "
            f"#{dynasty_rank} of 16 on the D-AVI ladder at {dynasty_score:.1f}. "
            "This section uses the webpage's exact team score and ordering rather than "
            "recalculating dynasty rank from the weekly-summary team files."
        ),
    }

    summary["sections"] = [
        section for section in summary["sections"] if section.get("id") != "dynasty-position"
    ]
    insert_at = next(
        (index + 1 for index, section in enumerate(summary["sections"]) if section.get("id") == "projected-power"),
        1,
    )
    summary["sections"].insert(insert_at, dynasty_section)
    summary["schema_version"] = max(8, int(summary.get("schema_version", 0)))
    summary["source"]["external_sources_used"] = False
    summary["source"]["files"].append("Autobots HQ live Power Rankings API")
    return summary


def validate_outputs() -> None:
    summaries = sorted(generator.OUTPUT.glob("*.json"))
    franchise_files = [path for path in summaries if path.name != "manifest.json"]
    if len(franchise_files) != 16:
        raise RuntimeError(f"Expected 16 franchise summaries, found {len(franchise_files)}")

    observed_ranks: set[int] = set()
    for path in summaries:
        text = path.read_text(encoding="utf-8")
        if "original roster" in text.casefold():
            raise RuntimeError(f"Untranslated original-roster reference remains in {path}")
        payload = json.loads(text)
        if path.name == "manifest.json":
            continue
        dynasty = payload.get("dynasty_power", {})
        rank = int(dynasty.get("rank") or 0)
        score = float(dynasty.get("score") or 0)
        expected = WEBSITE_DYNASTY.get(normalize_franchise(payload["franchise_name"]))
        if not expected:
            raise RuntimeError(f"Missing website dynasty row for {path}")
        if rank != expected["rank"] or round(score, 4) != round(expected["score"], 4):
            raise RuntimeError(f"Website dynasty mismatch in {path}")
        observed_ranks.add(rank)

    if observed_ranks != set(range(1, 17)):
        raise RuntimeError(f"Generated dynasty ladder is incomplete: {sorted(observed_ranks)}")


generator.split_assets = split_assets_with_team_names
generator.latest_trade = latest_non_blacklisted_trade
generator.parse_team = parse_team_with_website_dynasty
generator.build_summary = build_summary_with_website_dynasty


if __name__ == "__main__":
    generator.main()
    validate_outputs()
