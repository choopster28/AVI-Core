from __future__ import annotations

import argparse

from avi.config import load_config
from avi.fantasypros.updater import update_fantasypros
from avi.sleeper.updater import update_sleeper
from avi.validation.sleeper import validate_sleeper_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="avi",
        description="Autobots Value Index automation",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sleeper-update", help="Download Sleeper data from 2024 onward")
    commands.add_parser("fantasypros-update", help="Download configured FantasyPros data")
    commands.add_parser("validate-sleeper", help="Validate Sleeper and trade outputs")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config()

    if args.command == "sleeper-update":
        update_sleeper(config)
    elif args.command == "fantasypros-update":
        update_fantasypros(config)
    elif args.command == "validate-sleeper":
        validate_sleeper_outputs(config)
