from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable

from avi.calculate_avi import build_avi_players
from avi.fantasypros.updater import update as update_fantasypros
from avi.identity.builder import build_player_identity_map
from avi.identity.registry import build_player_registry
from avi.reports.draft_pick_values import build_draft_pick_values
from avi.reports.historical_trades import build_historical_trades
from avi.reports.player_lookup import build_player_lookup
from avi.reports.team_profiles import build_team_profiles
from avi.sleeper.updater import update as update_sleeper
from avi.validation.source import (
    validate_fantasypros,
    validate_sleeper,
)


PipelineStep = tuple[
    str,
    Callable[[], Any],
]


def run_daily_update(
    config: Any,
) -> dict[str, Any]:
    """
    Run the complete AVI daily update pipeline.

    The pipeline stops immediately if any step raises an exception.
    This prevents downstream reports from being generated from
    incomplete or invalid source data.
    """
    started_at = datetime.now(
        UTC
    )

    steps: list[PipelineStep] = [
        (
            "update_sleeper",
            lambda: update_sleeper(
                config
            ),
        ),
        (
            "validate_sleeper",
            lambda: validate_sleeper(
                config
            ),
        ),
        (
            "update_fantasypros",
            lambda: update_fantasypros(
                config
            ),
        ),
        (
            "validate_fantasypros",
            validate_fantasypros,
        ),
        (
            "build_identities",
            build_player_identity_map,
        ),
        (
            "build_registry",
            build_player_registry,
        ),
        (
            "calculate_avi",
            build_avi_players,
        ),
        (
            "build_draft_pick_values",
            build_draft_pick_values,
        ),
        (
            "build_historical_trades",
            build_historical_trades,
        ),
        (
            "build_team_profiles",
            build_team_profiles,
        ),
        (
            "build_player_lookup",
            build_player_lookup,
        ),
    ]

    completed_steps: list[str] = []
    step_results: dict[
        str,
        Any,
    ] = {}

    print()
    print("=" * 60)
    print("AVI DAILY UPDATE STARTED")
    print("=" * 60)

    for index, (
        step_name,
        step,
    ) in enumerate(
        steps,
        start=1,
    ):
        print()
        print(
            f"[{index}/{len(steps)}] "
            f"{step_name}"
        )
        print("-" * 60)

        result = step()

        completed_steps.append(
            step_name
        )

        step_results[
            step_name
        ] = result

        print(
            f"Completed: {step_name}"
        )

    finished_at = datetime.now(
        UTC
    )

    summary = {
        "status": "passed",
        "started_at_utc": (
            started_at.isoformat()
        ),
        "finished_at_utc": (
            finished_at.isoformat()
        ),
        "duration_seconds": round(
            (
                finished_at
                - started_at
            ).total_seconds(),
            2,
        ),
        "completed_steps": (
            completed_steps
        ),
        "step_count": len(
            completed_steps
        ),
        "step_results": (
            step_results
        ),
    }

    print()
    print("=" * 60)
    print("AVI DAILY UPDATE COMPLETE")
    print("=" * 60)
    print(
        f"Steps completed: "
        f"{len(completed_steps)}"
    )
    print(
        f"Duration: "
        f"{summary['duration_seconds']} seconds"
    )

    return summary