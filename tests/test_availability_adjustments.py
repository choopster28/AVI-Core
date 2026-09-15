from avi.valuation.availability_adjustments import (
    _apply_projection_aware_cap,
    _availability_ceiling,
    _expected_missed_weeks,
)


def test_projection_aware_cap_does_not_double_penalize_reduced_cavi():
    # If projections/rankings have already pushed C-AVI below the availability
    # ceiling, the injury layer must not reduce it again.
    final, delta = _apply_projection_aware_cap(68.0, 75.0)
    assert final == 68.0
    assert delta == 0.0


def test_projection_aware_cap_closes_only_residual_overstatement():
    final, delta = _apply_projection_aware_cap(91.0, 75.0)
    assert final == 75.0
    assert delta == -16.0


def test_four_week_ir_in_week_two_sets_75_point_ceiling():
    # Weeks 2-17 = 16 championship-relevant weeks. Four missed weeks leaves
    # 12/16 = 75% maximum remaining championship contribution.
    assert _availability_ceiling(2, 4.0) == 75.0


def test_ir_uses_at_least_four_weeks_when_feed_has_no_timeline():
    state = {
        "sleeper": {"injury_status": "IR", "status": "Active"},
        "fantasypros": {"ir_weeks": []},
    }
    missed, reason = _expected_missed_weeks(state, 2)
    assert missed == 4.0
    assert reason == "injured_reserve"


def test_explicit_ir_weeks_can_extend_beyond_minimum():
    state = {
        "sleeper": {"injury_status": "IR"},
        "fantasypros": {"ir_weeks": [2, 3, 4, 5, 6, 7]},
    }
    missed, reason = _expected_missed_weeks(state, 2)
    assert missed == 6.0
    assert reason == "injured_reserve"


def test_questionable_uses_probability_without_large_hard_penalty():
    state = {
        "fantasypros": {
            "status": "Questionable",
            "probability_of_playing": 80,
        }
    }
    missed, reason = _expected_missed_weeks(state, 2)
    assert round(missed, 2) == 0.20
    assert reason == "questionable"


def test_season_ending_comment_uses_entire_remaining_horizon():
    state = {
        "fantasypros": {
            "status": "IR",
            "comment": "Expected to miss the remainder of the season.",
        }
    }
    missed, reason = _expected_missed_weeks(state, 10)
    assert missed == 8.0
    assert reason == "season_ending"
