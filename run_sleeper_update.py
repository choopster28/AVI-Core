from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_DIRECTORY = PROJECT_ROOT / "src"

sys.path.insert(
    0,
    str(SOURCE_DIRECTORY),
)

from avi.config import load_config
from avi.sleeper.downloader import (
    download_sleeper_snapshot,
)


def main() -> None:
    config = load_config()
    download_sleeper_snapshot(config)


if __name__ == "__main__":
    main()