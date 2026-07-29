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
CURRENT_SEASON = 2026

# These entries are a reversed or administrative transaction chain and must
# never appear in franchise executive summaries or rival-watch sections.
BLACKLISTED_TRANSACTION_IDS = {
    "1384427332722233344",
    "1384401342625226752",
    "1384338064138043392",
}

ORIGINAL_ROSTER_RE = re.compile(
    r"\(original roster\s+(\d+)\)",
    re.IGNORECASE,
)

DRAFT_ASSET_RE = re.compile(
    r"\b(20\d{2})\b.*?\bD-AVI\s+([0-9]+(?:\.[0-9]+)?)",
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

NO_PICK_RECOMMENDATION_RE = re.compile(
    r"no owned pick card|no verified.*pick|"
    r"no franchise-owned pick card|"
    r"avoid assuming unavailable draft leverage",
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
_original_parse_team = generator.parse_team
_original_gap_actions = generator.gap_actions
_original_build_summary = generator.build_summary


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
ROSTER_IDS_BY_NAME = {
    team_name.casefold(): roster_id
    for roster_id, team_name in ROSTER_NAMES.items()
}


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
    return [
        replace_original_roster(item)
        for item in _original_split_assets(value)
    ]


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
    return _original_latest_trade(team, filtered_ledger, now)


def parse_future_pick_d_avi(draft_assets: list[str]) -> float:
    total = 0.0
    for asset in draft_assets:
        match = DRAFT_ASSET_RE.search(asset)
        if not match:
            continue
        season = int(match.group(1))
        if season <= CURRENT_SEASON:
            continue
        total += float(match.group(2))
    return round(total, 2)


def parse_team_with_canonical_dynasty(path: Path) -> dict[str, Any]:
    team = _original_parse_team(path)
    player_d_avi = round(float(team.get("dynasty_score") or 0.0), 2)
    future_pick_d_avi = parse_future_pick_d_avi(
        list(team.get("draft_assets") or [])
    )
    team["player_d_avi"] = player_d_avi
    team["future_pick_d_avi"] = future_pick_d_avi
    team["dynasty_score"] = round(player_d_avi + future_pick_d_avi, 2)
    return team


def gap_actions_without_unverified_pick_language(
    team: dict[str, Any],
    above: dict[str, Any] | None,
) -> list[str]:
    return [
        action
        for action in _original_gap_actions(team, above)
        if not NO_PICK_RECOMMENDATION_RE.search(action)
    ]


def iter_json_records(value: Any) -> Iterable[dict[str, Any]]:
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
    files: list[Path] = []
    for search_root in (ROOT / "data", ROOT / "knowledge"):
        if not search_root.is_dir():
            continue
        for path in search_root.rglob("*.json"):
            if VERIFIED_OUTPUT_DIR in path.parents:
                continue
            if TRANSACTION_FILE_RE.search(path.name):
                files.append(path)
    return sorted(set(files))


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
            parsed = datetime.fromisoformat(
                stripped.replace("Z", "+00:00")
            )
            return int(parsed.timestamp() * 1000)
        except ValueError:
            return 0

    return 0


def load_verified_transactions() -> list[dict[str, Any]]:
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
            if (
                not transaction_id
                or transaction_id in BLACKLISTED_TRANSACTION_IDS
            ):
                continue

            status = str(record.get("status") or "complete").casefold()
            if status and status not in COMPLETED_STATUSES:
                continue

            normalized = dict(record)
            normalized["_source_file"] = str(path.relative_to(ROOT))
            existing = by_id.get(transaction_id)
            if (
                existing is None
                or transaction_created_ms(normalized)
                >= transaction_created_ms(existing)
            ):
                by_id[transaction_id] = normalized

    return sorted(
        by_id.values(),
        key=transaction_created_ms,
        reverse=True,
    )


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
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("players"), (dict, list))
        ):
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
                player_id = (
                    item.get("player_id")
                    or item.get("id")
                    or fallback_id
                )
                name = item.get("full_name") or item.get("name")
                if (
                    player_id is not None
                    and isinstance(name, str)
                    and name.strip()
                ):
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
            names.append(
                PLAYER_NAMES.get(str(player_id), f"player {player_id}")
            )
    return names


