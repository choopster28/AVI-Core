from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from avi.config import AviConfig
from avi.fantasypros.client import FantasyProsClient
from avi.io import write_json


RAW_ROOT = Path("data/raw/fantasypros")


def update_fantasypros(config: AviConfig) -> dict[str, Any]:
    client = FantasyProsClient(
        base_url=config.fantasypros_base_url,
        api_key=config.fantasypros_api_key,
        api_key_header=config.fantasypros_api_key_header,
    )

    endpoints = {
        "players": config.fantasypros_players_path,
        "projections": config.fantasypros_projections_path,
        "rankings": config.fantasypros_rankings_path,
        "injuries": config.fantasypros_injuries_path,
        "news": config.fantasypros_news_path,
    }

    downloaded: dict[str, Any] = {}
    skipped: list[str] = []

    for label, path in endpoints.items():
        if not path:
            skipped.append(label)
            print(f"Skipped FantasyPros {label}: no endpoint configured.")
            continue

        payload = client.get_json(path)
        write_json(RAW_ROOT / f"{label}.json", payload)
        downloaded[label] = payload

    if not downloaded:
        raise RuntimeError(
            "No FantasyPros endpoint paths are configured. "
            "Add at least one FANTASYPROS_*_PATH value."
        )

    now = datetime.now(UTC)
    manifest = {
        "snapshot_id": now.strftime("%Y-%m-%dT%H-%M-%SZ"),
        "downloaded_at_utc": now.isoformat(),
        "base_url": config.fantasypros_base_url,
        "downloaded_datasets": sorted(downloaded),
        "skipped_datasets": sorted(skipped),
        "methodology_version": config.methodology_version,
        "status": "passed",
    }
    write_json(RAW_ROOT / "manifest.json", manifest)
    return manifest
