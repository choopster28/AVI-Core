from __future__ import annotations

import argparse
import json

from avi.calculate_avi import build_avi_players
from avi.config import load_config
from avi.fantasypros.updater import update as update_fantasypros
from avi.identity.builder import build_player_identity_map
from avi.identity.registry import build_player_registry
from avi.league.loader import load_league_structure
from avi.pipeline import run_daily_update
from avi.reports.draft_pick_values import build_draft_pick_values
from avi.reports.historical_trades import build_historical_trades
from avi.reports.player_lookup import build_player_lookup
from avi.reports.team_profiles import build_team_profiles
from avi.sleeper.updater import update as update_sleeper
from avi.validation.source import (
    validate_fantasypros,
    validate_sleeper,
)
from avi.valuation.picks import first_round_pick_table


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="avi")

    commands = root.add_subparsers(
        dest="command",
        required=True,
    )

    commands.add_parser("update-sleeper")
    commands.add_parser("validate-sleeper")
    commands.add_parser("update-fantasypros")
    commands.add_parser("validate-fantasypros")

    commands.add_parser("build-identities")
    commands.add_parser("build-registry")
    commands.add_parser("calculate-avi")
    commands.add_parser("build-team-profiles")
    commands.add_parser("build-player-lookup")
    commands.add_parser("build-historical-trades")
    commands.add_parser("build-draft-pick-values")
    commands.add_parser("daily-update")

    commands.add_parser("show-pick-values")
    commands.add_parser("show-league-structure")

    return root


def main() -> None:
    args = parser().parse_args()
    config = load_config()

    if args.command == "update-sleeper":
        update_sleeper(config)

    elif args.command == "validate-sleeper":
        validate_sleeper(config)

    elif args.command == "update-fantasypros":
        update_fantasypros(config)

    elif args.command == "validate-fantasypros":
        validate_fantasypros()

    elif args.command == "build-identities":
        build_player_identity_map()

    elif args.command == "build-registry":
        build_player_registry()

    elif args.command == "calculate-avi":
        build_avi_players()

    elif args.command == "build-team-profiles":
        build_team_profiles()

    elif args.command == "build-player-lookup":
        build_player_lookup()

    elif args.command == "build-historical-trades":
        build_historical_trades()

    elif args.command == "build-draft-pick-values":
        build_draft_pick_values()

    elif args.command == "daily-update":
        run_daily_update(config)

    elif args.command == "show-pick-values":
        print(
            json.dumps(
                first_round_pick_table(),
                indent=2,
            )
        )

    elif args.command == "show-league-structure":
        structure = load_league_structure()

        print(
            json.dumps(
                {
                    "league_id": structure.league_id,
                    "league_name": structure.league_name,
                    "season": structure.season,
                    "team_count": structure.team_count,
                    "starter_counts": structure.starter_counts,
                    "bench_spots": structure.bench_spots,
                    "reserve_spots": structure.reserve_spots,
                    "playoff_teams": structure.playoff_teams,
                    "playoff_start_week": structure.playoff_start_week,
                    "trade_deadline_week": structure.trade_deadline_week,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()