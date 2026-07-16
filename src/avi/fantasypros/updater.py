from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from avi.config import AviConfig
from avi.fantasypros.checkpoint import (
    is_completed,
    load_checkpoint,
    mark_completed,
    mark_failed,
    reset_checkpoint,
)
from avi.fantasypros.client import FantasyProsClient
from avi.io import write_json


RAW = Path("data/raw/fantasypros")

POSITIONS = (
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
    "DL",
    "LB",
    "DB",
)

PLAYER_POINT_POSITIONS = (
    "QB",
    "RB",
    "WR",
    "TE",
    "K",
    "DE",
    "DT",
    "LB",
    "CB",
    "S",
    "DB",
)


def download_dataset(
    *,
    checkpoint: dict[str, Any],
    dataset_key: str,
    output_path: Path,
    downloader: Callable[[], Any],
) -> Any | None:
    """
    Download one FantasyPros dataset.

    Completed datasets are skipped when both the checkpoint entry and
    output file exist. Failed datasets remain available for the next run.
    """
    if is_completed(checkpoint, dataset_key) and output_path.exists():
        print(f"Skipping completed dataset: {dataset_key}")
        return None

    print(f"Downloading: {dataset_key}")

    try:
        payload = downloader()
    except Exception:
        mark_failed(checkpoint, dataset_key)
        raise

    write_json(output_path, payload)
    mark_completed(checkpoint, dataset_key)

    return payload


def update(config: AviConfig) -> dict[str, Any]:
    client = FantasyProsClient(
        config.fantasypros_base_url,
        config.fantasypros_api_key,
        config.fantasypros_api_key_header,
        max_requests_per_run=(
            config.fantasypros_max_requests_per_run
        ),
    )

    checkpoint = load_checkpoint()
    warnings: list[str] = []

    print("=" * 60)
    print("AVI FANTASYPROS UPDATE")
    print("=" * 60)
    print(
        "Previously completed datasets: "
        f"{len(checkpoint.get('completed', []))}"
    )
    print()

    download_dataset(
        checkpoint=checkpoint,
        dataset_key="players",
        output_path=RAW / "players.json",
        downloader=client.players,
    )

    download_dataset(
        checkpoint=checkpoint,
        dataset_key="injuries",
        output_path=RAW / "injuries.json",
        downloader=lambda: client.injuries(
            config.avi_season
        ),
    )

    download_dataset(
        checkpoint=checkpoint,
        dataset_key="news",
        output_path=RAW / "news.json",
        downloader=client.news,
    )

    for position in POSITIONS:
        dataset_key = f"projections_{position}"
        output_path = (
            RAW
            / "projections"
            / f"{position}.json"
        )

        try:
            download_dataset(
                checkpoint=checkpoint,
                dataset_key=dataset_key,
                output_path=output_path,
                downloader=lambda position=position: (
                    client.projections(
                        config.avi_season,
                        position,
                    )
                ),
            )
        except Exception as exc:
            if position in {"DL", "LB", "DB"}:
                warning = (
                    f"{position} projections unavailable: "
                    f"{type(exc).__name__}: {exc}"
                )
                warnings.append(warning)
                print(f"WARNING: {warning}")

                # Preserve the approved IDP baseline and do not repeatedly
                # spend requests on an unsupported projection dataset.
                mark_completed(
                    checkpoint,
                    dataset_key,
                )
                continue

            raise

    for position in POSITIONS:
        dataset_key = f"dynasty_rankings_{position}"

        download_dataset(
            checkpoint=checkpoint,
            dataset_key=dataset_key,
            output_path=(
                RAW
                / "rankings"
                / "dynasty"
                / f"{position}.json"
            ),
            downloader=lambda position=position: (
                client.consensus_rankings(
                    config.avi_season,
                    position,
                    "DYNASTY",
                    config.avi_scoring,
                    position in {"DL", "LB", "DB"},
                )
            ),
        )

    for position in POSITIONS:
        dataset_key = f"redraft_rankings_{position}"

        download_dataset(
            checkpoint=checkpoint,
            dataset_key=dataset_key,
            output_path=(
                RAW
                / "rankings"
                / "redraft"
                / f"{position}.json"
            ),
            downloader=lambda position=position: (
                client.consensus_rankings(
                    config.avi_season,
                    position,
                    "DRAFT",
                    config.avi_scoring,
                    position in {"DL", "LB", "DB"},
                )
            ),
        )

    for position in PLAYER_POINT_POSITIONS:
        dataset_key = f"player_points_{position}"

        download_dataset(
            checkpoint=checkpoint,
            dataset_key=dataset_key,
            output_path=(
                RAW
                / "player_points"
                / f"{position}.json"
            ),
            downloader=lambda position=position: (
                client.player_points(
                    config.avi_season,
                    position,
                    config.avi_scoring,
                )
            ),
        )

    downloaded_at = datetime.now(UTC)

    manifest = {
        "snapshot_id": downloaded_at.strftime(
            "%Y-%m-%dT%H-%M-%SZ"
        ),
        "downloaded_at_utc": downloaded_at.isoformat(),
        "season": config.avi_season,
        "scoring": config.avi_scoring,
        "methodology_version": (
            config.methodology_version
        ),
        "request_budget": {
            "used": client.requests_used,
            "maximum": (
                client.max_requests_per_run
            ),
        },
        "player_points": {
            "collected": True,
            "preseason_weight": 0.0,
            "in_season_weight": 0.10,
            "currently_used_in_c_avi": False,
        },
        "warnings": warnings,
        "status": "passed",
    }

    write_json(
        RAW / "manifest.json",
        manifest,
    )

    # A fully successful update is complete. Clear the checkpoint so the
    # next scheduled FantasyPros refresh downloads fresh source data.
    reset_checkpoint()

    print()
    print("=" * 60)
    print("FANTASYPROS UPDATE COMPLETED")
    print("=" * 60)
    print(
        "Requests used this invocation: "
        f"{client.requests_used}/"
        f"{client.max_requests_per_run}"
    )

    return manifest