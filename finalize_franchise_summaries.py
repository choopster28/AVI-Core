from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SUMMARY_DIR = ROOT / "knowledge" / "franchise_summaries"
PICK_VALUES_PATH = ROOT / "data" / "processed" / "reports" / "draft_pick_values.json"
CURRENT_SEASON = 2026
EXPECTED_FRANCHISE_COUNT = 16

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


def load_owned_pick_totals() -> dict[int, float]:
    """Total every verified currently owned pick from the current draft onward."""
    payload = json.loads(PICK_VALUES_PATH.read_text(encoding="utf-8"))
    totals: dict[int, float] = {}

    for pick in payload.get("picks", []):
        if not isinstance(pick, dict):
            continue
        season = int(pick.get("season") or 0)
        if season < CURRENT_SEASON:
            continue
        try:
            roster_id = int(pick.get("current_owner_roster_id"))
        except (TypeError, ValueError):
            continue
        totals[roster_id] = totals.get(roster_id, 0.0) + number(
            pick.get("draft_pick_avi")
        )

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
            7,
        )
        summary["dynasty_power"] = {
            "rank": 0,
            "league_size": EXPECTED_FRANCHISE_COUNT,
            "score": total,
            "player_d_avi": round(player_d_avi, 2),
            "future_pick_d_avi": round(owned_pick_d_avi, 2),
            "method": (
                "Canonical Power Rankings D-AVI ladder: full verified roster "
                "D-AVI plus every verified currently owned 2026+ draft pick AVI "
                "from data/processed/reports/draft_pick_values.json"
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
        5,
    )
    manifest["dynasty_power_method"] = (
        "Full roster D-AVI plus verified currently owned 2026+ draft-pick AVI"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "Finalized 16 franchise summaries with canonical dynasty ranks, "
        "all currently owned draft-pick values, and verified Rival Watch attribution."
    )


if __name__ == "__main__":
    main()
