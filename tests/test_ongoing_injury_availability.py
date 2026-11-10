from avi.valuation.availability_adjustments import (
    _apply_projection_aware_cap,
    _availability_ceiling,
    _ongoing_injury_risk_points,
    _expected_missed_weeks,
    _comment_text,
)


def _player(games: int, completed: int = 8):
    return {"in_season_player_points": {"games": games, "completed_through_week": completed}}


def test_recurring_injury_with_missed_games_lowers_championship_value():
    # Week-8 observed availability sample, not a manually named player override.
    risk, missed = _ongoing_injury_risk_points(_player(4), "questionable")
    assert missed == 3  # one possible bye exempted
    assert risk == 6.0
    ceiling = _availability_ceiling(9, 0.2)
    adjusted, delta = _apply_projection_aware_cap(79.4 - risk, ceiling)
    assert adjusted == 73.4
    assert delta == 0.0


def test_cleared_player_has_no_historical_missed_games_penalty():
    for status in ("healthy_or_no_actionable_designation", "season_complete", "probable"):
        assert _ongoing_injury_risk_points(_player(4), status) == (0.0, 0)


def test_no_bye_penalty_or_arbitrary_risk_without_sample():
    assert _ongoing_injury_risk_points(_player(7), "questionable") == (1.5, 0)
    assert _ongoing_injury_risk_points({}, "questionable") == (0.0, 0)


def test_risk_is_bounded_and_season_ending_availability_remains_zero():
    risk, _ = _ongoing_injury_risk_points(_player(1, 14), "injured_reserve")
    assert risk <= 9.0
    assert _apply_projection_aware_cap(90 - risk, 0.0)[0] == 0.0


def test_generic_sleeper_out_does_not_hide_confirmed_season_ending_report():
    state = {
        "sleeper": {"injury_status": "Out", "status": "IR"},
        "fantasypros": {"status": "Out", "comment": "Will miss the rest of the season"},
    }
    assert "rest of the season" in _comment_text(state)
    missed, reason = _expected_missed_weeks(state, 10)
    assert (missed, reason) == (8.0, "season_ending")
    assert _availability_ceiling(10, missed) == 0.0


def test_sleeper_injury_notes_can_independently_confirm_season_ending():
    state = {
        "sleeper": {
            "injury_status": "IR",
            "status": "IR",
            "injury_notes": "Ruled out for the season",
        },
    }
    missed, reason = _expected_missed_weeks(state, 11)
    assert reason == "season_ending"
    assert _availability_ceiling(11, missed) == 0.0


def test_temporary_ir_is_not_assumed_season_ending():
    state = {"sleeper": {"injury_status": "IR", "status": "IR"}}
    missed, reason = _expected_missed_weeks(state, 10)
    assert reason == "injured_reserve"
    assert missed == 4.0
    assert _availability_ceiling(10, missed) > 0.0


def test_temporary_out_does_not_zero_cavi():
    state = {"sleeper": {"injury_status": "Out", "status": "Active"}}
    missed, reason = _expected_missed_weeks(state, 10)
    assert (missed, reason) == (1.0, "out")


def test_confirmed_season_ending_can_be_reversed_when_cleared():
    state = {"sleeper": {"injury_status": None, "status": "Active"}}
    missed, reason = _expected_missed_weeks(state, 10)
    assert (missed, reason) == (0.0, "healthy_or_no_actionable_designation")


def test_sourced_confirmation_overrides_generic_injury_feed_without_player_exceptions():
    state = {
        "sleeper": {"injury_status": "Out", "status": "IR"},
        "fantasypros": {"status": "OUT", "comment": "injured"},
        "season_ending_confirmation": {
            "season_ending": True,
            "source_url": "https://www.nfl.com/news/example",
            "confirmed_on": "2026-09-28",
        },
    }
    missed, reason = _expected_missed_weeks(state, 10)
    assert (missed, reason) == (8.0, "season_ending")
    assert _apply_projection_aware_cap(50.0, _availability_ceiling(10, missed))[0] == 0.0


def test_sourced_confirmation_cannot_zero_a_cleared_player():
    state = {
        "sleeper": {"injury_status": None, "status": "Active"},
        "fantasypros": {"status": "", "comment": ""},
        "season_ending_confirmation": {"season_ending": True},
    }
    missed, reason = _expected_missed_weeks(state, 10)
    assert (missed, reason) == (0.0, "healthy_or_no_actionable_designation")
