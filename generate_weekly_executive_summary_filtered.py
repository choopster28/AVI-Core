from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

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

TRANSACTION_FILE_RE = re.compile(
    r"(?:transaction|waiver|activity|move)",
    re.IGNORECASE,
)

COMPLETED_STATUSES = {
    "complete",
    "completed",
    "successful",
    "success",
}


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
_original_rival_snapshot = generator.rival_snapshot


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


def iter_json_records(value: Any) -> Iterable[dict[str, Any]]:
    """Yield nested dictionaries that look like Sleeper transactions."""
    if isinstance(value, list):
        for item in value:
            yield from iter_json_records(item)
        return

    if not isinstance(value, dict):
        return

    record_type = str(value.get("type") or "").casefold()
    has_identity = "transaction_id" in value or "id" in value
    has_created = "created" in value or "created_at" in value
    has_roster_data = any(
        key in value
        for key in ("roster_ids", "adds", "drops", "draft_picks")
    )

    if has_identity and has_created and (record_type or has_roster_data):
        yield value

    for child in value.values():
        if isinstance(child, (dict, list)):
            yield from iter_json_records(child)


def candidate_transaction_files() -> list[Path]:
    roots = [ROOT / "data", ROOT / "knowledge"]
    files: list[Path] = []

    for search_root in roots:
        if not search_root.is_dir():
            continue
        for path in search_root.rglob("*.json"):
            if VERIFIED_OUTPUT_DIR in path.parents:
                continue
            if TRANSACTION_FILE_RE.search(path.name):
                files.append(path)

    return sorted(set(files))


def load_verified_transactions() -> list[dict[str, Any]]:
    """
    Load completed Sleeper activity from checked-in transaction JSON files.

    This intentionally does not call the network. The weekly brief remains
    reproducible and uses only files committed to AVI-Core.
    """
    by_id: dict[str, dict[str, Any]] = {}

    for path in candidate_transaction_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue

        for record in iter_json_records(payload):
            transaction_id = str(
                record.get("transaction_id") or record.get("id") or ""
            )
            if not transaction_id or transaction_id in BLACKLISTED_TRANSACTION_IDS:
                continue

            status = str(record.get("status") or "complete").casefold()
            if status and status not in COMPLETED_STATUSES:
                continue

            normalized = dict(record)
            normalized["_source_file"] = str(path.relative_to(ROOT))
            by_id[transaction_id] = normalized

    return sorted(
        by_id.values(),
        key=transaction_created_ms,
        reverse=True,
    )


