from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import generate_weekly_executive_summary as generator


ROOT = Path(__file__).resolve().parent
VERIFIED_TEAMS_DIR = ROOT / "knowledge" / "teams"
VERIFIED_OUTPUT_DIR = ROOT / "knowledge" / "franchise_summaries"

EXPECTED_FRANCHISE_COUNT = 16

# These entries are a reversed or administrative transaction chain and must
# never appear in franchise executive summaries or rival-watch sections.
BLACKLISTED_TRANSACTION_IDS = {
    "1384427332722233344",  # related pick-only reversal
    "1384401342625226752",  # Mayfield/Brissett plus related picks
    "1384338064138043392",  # Mayfield/Brissett reversal
}

ORIGINAL_ROSTER_RE = re.compile(
    r"\(original roster\s+(\d+)\)",
    re.IGNORECASE,
)


def require_directory(path: Path, description: str) -> None:
    if not path.is_dir():
        raise RuntimeError(
            f"{description} does not exist or is not a directory: {path}"
        )


def configure_generator_paths() -> None:
    require_directory(
        VERIFIED_TEAMS_DIR,
        "Verified team profile directory",
    )

    generator.TEAMS = VERIFIED_TEAMS_DIR
    generator.OUTPUT = VERIFIED_OUTPUT_DIR


configure_generator_paths()

_original_latest_trade = generator.latest_trade
_original_split_assets = generator.split_assets


def roster_name_map() -> dict[int, str]:
    mapping: dict[int, str] = {}
    team_files = sorted(VERIFIED_TEAMS_DIR.glob("*.md"))

    if not team_files:
        raise RuntimeError(
            f"No Markdown team profile files were found in {VERIFIED_TEAMS_DIR}"
        )

    for path in team_files:
        lines = path.read_text(encoding="utf-8").splitlines()

        identity = generator.fields(
            generator.section(lines, "## Team Identity")
        )

        roster_id_value = identity.get("Roster ID")
        team_name = identity.get("Team name")

        if not roster_id_value or not team_name:
            continue

        try:
            roster_id = int(roster_id_value)
        except ValueError as exc:
            raise RuntimeError(
                f"Invalid Roster ID {roster_id_value!r} in {path}"
            ) from exc

        if roster_id in mapping:
            raise RuntimeError(
                f"Duplicate Roster ID {roster_id} found in {path}"
            )

        mapping[roster_id] = team_name

    if len(mapping) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_FRANCHISE_COUNT} verified "
            f"roster-to-franchise mappings, found {len(mapping)} "
            f"from {len(team_files)} team profile files in "
            f"{VERIFIED_TEAMS_DIR}"
        )

    return mapping


ROSTER_NAMES = roster_name_map()


def replace_original_roster(value: str) -> str:
    def replacement(match: re.Match[str]) -> str:
        roster_id = int(match.group(1))
        team_name = ROSTER_NAMES.get(roster_id)

        if not team_name:
            raise RuntimeError(
                f"No verified franchise name found for original roster "
                f"{roster_id}"
            )

        return f"({team_name})"

    return ORIGINAL_ROSTER_RE.sub(replacement, value)


def split_assets_with_team_names(value: str | None) -> list[str]:
    assets = _original_split_assets(value)
    return [replace_original_roster(item) for item in assets]


def latest_non_blacklisted_trade(
    team: dict[str, Any],
    ledger: list[dict[str, Any]],
    now: Any,
) -> Any:
    filtered_ledger = [
        trade
        for trade in ledger
        if str(trade.get("transaction_id"))
        not in BLACKLISTED_TRANSACTION_IDS
    ]

    return _original_latest_trade(
        team,
        filtered_ledger,
        now,
    )


def validate_outputs() -> None:
    require_directory(
        VERIFIED_OUTPUT_DIR,
        "Franchise summary output directory",
    )

    summaries = sorted(VERIFIED_OUTPUT_DIR.glob("*.json"))
    franchise_files = [
        path
        for path in summaries
        if path.name != "manifest.json"
    ]
    manifest_path = VERIFIED_OUTPUT_DIR / "manifest.json"

    if len(franchise_files) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_FRANCHISE_COUNT} franchise summaries, "
            f"found {len(franchise_files)} in {VERIFIED_OUTPUT_DIR}"
        )

    if not manifest_path.is_file():
        raise RuntimeError(
            f"Manifest file was not generated: {manifest_path}"
        )

    for path in [*franchise_files, manifest_path]:
        text = path.read_text(encoding="utf-8")

        if "original roster" in text.casefold():
            raise RuntimeError(
                f"Untranslated original-roster reference remains in {path}"
            )

        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Generated file is not valid JSON: {path}"
            ) from exc

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    franchise_count = manifest.get("franchise_count")
    manifest_files = manifest.get("files")

    if franchise_count != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Manifest franchise_count is {franchise_count!r}; "
            f"expected {EXPECTED_FRANCHISE_COUNT}"
        )

    if not isinstance(manifest_files, list):
        raise RuntimeError(
            "Manifest field 'files' is missing or is not a list"
        )

    if len(manifest_files) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Manifest declares {len(manifest_files)} files; "
            f"expected {EXPECTED_FRANCHISE_COUNT}"
        )

    print(
        f"Validated {EXPECTED_FRANCHISE_COUNT} franchise summaries "
        f"and manifest in {VERIFIED_OUTPUT_DIR}"
    )


generator.split_assets = split_assets_with_team_names
generator.latest_trade = latest_non_blacklisted_trade


def main() -> None:
    print(f"Using team profiles from: {VERIFIED_TEAMS_DIR}")
    print(f"Writing franchise summaries to: {VERIFIED_OUTPUT_DIR}")
    print(f"Verified roster mappings: {len(ROSTER_NAMES)}")

    generator.main()
    validate_outputs()


if __name__ == "__main__":
    main()
