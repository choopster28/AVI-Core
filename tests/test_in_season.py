from avi.valuation.in_season import (
    _completed_points,
    _fresh_completed_week_available,
    _player_point_components,
)


def test_week_one_does_not_activate_before_completed_games():
    active, completed = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 1},
        max_observed_week=1,
        mapped_records=200,
        current_week_complete=False,
    )
    assert active is False
    assert completed == 0


def test_week_one_activates_as_soon_as_schedule_is_complete():
    active, completed = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 1},
        max_observed_week=1,
        mapped_records=200,
        current_week_complete=True,
    )
    assert active is True
    assert completed == 1


def test_stale_prior_season_points_never_activate_in_week_two():
    active, completed = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 2},
        max_observed_week=18,
        mapped_records=200,
    )
    assert active is False
    assert completed == 1


def test_completed_week_one_activates_during_week_two():
    active, completed = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 2},
        max_observed_week=1,
        mapped_records=200,
    )
    assert active is True
    assert completed == 1


def test_partial_current_week_keeps_prior_completed_weeks_active():
    active, completed = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 6},
        max_observed_week=6,
        mapped_records=200,
        current_week_complete=False,
    )
    assert active is True
    assert completed == 5


def test_current_week_two_activates_when_all_games_are_final():
    active, completed = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 2},
        max_observed_week=2,
        mapped_records=200,
        current_week_complete=True,
    )
    assert active is True
    assert completed == 2


def test_partial_feed_does_not_activate():
    active, _ = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 3},
        max_observed_week=2,
        mapped_records=12,
    )
    assert active is False


def test_completed_points_excludes_partial_current_week():
    trimmed = _completed_points(
        {
            "A": {
                "position": "WR",
                "weeks": {1: 10.0, 2: 20.0, 6: 50.0},
                "raw_points": 26.7,
                "season_points": 80.0,
                "games": 3.0,
                "weekly_ceiling": 50.0,
            }
        },
        completed_through=5,
    )
    assert trimmed["A"]["season_points"] == 30.0
    assert trimmed["A"]["games"] == 2.0
    assert trimmed["A"]["raw_points"] == 15.0
    assert trimmed["A"]["weekly_ceiling"] == 20.0


def test_player_points_reward_relevant_production_without_depth_chart_inflation():
    values = _player_point_components(
        {
            "A": {"position": "RB", "raw_points": 20.0, "season_points": 100.0},
            "B": {"position": "RB", "raw_points": 10.0, "season_points": 50.0},
            "C": {"position": "RB", "raw_points": 0.0, "season_points": 0.0},
        }
    )
    assert values["A"] > values["B"] > values["C"]
    assert values["A"] == 100.0
    assert values["C"] == 0.0