def pick_label(pick: dict[str, Any]) -> str:
    season = pick.get("season") or pick.get("year") or "Future"
    round_value = pick.get("round") or "?"
    original_roster = pick.get("roster_id")
    original_name = None
    try:
        original_name = ROSTER_NAMES.get(int(original_roster))
    except (TypeError, ValueError):
        pass

    label = f"{season} Round {round_value}"
    if original_name:
        label += f" ({original_name})"
    return label


def transaction_pick_moves(
    record: dict[str, Any],
    roster_id: int,
) -> tuple[list[str], list[str]]:
    received: list[str] = []
    sent: list[str] = []

    for pick in record.get("draft_picks") or []:
        if not isinstance(pick, dict):
            continue
        try:
            owner_id = int(pick.get("owner_id"))
        except (TypeError, ValueError):
            owner_id = -1
        try:
            previous_owner_id = int(pick.get("previous_owner_id"))
        except (TypeError, ValueError):
            previous_owner_id = -1

        label = pick_label(pick)
        if owner_id == roster_id and previous_owner_id != roster_id:
            received.append(label)
        if previous_owner_id == roster_id and owner_id != roster_id:
            sent.append(label)

    return received, sent


def format_activity_date(created_ms: int) -> str:
    if created_ms <= 0:
        return "Date unavailable"
    created = datetime.fromtimestamp(
        created_ms / 1000,
        tz=generator.UTC,
    )
    return created.astimezone(generator.MOUNTAIN).strftime("%B %-d")


def summarize_transaction(
    record: dict[str, Any],
    team: dict[str, Any],
) -> str:
    roster_id = int(team["roster_id"])
    transaction_type = str(
        record.get("type") or "transaction"
    ).casefold()
    date_label = format_activity_date(transaction_created_ms(record))
    added = asset_names(record.get("adds"), roster_id)
    dropped = asset_names(record.get("drops"), roster_id)
    picks_received, picks_sent = transaction_pick_moves(record, roster_id)

    if transaction_type == "trade":
        other_ids = sorted(transaction_roster_ids(record) - {roster_id})
        counterparties = [
            ROSTER_NAMES.get(value, f"roster {value}")
            for value in other_ids
        ]
        opening = f"On {date_label}, {team['team_name']} completed a trade"
        if counterparties:
            opening += f" with {', '.join(counterparties)}"

        received = [*added, *picks_received]
        sent = [*dropped, *picks_sent]
        details: list[str] = []
        if received:
            details.append(f"acquired {', '.join(received)}")
        if sent:
            details.append(f"sent {', '.join(sent)}")
        return opening + (
            f" and {' while '.join(details)}."
            if details
            else "."
        )

    if transaction_type == "waiver":
        opening = (
            f"On {date_label}, {team['team_name']} completed a waiver claim"
        )
    elif transaction_type in {"free_agent", "free agent"}:
        opening = (
            f"On {date_label}, {team['team_name']} completed a free-agent move"
        )
    else:
        opening = (
            f"On {date_label}, {team['team_name']} completed a roster transaction"
        )

    details = []
    if added:
        details.append(f"added {', '.join(added)}")
    if dropped:
        details.append(f"dropped {', '.join(dropped)}")
    return opening + (
        f" and {' while '.join(details)}."
        if details
        else "."
    )


def latest_verified_activity(
    team: dict[str, Any],
    ledger: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any] | None:
    cutoff_ms = int(
        (now.astimezone(generator.UTC) - timedelta(days=365)).timestamp()
        * 1000
    )
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
                datetime.fromisoformat(
                    str(trade["created_at"]).replace("Z", "+00:00")
                ).timestamp()
                * 1000
            )
        except ValueError:
            trade_ms = 0

    sleeper_ms = (
        transaction_created_ms(sleeper_record)
        if sleeper_record
        else 0
    )

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
            "type": str(
                sleeper_record.get("type") or "transaction"
            ),
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
        "latest_trade": (
            activity
            if activity and activity.get("type") == "trade"
            else None
        ),
        "latest_activity": activity,
        "summary": (
            activity["summary"]
            if activity
            else (
                f"No completed transaction for {team['team_name']} was "
                "found in the last 365 days of the authoritative "
                "AVI-Core activity files."
            )
        ),
    }


