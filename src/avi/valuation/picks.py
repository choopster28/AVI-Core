from __future__ import annotations


def first_round_pick_value(slot: int) -> float:
    if slot < 1 or slot > 16:
        raise ValueError("First-round slot must be from 1 through 16.")
    return round(95.0 - 1.2 * (slot - 1), 1)


def first_round_pick_table() -> dict[str, float]:
    return {
        f"1.{slot:02d}": first_round_pick_value(slot)
        for slot in range(1, 17)
    }
