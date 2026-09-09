from avi.valuation.in_season import _fresh_completed_week_available, _player_point_components


def test_week_one_does_not_activate_before_completed_games():
    active, completed = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 1},
        max_observed_week=18,
        mapped_records=200,
    )
    assert active is False
    assert completed == 0


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


def test_partial_feed_does_not_activate():
    active, _ = _fresh_completed_week_available(
        {"season": "2026", "season_type": "regular", "week": 3},
        max_observed_week=2,
        mapped_records=12,
    )
    assert active is False


def test_player_points_are_scaled_within_position():
    values = _player_point_components(
        {
            "A": {"position": "RB", "raw_points": 20.0},
            "B": {"position": "RB", "raw_points": 10.0},
            "C": {"position": "RB", "raw_points": 0.0},
        }
    )
    assert values["A"] > values["B"] > values["C"]
