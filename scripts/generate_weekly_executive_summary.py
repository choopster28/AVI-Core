from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "reports" / "weekly_executive_summaries" / "big-balder-brand.json"


def mountain_now() -> datetime:
    return datetime.now(ZoneInfo("America/Denver"))


def build_summary() -> dict:
    now = mountain_now()
    season_mode = "preseason" if now.month < 9 else "regular_season"

    preseason_sections = [
        {
            "title": "Front Office Snapshot",
            "body": "Big Balder Brand enters the 2026 cycle as an Elite Contender with a legitimate championship window. The roster is built to win now without being forced into an all-in move, so the best path is targeted improvement rather than broad turnover."
        },
        {
            "title": "Recommended Focus",
            "body": "Prioritize moves that raise the weekly starting-lineup ceiling, especially at the weakest starting position, while protecting premium young assets. Depth-for-upgrade consolidation is preferable to spending multiple future first-round assets on a marginal gain."
        },
        {
            "title": "Roster Intelligence",
            "body": "Monitor veteran recovery timelines, training-camp role changes, and any injury that affects the opening-week lineup. When no material injury is present, the report should explicitly note that the roster stayed healthy and no emergency move is required."
        },
        {
            "title": "Draft Room",
            "body": "Use the 1.01 on the highest-confidence cornerstone available and treat later premium selections as opportunities to add either a falling offensive prospect or a difference-making IDP. Draft recommendations must be refreshed against the live pick board and actual players still available."
        },
        {
            "title": "AVI Watchlist",
            "body": "Track one rising asset, one risk factor, and one decision point each week. For this roster, the key question is whether an available move creates a clear starting-lineup advantage without shortening the competitive window more than necessary."
        }
    ]

    regular_sections = [
        {"title": "Weekly Matchup Recap", "body": "Generated from the completed Sleeper matchup once regular-season scoring is available."},
        {"title": "Upcoming Matchup", "body": "Generated from the next scheduled opponent, projected lineup strengths, and current availability."},
        {"title": "Recommended Focus", "body": "Generated from lineup gaps, waiver options, trade market reality, and playoff positioning."},
        {"title": "Injury Report", "body": "Generated from verified weekly injuries and recommended replacement paths; otherwise confirms the roster remained healthy."},
        {"title": "Conference, Division & Standings", "body": "Generated from weekly conference and division results with updated standings and playoff implications."}
    ]

    return {
        "schema_version": 1,
        "franchise_id": "big-balder-brand",
        "franchise_name": "Big Balder Brand",
        "mode": season_mode,
        "reporting_period": now.strftime("Week of %B %-d, %Y"),
        "generated_at": now.isoformat(),
        "refresh_schedule": "Wednesdays at 11:00 AM America/Denver",
        "confidence": "pilot",
        "headline": "Big Balder Brand Weekly Executive Summary",
        "lede": "A concise front-office briefing built from AVI-Core data and the approved AVI instruction set.",
        "sections": preseason_sections if season_mode == "preseason" else regular_sections,
        "next_refresh": "Wednesday at 11:00 AM Mountain Time",
        "notes": [
            "Pilot edition for Big Balder Brand.",
            "Regular-season matchup, standings, conference, division, and injury sections activate when verified 2026 weekly data is available.",
            "Future iterations will replace general pilot language with fully hydrated franchise-specific facts from AVI-Core feeds."
        ]
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_summary(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
