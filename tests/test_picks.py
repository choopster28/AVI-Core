import pytest

from avi.valuation.picks import (
    draft_pick_overall_number,
    draft_pick_value,
    first_round_pick_table,
    first_round_pick_value,
    full_draft_pick_table,
)


def test_first_round_pick_values() -> None:
    assert first_round_pick_value(1) == 95.0
    assert first_round_pick_value(16) == 77.0


def test_draft_pick_overall_number() -> None:
    assert draft_pick_overall_number(
        round_number=1,
        slot=1,
    ) == 1

    assert draft_pick_overall_number(
        round_number=2,
        slot=1,
    ) == 17

    assert draft_pick_overall_number(
        round_number=10,
        slot=16,
    ) == 160


def test_draft_pick_value_depreciates_across_rounds() -> None:
    assert draft_pick_value(
        round_number=1,
        slot=1,
    ) == 95.0

    assert draft_pick_value(
        round_number=1,
        slot=2,
    ) == 93.8

    assert draft_pick_value(
        round_number=2,
        slot=1,
    ) == 75.8


def test_draft_pick_value_floors_at_zero() -> None:
    assert draft_pick_value(
        round_number=10,
        slot=16,
    ) == 0.0


def test_pick_tables() -> None:
    first_round = first_round_pick_table()
    full_table = full_draft_pick_table()

    assert len(first_round) == 16
    assert len(full_table) == 160
    assert full_table["1.01"] == 95.0
    assert full_table["10.16"] == 0.0


def test_invalid_round_and_slot() -> None:
    with pytest.raises(ValueError):
        draft_pick_value(
            round_number=0,
            slot=1,
        )

    with pytest.raises(ValueError):
        draft_pick_value(
            round_number=11,
            slot=1,
        )

    with pytest.raises(ValueError):
        draft_pick_value(
            round_number=1,
            slot=0,
        )

    with pytest.raises(ValueError):
        draft_pick_value(
            round_number=1,
            slot=17,
        )