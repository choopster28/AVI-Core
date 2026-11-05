from avi.valuation.availability_adjustments import (
    _apply_projection_aware_cap,
    _availability_ceiling,
    _ongoing_injury_risk_points,
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
