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
            "title": "Where Big Balder Stands",
            "body": "Big Balder enters 2026 in full championship mode after finishing third last season. The roster has enough established production to compete immediately and enough usable dynasty value to avoid a reckless all-in approach. The mission is simple: close the gap at the top without sacrificing the ability to contend again in 2027 and 2028."
        },
        {
            "title": "The Move That Matters",
            "body": "Do not chase volume for the sake of activity. Big Balder should pursue consolidation only when it creates a clear weekly starter upgrade. Jameson Williams is easier to move once Jeremiyah Love enters the flex plan, but he should not be sold cheaply just because his lineup role changes. The ideal deal converts expendable depth or future capital into proven production at the roster's weakest championship position."
        },
        {
            "title": "Training Room & Roster Watch",
            "body": "The roster does not require an emergency repair this week. The important monitoring points are veteran recovery timelines, any camp development that changes Brenton Strange's long-term trajectory, and whether the planned starting group reaches Week 1 intact. A healthy preseason favors patience; an injury to a core starter would justify a targeted response rather than a broad roster shakeup."
        },
        {
            "title": "Draft Room: Build Around 1.01",
            "body": "The draft plan begins with Jeremiyah Love at 1.01. His arrival gives Big Balder another high-upside starter and makes the offense less dependent on Jameson Williams occupying a weekly flex spot. At 1.15, the priority should be value over forced need: take the best falling offensive prospect unless a premium IDP with immediate impact separates clearly from the board."
        },
        {
            "title": "This Week's Front-Office Checklist",
            "body": "Hold the core. Keep Love's arrival central to every roster decision. Test the market for a meaningful starter upgrade, but reject lateral deals dressed up as win-now moves. The best outcome this week may be no transaction at all if the available prices require Big Balder to pay elite capital for only a marginal lineup gain."
        }
    ]

    regular_sections = [
        {"title": "What Happened Sunday", "body": "Generated from Big Balder Brand's completed Sleeper matchup, scoring swings, lineup decisions, and the players who changed the result."},
        {"title": "Next Opponent", "body": "Generated from the scheduled opponent, projected starters, positional advantages, and current player availability."},
        {"title": "The Weekly Edge", "body": "Generated from Big Balder's lineup gaps, waiver options, realistic trade paths, and playoff positioning."},
        {"title": "Training Room", "body": "Generated from verified injuries and replacement options; when the roster is healthy, the report will say so directly."},
        {"title": "Conference & Division Pulse", "body": "Generated from the week's conference and division results, updated standings, and the teams affecting Big Balder's playoff path."}
    ]

    return {
        "schema_version": 1,
        "franchise_id": "big-balder-brand",
        "franchise_name": "Big Balder Brand",
        "mode": season_mode,
        "reporting_period": now.strftime("Week of %B %-d, %Y"),
        "generated_at": now.isoformat(),
        "refresh_schedule": "Wednesdays at 11:00 AM America/Denver",
        "confidence": "current",
        "headline": "Big Balder Brand: The Final Push Starts Now" if season_mode == "preseason" else "Big Balder Brand Weekly Command Brief",
        "lede": "Big Balder is already built like a contender. This preseason is not about rebuilding the roster; it is about turning a strong core, the 1.01, and a two-year championship window into the one or two advantages that separate a playoff team from the favorite." if season_mode == "preseason" else "A direct read on what changed, what comes next, and the move most likely to improve Big Balder Brand's championship odds.",
        "sections": preseason_sections if season_mode == "preseason" else regular_sections,
        "next_refresh": "Wednesday at 11:00 AM Mountain Time",
        "notes": [
            "Regular-season matchup, standings, conference, division, and weekly injury sections activate when verified 2026 scoring data is available.",
            "Recommendations are written specifically for Big Balder Brand's current championship window, roster plan, and verified draft position."
        ]
    }


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(build_summary(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
