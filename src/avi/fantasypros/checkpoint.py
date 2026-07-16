from __future__ import annotations

from pathlib import Path
from typing import Any

from avi.io import read_json, write_json


CHECKPOINT_PATH = Path(
    "data/processed/fantasypros/checkpoint.json"
)


def load_checkpoint() -> dict[str, Any]:
    if not CHECKPOINT_PATH.exists():
        return {
            "completed": [],
            "failed": [],
        }

    checkpoint = read_json(CHECKPOINT_PATH)

    if not isinstance(checkpoint, dict):
        raise RuntimeError(
            "FantasyPros checkpoint is not a JSON object."
        )

    checkpoint.setdefault("completed", [])
    checkpoint.setdefault("failed", [])

    return checkpoint


def save_checkpoint(
    checkpoint: dict[str, Any],
) -> None:
    write_json(
        CHECKPOINT_PATH,
        checkpoint,
    )


def is_completed(
    checkpoint: dict[str, Any],
    dataset_key: str,
) -> bool:
    completed = checkpoint.get(
        "completed",
        [],
    )

    return dataset_key in completed


def mark_completed(
    checkpoint: dict[str, Any],
    dataset_key: str,
) -> None:
    completed = checkpoint.setdefault(
        "completed",
        [],
    )

    failed = checkpoint.setdefault(
        "failed",
        [],
    )

    if dataset_key not in completed:
        completed.append(dataset_key)

    if dataset_key in failed:
        failed.remove(dataset_key)

    save_checkpoint(checkpoint)


def mark_failed(
    checkpoint: dict[str, Any],
    dataset_key: str,
) -> None:
    failed = checkpoint.setdefault(
        "failed",
        [],
    )

    if dataset_key not in failed:
        failed.append(dataset_key)

    save_checkpoint(checkpoint)


def reset_checkpoint() -> None:
    save_checkpoint(
        {
            "completed": [],
            "failed": [],
        }
    )