import pytest

from avi.valuation.picks import (
    draft_pick_overall_number,
    draft_pick_value,
    first_round_pick_table,
    first_round_pick_value,
    full_draft_pick_table,
)


def test_first_round_pick_values() -> None:
    assert first_round_pick_value(1) == 91.0
    assert first_round_pick_value(2) == 89.8
    assert first_round_pick_value(4) == 87.4
    assert first_round_pick_value(5) == 85.7
    assert first_round_pick_value(11) == 75.5
    assert first_round_pick_value(12) == 73.5
    assert first_round_pick_value(16) == 65.5


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


def test_draft_pick_value_uses_segmented_depreciation_curve() -> None:
    assert draft_pick_value(
        round_number=1,
        slot=1,
    ) == 91.0

    assert draft_pick_value(
        round_number=1,
        slot=2,
    ) == 89.8

    assert draft_pick_value(
        round_number=1,
        slot=4,
    ) == 87.4

    assert draft_pick_value(
        round_number=1,
        slot=5,
    ) == 85.7

    assert draft_pick_value(
        round_number=1,
        slot=11,
    ) == 75.5

    assert draft_pick_value(
        round_number=1,
        slot=12,
    ) == 73.5


def test_draft_pick_value_continues_depreciating_across_rounds() -> None:
    assert draft_pick_value(
        round_number=1,
        slot=16,
    ) == 65.5

    assert draft_pick_value(
        round_number=2,
        slot=1,
    ) == 63.5

    assert draft_pick_value(
        round_number=2,
        slot=2,
    ) == 61.5


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

    assert first_round["1.01"] == 91.0
    assert first_round["1.04"] == 87.4
    assert first_round["1.05"] == 85.7
    assert first_round["1.11"] == 75.5
    assert first_round["1.12"] == 73.5
    assert first_round["1.16"] == 65.5

    assert full_table["1.01"] == 91.0
    assert full_table["1.16"] == 65.5
    assert full_table["2.01"] == 63.5
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
