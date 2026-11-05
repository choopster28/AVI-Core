from avi.valuation.calculator import CAVIComponents, calculate_c_avi, in_season_cavi_weights


def test_in_season_production_weight_is_40_percent_at_every_verified_week():
    weights = {
        "player_points": 0.40,
        "projections": 0.25,
        "league_context": 0.10,
        "public_market": 0.15,
        "elite_upside": 0.10,
    }
    for completed_week in range(0, 19):
        assert in_season_cavi_weights(completed_week) == weights
        assert abs(sum(in_season_cavi_weights(completed_week).values()) - 1.0) < 1e-9


def test_projection_and_market_protect_future_championship_contribution():
    hot_start = CAVIComponents(
        player_points=90,
        projections=40,
        league_context=50,
        public_market=55,
        elite_upside=60,
    )
    future_starter = CAVIComponents(
        player_points=60,
        projections=95,
        league_context=50,
        public_market=92,
        elite_upside=80,
    )
    assert calculate_c_avi(future_starter, True, completed_weeks=8) > calculate_c_avi(
        hot_start, True, completed_weeks=8
    )


def test_actual_production_still_has_largest_single_weight():
    baseline = CAVIComponents(50, 50, 50, 50, 50)
    actual_plus_ten = CAVIComponents(60, 50, 50, 50, 50)
    forward_plus_ten = CAVIComponents(50, 60, 50, 50, 50)
    assert calculate_c_avi(actual_plus_ten, True, completed_weeks=8) - calculate_c_avi(
        baseline, True, completed_weeks=8
    ) == 4.0
    assert calculate_c_avi(forward_plus_ten, True, completed_weeks=8) - calculate_c_avi(
        baseline, True, completed_weeks=8
    ) == 2.5


def test_preseason_formula_stays_unchanged():
    example = CAVIComponents(70, 80, 90, 75, 50)
    assert calculate_c_avi(example, False) == 76.5
