from avi.valuation.availability_adjustments import (
    _apply_projection_aware_cap,
    _availability_ceiling,
    _expected_missed_weeks,
    _availability_adjusted_cavi,
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


def test_questionable_active_starter_keeps_risk_but_no_fractional_hard_cap():
    # Generic regression for a premium player with 0.2 expected misses in
    # a six-game fantasy championship horizon. A 96.7 hard cap would
    # unnecessarily erase a genuine current-production lead.
    final, delta = _availability_adjusted_cavi(
        base_cavi=99.2,
        ceiling=96.7,
        ongoing_risk=1.5,
        reason_code="questionable",
        expected_missed_weeks=0.2,
    )
    assert final == 97.7
    assert delta == -1.5


def test_likely_to_miss_doubtful_player_keeps_hard_availability_ceiling():
    final, delta = _availability_adjusted_cavi(
        base_cavi=98.0, ceiling=87.5,
        ongoing_risk=2.5, reason_code="doubtful",
        expected_missed_weeks=0.75,
    )
    assert final == 87.5
    assert delta == -10.5


def test_confirmed_out_still_has_hard_ceiling():
    final, _ = _availability_adjusted_cavi(
        base_cavi=98.0, ceiling=83.3,
        ongoing_risk=3.0, reason_code="out",
        expected_missed_weeks=1.0,
    )
    assert final == 83.3
