from avi.valuation.picks import first_round_pick_value


def test_pick_curve() -> None:
    assert first_round_pick_value(1) == 95.0
    assert first_round_pick_value(2) == 93.8
    assert first_round_pick_value(3) == 92.6
    assert first_round_pick_value(16) == 77.0
