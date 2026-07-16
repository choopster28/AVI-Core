from __future__ import annotations

from typing import Any


METHODOLOGY_VERSION = "current-approved"


def calculate_player_avi(player_inputs: dict[str, Any]) -> dict[str, float]:
    """
    Port the exact currently approved C-AVI and D-AVI calculations here.

    This function intentionally fails instead of estimating or changing the
    existing methodology. Replace only after the present spreadsheet/script/
    written formula has been supplied and verified against existing AVI files.
    """
    raise NotImplementedError(
        "Official C-AVI and D-AVI formulas have not yet been ported. "
        "AVI Core will not fabricate methodology."
    )
