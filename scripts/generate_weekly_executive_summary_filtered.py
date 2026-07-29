from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
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
LEAGUE_SIZE = 16

_original_latest_trade = generator.latest_trade
_original_split_assets = generator.split_assets
_original_parse_team = generator.parse_team
_original_build_summary = generator.build_summary

ORIGINAL_ROSTER_RE = re.compile(
    r"\(original roster\s+(\d+)\)",
    re.IGNORECASE,
)


def normalize_franchise(value: Any) -> str:
    """
    Create a stable franchise lookup key.

    Examples:
        SmokyValleyWheatWarriors
        Smoky Valley Wheat Warriors
        Smoky-Valley Wheat Warriors

    All normalize to:
        smokyvalleywheatwarriors
    """
    if value is None:
        return ""

    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.casefold()

    return re.sub(r"[^a-z0-9]+", "", text)


def normalize_roster_id(value: Any) -> int | None:
    if value in (None, ""):
        return None

    try:
        roster_id = int(value)
    except (TypeError, ValueError):
        return None

    if roster_id < 1:
        return None

    return roster_id


def roster_name_map() -> dict[int, str]:
    mapping: dict[int, str] = {}

    for path in sorted(generator.TEAMS.glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        identity = generator.fields(
            generator.section(lines, "## Team Identity")
        )

        roster_id = normalize_roster_id(identity.get("Roster ID"))
        team_name = str(identity.get("Team name") or "").strip()

        if roster_id is None or not team_name:
            continue

        if roster_id in mapping:
            raise RuntimeError(
                f"Duplicate roster ID {roster_id} in team files"
            )

        mapping[roster_id] = team_name

    if len(mapping) != LEAGUE_SIZE:
        raise RuntimeError(
            "Expected "
            f"{LEAGUE_SIZE} verified roster-to-franchise mappings, "
            f"found {len(mapping)}"
        )

    return mapping


ROSTER_NAMES = roster_name_map()


def extract_api_team_name(row: dict[str, Any]) -> str:
    return str(
        row.get("franchise_name")
        or row.get("team_name")
        or row.get("team")
        or row.get("name")
        or ""
    ).strip()


def extract_api_roster_id(row: dict[str, Any]) -> int | None:
    return normalize_roster_id(
        row.get("roster_id")
        or row.get("rosterId")
        or row.get("team_id")
    )


def load_website_power_rankings() -> dict[str, dict]:
    request = Request(
        f"{POWER_RANKINGS_URL}?v={int(datetime.now().timestamp())}",
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "AVI-Core weekly summary generator",
        },
    )

    try:
        with urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except Exception as exc:
        raise RuntimeError(
            f"Unable to load website power rankings: {exc}"
        ) from exc

    dynasty = payload.get("dynasty")

    if not isinstance(dynasty, list):
        raise RuntimeError(
            "Website power-ranking endpoint did not return a dynasty list"
        )

    if len(dynasty) != LEAGUE_SIZE:
        raise RuntimeError(
            "Website power-ranking endpoint returned "
            f"{len(dynasty)} dynasty teams; expected {LEAGUE_SIZE}"
        )

    by_name: dict[str, dict] = {}
    by_roster_id: dict[int, dict] = {}
    ranks: set[int] = set()

    for row in dynasty:
        if not isinstance(row, dict):
            raise RuntimeError(
                f"Invalid website dynasty row type: {row!r}"
            )

        name = extract_api_team_name(row)
        roster_id = extract_api_roster_id(row)

        try:
            rank = int(row.get("rank") or 0)
            score = float(row.get("score"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Invalid website dynasty rank or score: {row}"
            ) from exc

        if not name:
            raise RuntimeError(
                f"Website dynasty row has no franchise name: {row}"
            )

        if rank < 1 or rank > LEAGUE_SIZE:
            raise RuntimeError(
                f"Invalid website dynasty rank: {row}"
            )

        name_key = normalize_franchise(name)

        if not name_key:
            raise RuntimeError(
                f"Could not normalize website dynasty franchise: {name!r}"
            )

        if name_key in by_name:
            raise RuntimeError(
                f"Duplicate website dynasty franchise: {name}"
            )

        normalized_row = {
            "rank": rank,
            "score": score,
            "franchise_name": name,
            "roster_id": roster_id,
        }

        by_name[name_key] = normalized_row

        if roster_id is not None:
            if roster_id in by_roster_id:
                raise RuntimeError(
                    f"Duplicate website dynasty roster ID: {roster_id}"
                )
            by_roster_id[roster_id] = normalized_row

        if rank in ranks:
            raise RuntimeError(
                f"Duplicate website dynasty rank: {rank}"
            )

        ranks.add(rank)

    expected_ranks = set(range(1, LEAGUE_SIZE + 1))

    if ranks != expected_ranks:
        raise RuntimeError(
            "Website dynasty ranks are incomplete or duplicated: "
            f"{sorted(ranks)}"
        )

    return {
        "by_name": by_name,
        "by_roster_id": by_roster_id,
    }


WEBSITE_DYNASTY = load_website_power_rankings()


def find_website_dynasty_row(team: dict[str, Any]) -> dict | None:
    """
    Prefer the immutable roster ID.

    Fall back to a compact normalized franchise name when the website API
    does not currently expose roster_id.
    """
    roster_id = normalize_roster_id(team.get("roster_id"))

    if roster_id is not None:
        website_row = WEBSITE_DYNASTY["by_roster_id"].get(roster_id)

        if website_row is not None:
            return website_row

    team_name = str(team.get("team_name") or "").strip()
    name_key = normalize_franchise(team_name)

    if name_key:
        website_row = WEBSITE_DYNASTY["by_name"].get(name_key)

        if website_row is not None:
            return website_row

    return None


def website_lookup_diagnostics(team: dict[str, Any]) -> str:
    available_names = sorted(
        row["franchise_name"]
        for row in WEBSITE_DYNASTY["by_name"].values()
    )

    available_roster_ids = sorted(
        WEBSITE_DYNASTY["by_roster_id"]
    )

    return (
        f"team_name={team.get('team_name')!r}, "
        f"normalized_name="
        f"{normalize_franchise(team.get('team_name'))!r}, "
        f"roster_id={team.get('roster_id')!r}, "
        f"available_roster_ids={available_roster_ids}, "
        f"available_franchises={available_names}"
    )


def replace_original_roster(value: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        roster_id = int(match.group(1))
        team_name = ROSTER_NAMES.get(roster_id)

        if not team_name:
            raise RuntimeError(
                "No verified franchise name found for "
                f"original roster {roster_id}"
            )

        return f"({team_name})"

    return ORIGINAL_ROSTER_RE.sub(replacement, value)


def split_assets_with_team_names(
    value: str | None,
) -> list[str]:
    return [
        replace_original_roster(item)
        for item in _original_split_assets(value)
    ]


def latest_non_blacklisted_trade(
    team: dict,
    ledger: list[dict],
    now,
):
    filtered_ledger = [
        trade
        for trade in ledger
        if str(trade.get("transaction_id") or "")
        not in BLACKLISTED_TRANSACTION_IDS
    ]

    return _original_latest_trade(
        team,
        filtered_ledger,
        now,
    )


def parse_team_with_website_dynasty(
    path: Path,
) -> dict:
    team = _original_parse_team(path)
    website = find_website_dynasty_row(team)

    if website is None:
        raise RuntimeError(
            "No website D-AVI ladder row found. "
            + website_lookup_diagnostics(team)
        )

    team["website_dynasty_rank"] = int(website["rank"])
    team["website_dynasty_score"] = float(website["score"])
    team["website_dynasty_name"] = website["franchise_name"]

    return team


def build_summary_with_website_dynasty(
    team: dict,
    above: dict | None,
    below: dict | None,
    ledger: list[dict],
    now,
):
    summary = _original_build_summary(
        team,
        above,
        below,
        ledger,
        now,
    )

    dynasty_rank = int(team["website_dynasty_rank"])
    dynasty_score = float(team["website_dynasty_score"])

    executive_summary = str(
        summary.get("executive_summary") or ""
    )

    # Remove a previous dynasty-ranking sentence before inserting the
    # authoritative live website result.
    executive_summary = re.sub(
        r"\s+The updated dynasty profile ranks "
        r"#[^.]+(?:\.)?",
        "",
        executive_summary,
        flags=re.IGNORECASE,
    ).rstrip()

    summary["executive_summary"] = (
        executive_summary
        + (
            " On the Power Rankings webpage's D-AVI ladder, "
            f"the franchise ranks #{dynasty_rank} of "
            f"{LEAGUE_SIZE} with a "
            f"{dynasty_score:.1f} team D-AVI score."
        )
    ).strip()

    summary["dynasty_power"] = {
        "rank": dynasty_rank,
        "league_size": LEAGUE_SIZE,
        "score": dynasty_score,
        "method": (
            "Exact rank and team D-AVI score from the live "
            "Autobots HQ Power Rankings webpage ladder"
        ),
        "source_url": POWER_RANKINGS_URL,
    }

    dynasty_section = {
        "id": "dynasty-position",
        "title": "D-AVI Power Ranking",
        "body": (
            "The live Power Rankings webpage places "
            f"{team['team_name']} #{dynasty_rank} of "
            f"{LEAGUE_SIZE} on the D-AVI ladder at "
            f"{dynasty_score:.1f}. This section uses the "
            "webpage's exact team score and ordering rather "
            "than recalculating dynasty rank from the "
            "weekly-summary team files."
        ),
    }

    sections = list(summary.get("sections") or [])

    sections = [
        section
        for section in sections
        if section.get("id") != "dynasty-position"
    ]

    insert_at = next(
        (
            index + 1
            for index, section in enumerate(sections)
            if section.get("id") == "projected-power"
        ),
        min(1, len(sections)),
    )

    sections.insert(insert_at, dynasty_section)
    summary["sections"] = sections

    summary["schema_version"] = max(
        8,
        int(summary.get("schema_version") or 0),
    )

    source = summary.setdefault("source", {})
    source["external_sources_used"] = True

    source_files = source.setdefault("files", [])

    if "Autobots HQ live Power Rankings API" not in source_files:
        source_files.append(
            "Autobots HQ live Power Rankings API"
        )

    return summary


def validate_website_team_coverage() -> None:
    missing: list[str] = []

    for path in sorted(generator.TEAMS.glob("*.md")):
        team = _original_parse_team(path)

        if find_website_dynasty_row(team) is None:
            missing.append(
                website_lookup_diagnostics(team)
            )

    if missing:
        raise RuntimeError(
            "Website D-AVI ladder could not be matched to "
            "all franchise files:\n- "
            + "\n- ".join(missing)
        )


def validate_outputs() -> None:
    summaries = sorted(generator.OUTPUT.glob("*.json"))

    franchise_files = [
        path
        for path in summaries
        if path.name != "manifest.json"
    ]

    if len(franchise_files) != LEAGUE_SIZE:
        raise RuntimeError(
            f"Expected {LEAGUE_SIZE} franchise summaries, "
            f"found {len(franchise_files)}"
        )

    observed_ranks: set[int] = set()

    for path in franchise_files:
        text = path.read_text(encoding="utf-8")

        if "original roster" in text.casefold():
            raise RuntimeError(
                "Untranslated original-roster reference "
                f"remains in {path}"
            )

        payload = json.loads(text)

        dynasty = payload.get("dynasty_power", {})

        try:
            rank = int(dynasty.get("rank") or 0)
            score = float(dynasty.get("score"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                f"Invalid dynasty_power block in {path}"
            ) from exc

        expected = find_website_dynasty_row(
            {
                "team_name": payload.get("franchise_name"),
                "roster_id": payload.get("roster_id"),
            }
        )

        if expected is None:
            raise RuntimeError(
                "Missing website dynasty row for "
                f"{path.name}: "
                f"franchise_name="
                f"{payload.get('franchise_name')!r}, "
                f"roster_id={payload.get('roster_id')!r}"
            )

        if (
            rank != int(expected["rank"])
            or round(score, 4)
            != round(float(expected["score"]), 4)
        ):
            raise RuntimeError(
                f"Website dynasty mismatch in {path.name}: "
                f"generated rank={rank}, score={score}; "
                f"expected rank={expected['rank']}, "
                f"score={expected['score']}"
            )

        if rank in observed_ranks:
            raise RuntimeError(
                f"Duplicate generated dynasty rank: {rank}"
            )

        observed_ranks.add(rank)

    expected_ranks = set(range(1, LEAGUE_SIZE + 1))

    if observed_ranks != expected_ranks:
        raise RuntimeError(
            "Generated dynasty ladder is incomplete: "
            f"{sorted(observed_ranks)}"
        )


generator.split_assets = split_assets_with_team_names
generator.latest_trade = latest_non_blacklisted_trade
generator.parse_team = parse_team_with_website_dynasty
generator.build_summary = build_summary_with_website_dynasty


if __name__ == "__main__":
    validate_website_team_coverage()
    generator.main()
    validate_outputs()
