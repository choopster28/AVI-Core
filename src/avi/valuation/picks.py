from __future__ import annotations


TEAMS_PER_ROUND = 16
MAX_DRAFT_ROUNDS = 10

STARTING_PICK_VALUE = 91.0
EARLY_PICK_DEPRECIATION = 1.2
MID_PICK_DEPRECIATION = 1.7
LATE_PICK_DEPRECIATION = 2.0
MINIMUM_PICK_VALUE = 0.0


def draft_pick_overall_number(
    *,
    round_number: int,
    slot: int,
) -> int:
    if round_number < 1 or round_number > MAX_DRAFT_ROUNDS:
        raise ValueError(
            f"Round must be from 1 through {MAX_DRAFT_ROUNDS}."
        )

    if slot < 1 or slot > TEAMS_PER_ROUND:
        raise ValueError(
            f"Slot must be from 1 through {TEAMS_PER_ROUND}."
        )

    return (
        (round_number - 1) * TEAMS_PER_ROUND
        + slot
    )


def draft_pick_value(
    *,
    round_number: int,
    slot: int,
) -> float:
    overall_number = draft_pick_overall_number(
        round_number=round_number,
        slot=slot,
    )

    if overall_number <= 4:
        value = (
            STARTING_PICK_VALUE
            - EARLY_PICK_DEPRECIATION
            * (overall_number - 1)
        )
    elif overall_number <= 11:
        value_at_1_04 = (
            STARTING_PICK_VALUE
            - EARLY_PICK_DEPRECIATION * 3
        )

        value = (
            value_at_1_04
            - MID_PICK_DEPRECIATION
            * (overall_number - 4)
        )
    else:
        value_at_1_04 = (
            STARTING_PICK_VALUE
            - EARLY_PICK_DEPRECIATION * 3
        )

        value_at_1_11 = (
            value_at_1_04
            - MID_PICK_DEPRECIATION * 7
        )

        value = (
            value_at_1_11
            - LATE_PICK_DEPRECIATION
            * (overall_number - 11)
        )

    return round(
        max(
            MINIMUM_PICK_VALUE,
            value,
        ),
        1,
    )


def first_round_pick_value(
    slot: int,
) -> float:
    return draft_pick_value(
        round_number=1,
        slot=slot,
    )


def first_round_pick_table() -> dict[str, float]:
    return {
        f"1.{slot:02d}": first_round_pick_value(slot)
        for slot in range(
            1,
            TEAMS_PER_ROUND + 1,
        )
    }


def full_draft_pick_table() -> dict[str, float]:
    return {
        f"{round_number}.{slot:02d}": (
            draft_pick_value(
                round_number=round_number,
                slot=slot,
            )
        )
        for round_number in range(
            1,
            MAX_DRAFT_ROUNDS + 1,
        )
        for slot in range(
            1,
            TEAMS_PER_ROUND + 1,
        )
    }
