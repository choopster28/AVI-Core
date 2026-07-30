from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SUMMARY_DIR = ROOT / "knowledge" / "franchise_summaries"
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


def active_traded_picks_path() -> Path | None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    seasons = [
        row for row in manifest.get("season_results", [])
        if row.get("league_id") and isinstance(row.get("season"), int)
    ]
    if not seasons:
        return None
    latest = max(seasons, key=lambda row: int(row["season"]))
    return (
        ROOT
        / "data"
        / "raw"
        / "sleeper"
        / "leagues"
        / f"{latest['season']}_{latest['league_id']}"
        / "traded_picks.json"
    )


def load_live_pick_owners() -> dict[tuple[int, int, int], int]:
    path = active_traded_picks_path()
    if not path or not path.is_file():
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


def main() -> None:
    future_pick_totals = load_future_pick_totals()
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
        dynasty = summary.get("dynasty_power") or {}
        player_d_avi = number(dynasty.get("player_d_avi", dynasty.get("score")))
        future_pick_d_avi = future_pick_totals.get(roster_id, 0.0)
        total = round(player_d_avi + future_pick_d_avi, 2)

        summary["schema_version"] = max(int(summary.get("schema_version") or 0), 9)
        summary["dynasty_power"] = {
            "rank": 0,
            "league_size": EXPECTED_FRANCHISE_COUNT,
            "score": total,
            "player_d_avi": round(player_d_avi, 2),
            "future_pick_d_avi": round(future_pick_d_avi, 2),
            "method": (
                "Canonical Autobots HQ D-AVI ladder: full verified roster D-AVI "
                "plus reconstructed live 2027+ ownership valued with the shared "
                "projected draft-pick curve"
            ),
        }
        remove_disallowed_pick_language(summary)
        validate_rival(summary, path)
        rows.append((path, summary))

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
        path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    manifest_path = SUMMARY_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = max(int(manifest.get("schema_version") or 0), 7)
    manifest["dynasty_power_method"] = (
        "Full roster D-AVI plus reconstructed live 2027+ ownership valued with "
        "the canonical projected draft-pick curve"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("Finalized 16 summaries with the exact Autobots HQ dynasty ladder model.")


if __name__ == "__main__":
    main()
