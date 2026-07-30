from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SUMMARY_DIR = ROOT / "knowledge" / "franchise_summaries"
PICK_VALUES_PATH = ROOT / "data" / "processed" / "reports" / "draft_pick_values.json"
HISTORICAL_TRADES_PATH = ROOT / "data" / "processed" / "reports" / "historical_trades.json"
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


def latest_traded_picks_path() -> Path | None:
    candidates = sorted(
        (ROOT / "data" / "raw" / "sleeper" / "leagues").glob(
            "*/traded_picks.json"
        ),
        reverse=True,
    )
    return candidates[0] if candidates else None


def load_live_pick_owners() -> dict[tuple[int, int, int], int]:
    path = latest_traded_picks_path()
    if not path:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    owners: dict[tuple[int, int, int], int] = {}
    for pick in payload if isinstance(payload, list) else []:
        if not isinstance(pick, dict):
            continue
        try:
            key = (
                int(pick.get("season")),
                int(pick.get("round")),
                int(pick.get("roster_id")),
            )
            owners[key] = int(pick.get("owner_id"))
        except (TypeError, ValueError):
            continue
    return owners


def load_owned_pick_totals() -> dict[int, float]:
    """Rebuild the exact current/future pick ledger used by Autobots HQ."""
    payload = json.loads(PICK_VALUES_PATH.read_text(encoding="utf-8"))
    raw = [pick for pick in payload.get("picks", []) if isinstance(pick, dict)]
    historical = json.loads(HISTORICAL_TRADES_PATH.read_text(encoding="utf-8"))
    live_owners = load_live_pick_owners()

    roster_ids: set[int] = set()
    future_seasons: set[int] = set()
    max_round = 0
    round_values: dict[tuple[int, int], list[float]] = {}

    for pick in raw:
        try:
            season = int(pick.get("season") or 0)
            round_value = int(pick.get("round") or 0)
        except (TypeError, ValueError):
            continue
        max_round = max(max_round, round_value)
        round_values.setdefault((season, round_value), []).append(
            number(pick.get("draft_pick_avi"))
        )
        for field in ("original_roster_id", "current_owner_roster_id"):
            try:
                roster_ids.add(int(pick.get(field)))
            except (TypeError, ValueError):
                pass
        if (
            pick.get("validation_status") == "future_order_tbd"
            or str(pick.get("current_owner_team") or "").strip().casefold()
            == "tbd"
        ):
            future_seasons.add(season)

    if len(roster_ids) != EXPECTED_FRANCHISE_COUNT:
        raise RuntimeError(
            f"Expected {EXPECTED_FRANCHISE_COUNT} roster ids in pick values, "
            f"found {len(roster_ids)}"
        )

    totals = {roster_id: 0.0 for roster_id in roster_ids}

    # Current slotted class: use live Sleeper ownership first, then processed owner.
    for pick in raw:
        try:
            season = int(pick.get("season") or 0)
            round_value = int(pick.get("round") or 0)
            original_id = int(pick.get("original_roster_id"))
        except (TypeError, ValueError):
            continue
        is_future = (
            pick.get("validation_status") == "future_order_tbd"
            or str(pick.get("current_owner_team") or "").strip().casefold()
            == "tbd"
        )
        if is_future:
            continue
        try:
            feed_owner = int(pick.get("current_owner_roster_id"))
        except (TypeError, ValueError):
            feed_owner = original_id
        owner_id = live_owners.get(
            (season, round_value, original_id),
            feed_owner,
        )
        if owner_id in totals:
            totals[owner_id] += number(pick.get("draft_pick_avi"))

    # Future classes: native ownership for every round, then apply verified trades.
    rounds_per_season = max(max_round, 10)
    future_ledger: dict[tuple[int, int, int], int] = {}
    for season in future_seasons:
        for round_value in range(1, rounds_per_season + 1):
            for original_id in roster_ids:
                future_ledger[(season, round_value, original_id)] = original_id

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
                if key in future_ledger:
                    future_ledger[key] = receiver_id

    # Raw Sleeper traded-picks data is the freshest ownership override.
    for key, owner_id in live_owners.items():
        if key in future_ledger and owner_id in roster_ids:
            future_ledger[key] = owner_id

    round_average = {
        key: round(sum(values) / len(values), 1) if values else 0.0
        for key, values in round_values.items()
    }
    for (season, round_value, _original_id), owner_id in future_ledger.items():
        totals[owner_id] += round_average.get((season, round_value), 0.0)

    return {
        roster_id: round(total, 2)
        for roster_id, total in totals.items()
    }


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
                    "Draft capital is included only when verified by the "
                    "canonical draft-pick ledger."
                )


def validate_rival(summary: dict[str, Any], path: Path) -> None:
    projected = summary.get("projected_power") or {}
    team_below = projected.get("team_below")
    rival = summary.get("rival_below")

    if team_below is None:
        if rival is not None:
            raise RuntimeError(
                f"Unexpected Rival Watch for last-place franchise: {path}"
            )
        return

    if not rival:
        raise RuntimeError(f"Missing Rival Watch in {path}")
    if rival.get("franchise_name") != team_below.get("name"):
        raise RuntimeError(
            f"Rival Watch franchise does not match team_below in {path}"
        )
    if rival.get("projected_rank") != team_below.get("rank"):
        raise RuntimeError(
            f"Rival Watch rank does not match team_below in {path}"
        )
    if "latest_activity" not in rival:
        raise RuntimeError(
            f"Rival Watch latest_activity is missing in {path}"
        )


def main() -> None:
    owned_pick_totals = load_owned_pick_totals()
    paths = sorted(
        path
        for path in SUMMARY_DIR.glob("*.json")
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
        player_d_avi = number(
            dynasty.get("player_d_avi", dynasty.get("score"))
        )
        owned_pick_d_avi = owned_pick_totals.get(roster_id, 0.0)
        total = round(player_d_avi + owned_pick_d_avi, 2)

        summary["schema_version"] = max(
            int(summary.get("schema_version") or 0),
            8,
        )
        summary["dynasty_power"] = {
            "rank": 0,
            "league_size": EXPECTED_FRANCHISE_COUNT,
            "score": total,
            "player_d_avi": round(player_d_avi, 2),
            "future_pick_d_avi": round(owned_pick_d_avi, 2),
            "method": (
                "Canonical Autobots HQ D-AVI ladder: full verified roster D-AVI "
                "plus the reconstructed live 2027+ pick ledger using native picks, "
                "historical trades, raw Sleeper ownership, and round-average AVI"
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
        path.write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )

    manifest_path = SUMMARY_DIR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = max(
        int(manifest.get("schema_version") or 0),
        6,
    )
    manifest["dynasty_power_method"] = (
        "Full roster D-AVI plus reconstructed live 2027+ pick ownership and values"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "Finalized 16 franchise summaries using the same reconstructed future-pick "
        "ledger as Autobots HQ."
    )


if __name__ == "__main__":
    main()