def build_summary_with_canonical_fields(
    team: dict[str, Any],
    above: dict[str, Any] | None,
    below: dict[str, Any] | None,
    ledger: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    summary = _original_build_summary(
        team,
        above,
        below,
        ledger,
        now,
    )

    summary["schema_version"] = 6
    summary["dynasty_power"] = {
        "rank": team["dynasty_rank"],
        "league_size": EXPECTED_FRANCHISE_COUNT,
        "score": team["dynasty_score"],
        "player_d_avi": team.get("player_d_avi", 0.0),
        "future_pick_d_avi": team.get("future_pick_d_avi", 0.0),
        "method": (
            "Canonical Power Rankings D-AVI ladder: full verified roster "
            "D-AVI plus every verified owned 2027+ draft pick D-AVI"
        ),
    }

    useful_moves = [
        move
        for move in summary.get("gap_closing_moves", [])
        if not NO_PICK_RECOMMENDATION_RE.search(move)
    ]
    summary["gap_closing_moves"] = useful_moves

    rival = summary.get("rival_below")
    team_below = summary.get("projected_power", {}).get("team_below")
    if rival is not None and team_below is not None:
        rival["franchise_name"] = team_below["name"]
        rival["projected_rank"] = team_below["rank"]
        rival["projected_score"] = team_below["score"]

    for section in summary.get("sections", []):
        if section.get("id") == "close-the-gap":
            section["items"] = useful_moves
            section["body"] = " ".join(useful_moves)
        elif section.get("id") == "rival-watch":
            section["body"] = (
                rival.get("summary")
                if rival
                else (
                    "This franchise is currently projected last, so there "
                    "is no team immediately beneath it."
                )
            )
        elif section.get("id") == "draft-assets" and not team.get(
            "draft_assets"
        ):
            section["body"] = (
                "No verified future draft assets are currently included "
                "in this summary."
            )

    return summary


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

    for path in franchise_files:
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

        projected = payload.get("projected_power") or {}
        team_below = projected.get("team_below")
        rival = payload.get("rival_below")

        if team_below is None:
            if rival is not None:
                raise RuntimeError(
                    f"Last-place franchise unexpectedly has Rival Watch in {path}"
                )
        else:
            if not rival:
                raise RuntimeError(
                    f"Rival Watch is missing in {path}"
                )
            if rival.get("franchise_name") != team_below.get("name"):
                raise RuntimeError(
                    f"Rival Watch team does not match team_below in {path}"
                )
            if rival.get("projected_rank") != team_below.get("rank"):
                raise RuntimeError(
                    f"Rival Watch rank does not match team_below in {path}"
                )
            if "latest_activity" not in rival:
                raise RuntimeError(
                    f"Rival Watch is missing latest_activity in {path}"
                )

        dynasty = payload.get("dynasty_power") or {}
        expected_total = round(
            float(dynasty.get("player_d_avi") or 0.0)
            + float(dynasty.get("future_pick_d_avi") or 0.0),
            2,
        )
        if round(float(dynasty.get("score") or 0.0), 2) != expected_total:
            raise RuntimeError(
                f"Dynasty score does not reconcile in {path}"
            )

        for move in payload.get("gap_closing_moves") or []:
            if NO_PICK_RECOMMENDATION_RE.search(move):
                raise RuntimeError(
                    f"Removed no-pick recommendation remains in {path}"
                )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    if manifest.get("franchise_count") != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Manifest franchise_count is "
            f"{manifest.get('franchise_count')!r}; expected "
            f"{EXPECTED_FRANCHISE_COUNT}"
        )
    if len(manifest.get("files") or []) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            "Manifest does not declare all 16 franchise summaries"
        )

    print(
        f"Validated {EXPECTED_FRANCHISE_COUNT} franchise summaries "
        f"and manifest in {VERIFIED_OUTPUT_DIR}"
    )


generator.split_assets = split_assets_with_team_names
generator.latest_trade = latest_non_blacklisted_trade
generator.parse_team = parse_team_with_canonical_dynasty
generator.gap_actions = gap_actions_without_unverified_pick_language
generator.rival_snapshot = rival_snapshot_with_latest_activity
generator.build_summary = build_summary_with_canonical_fields


def main() -> None:
    print(f"Using team profiles from: {VERIFIED_TEAMS_DIR}")
    print(f"Writing franchise summaries to: {VERIFIED_OUTPUT_DIR}")
    print(f"Verified roster mappings: {len(ROSTER_NAMES)}")
    print(
        f"Verified completed transactions loaded: "
        f"{len(VERIFIED_TRANSACTIONS)}"
    )

    generator.main()
    validate_outputs()


if __name__ == "__main__":
    main()