def transaction_created_ms(record: dict[str, Any]) -> int:
    raw = record.get("created") or record.get("created_at") or 0

    if isinstance(raw, (int, float)):
        value = int(raw)
        return value * 1000 if 0 < value < 10_000_000_000 else value

    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped.isdigit():
            value = int(stripped)
            return value * 1000 if value < 10_000_000_000 else value
        try:
            return int(datetime.fromisoformat(stripped.replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return 0

    return 0


def transaction_roster_ids(record: dict[str, Any]) -> set[int]:
    roster_ids: set[int] = set()

    def add(value: Any) -> None:
        try:
            roster_ids.add(int(value))
        except (TypeError, ValueError):
            pass

    for value in record.get("roster_ids") or []:
        add(value)

    for field in ("adds", "drops"):
        mapping = record.get(field)
        if isinstance(mapping, dict):
            for value in mapping.values():
                add(value)

    for pick in record.get("draft_picks") or []:
        if not isinstance(pick, dict):
            continue
        add(pick.get("owner_id"))
        add(pick.get("previous_owner_id"))
        add(pick.get("roster_id"))

    return roster_ids


def player_name_map() -> dict[str, str]:
    """Resolve Sleeper player IDs without requiring a specific export path."""
    names: dict[str, str] = {}
    likely_files: list[Path] = []

    for search_root in (ROOT / "data", ROOT / "knowledge"):
        if not search_root.is_dir():
            continue
        for path in search_root.rglob("*.json"):
            lowered = path.name.casefold()
            if "player" in lowered and "transaction" not in lowered:
                likely_files.append(path)

    for path in sorted(set(likely_files)):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue

        containers: list[Any]
        if isinstance(payload, dict) and isinstance(payload.get("players"), (dict, list)):
            containers = [payload["players"]]
        else:
            containers = [payload]

        for container in containers:
            if isinstance(container, dict):
                items = container.items()
            elif isinstance(container, list):
                items = ((None, item) for item in container)
            else:
                continue

            for fallback_id, item in items:
                if not isinstance(item, dict):
                    continue
                player_id = item.get("player_id") or item.get("id") or fallback_id
                name = item.get("full_name") or item.get("name")
                if player_id is not None and isinstance(name, str) and name.strip():
                    names[str(player_id)] = name.strip()

    return names


VERIFIED_TRANSACTIONS = load_verified_transactions()
PLAYER_NAMES = player_name_map()


def asset_names(mapping: Any, roster_id: int) -> list[str]:
    if not isinstance(mapping, dict):
        return []

    names: list[str] = []
    for player_id, assigned_roster in mapping.items():
        try:
            matches = int(assigned_roster) == roster_id
        except (TypeError, ValueError):
            matches = False
        if matches:
            names.append(PLAYER_NAMES.get(str(player_id), f"player {player_id}"))
    return names


def format_activity_date(created_ms: int) -> str:
    if created_ms <= 0:
        return "Date unavailable"
    created = datetime.fromtimestamp(created_ms / 1000, tz=generator.UTC)
    return created.astimezone(generator.MOUNTAIN).strftime("%B %-d")


def summarize_transaction(record: dict[str, Any], team: dict[str, Any]) -> str:
    roster_id = int(team["roster_id"])
    transaction_type = str(record.get("type") or "transaction").casefold()
    date_label = format_activity_date(transaction_created_ms(record))
    added = asset_names(record.get("adds"), roster_id)
    dropped = asset_names(record.get("drops"), roster_id)

    if transaction_type == "trade":
        other_ids = sorted(transaction_roster_ids(record) - {roster_id})
        counterparties = [ROSTER_NAMES.get(value, f"roster {value}") for value in other_ids]
        opening = f"On {date_label}, {team['team_name']} completed a trade"
        if counterparties:
            opening += f" with {', '.join(counterparties)}"
        details: list[str] = []
        if added:
            details.append(f"acquired {', '.join(added)}")
        if dropped:
            details.append(f"sent {', '.join(dropped)}")
        return opening + (f" and {' while '.join(details)}." if details else ".")

    if transaction_type == "waiver":
        opening = f"On {date_label}, {team['team_name']} completed a waiver claim"
    elif transaction_type in {"free_agent", "free agent"}:
        opening = f"On {date_label}, {team['team_name']} completed a free-agent move"
    else:
        opening = f"On {date_label}, {team['team_name']} completed a roster transaction"

    details = []
    if added:
        details.append(f"added {', '.join(added)}")
    if dropped:
        details.append(f"dropped {', '.join(dropped)}")
    return opening + (f" and {' while '.join(details)}." if details else ".")


def latest_verified_activity(
    team: dict[str, Any],
    ledger: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any] | None:
    cutoff_ms = int((now - timedelta(days=365)).timestamp() * 1000)
    roster_id = int(team["roster_id"])

    sleeper_record = next(
        (
            record
            for record in VERIFIED_TRANSACTIONS
            if transaction_created_ms(record) >= cutoff_ms
            and roster_id in transaction_roster_ids(record)
        ),
        None,
    )

    trade = latest_non_blacklisted_trade(team, ledger, now)
    trade_ms = 0
    if trade and trade.get("created_at"):
        try:
            trade_ms = int(
                datetime.fromisoformat(str(trade["created_at"])).timestamp() * 1000
            )
        except ValueError:
            trade_ms = 0

    sleeper_ms = transaction_created_ms(sleeper_record) if sleeper_record else 0

    if sleeper_record and sleeper_ms >= trade_ms:
        return {
            "transaction_id": str(
                sleeper_record.get("transaction_id")
                or sleeper_record.get("id")
            ),
            "created_at": datetime.fromtimestamp(
                sleeper_ms / 1000,
                tz=generator.UTC,
            ).isoformat(),
            "type": str(sleeper_record.get("type") or "transaction"),
            "summary": summarize_transaction(sleeper_record, team),
            "source_file": sleeper_record.get("_source_file"),
        }

    if trade:
        return {**trade, "type": "trade"}

    return None


def rival_snapshot_with_latest_activity(
    team: dict[str, Any] | None,
    ledger: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any] | None:
    if not team:
        return None

    activity = latest_verified_activity(team, ledger, now)
    return {
        "franchise_name": team["team_name"],
        "projected_rank": team["projected_rank"],
        "projected_score": team["projected_score"],
        # Retain latest_trade for compatibility with the existing generator and
        # website while also exposing the more accurate latest_activity field.
        "latest_trade": activity if activity and activity.get("type") == "trade" else None,
        "latest_activity": activity,
        "summary": (
            activity["summary"]
            if activity
            else f"No completed transaction for {team['team_name']} was found in the last 365 days of the authoritative AVI-Core activity files."
        ),
    }


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
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Generated file is not valid JSON: {path}"
            ) from exc

        if path.name != "manifest.json":
            rival = payload.get("rival_below")
            if rival is not None:
                if not rival.get("franchise_name"):
                    raise RuntimeError(
                        f"Rival Watch is missing a franchise name in {path}"
                    )
                if "latest_activity" not in rival:
                    raise RuntimeError(
                        f"Rival Watch is missing latest_activity in {path}"
                    )

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
generator.rival_snapshot = rival_snapshot_with_latest_activity


def main() -> None:
    print(f"Using team profiles from: {VERIFIED_TEAMS_DIR}")
    print(f"Writing franchise summaries to: {VERIFIED_OUTPUT_DIR}")
    print(f"Verified roster mappings: {len(ROSTER_NAMES)}")
    print(f"Verified completed transactions loaded: {len(VERIFIED_TRANSACTIONS)}")

    generator.main()
    validate_outputs()


if __name__ == "__main__":
    main()
