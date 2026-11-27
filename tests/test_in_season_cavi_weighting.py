from avi.valuation.calculator import CAVIComponents, calculate_c_avi, in_season_cavi_weights


def test_week_two_uses_reliability_first_mix():
    assert in_season_cavi_weights(2) == {
        "player_points": 0.40,
        "projections": 0.25,
        "league_context": 0.10,
        "public_market": 0.15,
        "elite_upside": 0.10,
    }


def test_week_eight_and_later_use_completed_production_first_mix():
    expected = {
        "player_points": 0.60,
        "projections": 0.15,
        "league_context": 0.10,
        "public_market": 0.05,
        "elite_upside": 0.10,
    }
    for completed_week in range(8, 19):
        assert in_season_cavi_weights(completed_week) == expected


def test_weights_transition_smoothly_and_sum_to_one():
    weights = [in_season_cavi_weights(week) for week in range(0, 19)]
    assert all(abs(sum(row.values()) - 1.0) < 1e-9 for row in weights)
    assert all(weights[i]["player_points"] <= weights[i + 1]["player_points"] for i in range(len(weights) - 1))
    assert all(weights[i]["projections"] >= weights[i + 1]["projections"] for i in range(len(weights) - 1))
    assert all(weights[i]["public_market"] >= weights[i + 1]["public_market"] for i in range(len(weights) - 1))
    assert in_season_cavi_weights(5)["player_points"] == 0.50


def test_verifiable_season_production_can_override_preseason_market():
    # Regression for the class of failure where a WR with materially better
    # completed PPR production trails a historical preseason consensus leader.
    # No player-specific exceptions or manual score adjustments.
    breakout = CAVIComponents(
        player_points=97, projections=89, league_context=78,
        public_market=87, elite_upside=98,
    )
    preseason_favorite = CAVIComponents(
        player_points=77, projections=98, league_context=78,
        public_market=100, elite_upside=91,
    )
    assert calculate_c_avi(breakout, True, completed_weeks=11) > calculate_c_avi(
        preseason_favorite, True, completed_weeks=11
    )


def test_small_sample_still_respects_forward_projection():
    hot_start = CAVIComponents(
        player_points=90, projections=40, league_context=50, public_market=55, elite_upside=60
    )
    established = CAVIComponents(
        player_points=60, projections=95, league_context=50, public_market=92, elite_upside=80
    )
    assert calculate_c_avi(established, True, completed_weeks=2) > calculate_c_avi(
        hot_start, True, completed_weeks=2
    )


def test_late_season_actual_production_is_largest_component():
    baseline = CAVIComponents(50, 50, 50, 50, 50)
    actual_plus_ten = CAVIComponents(60, 50, 50, 50, 50)
    forward_plus_ten = CAVIComponents(50, 60, 50, 50, 50)
    assert calculate_c_avi(actual_plus_ten, True, completed_weeks=11) - calculate_c_avi(
        baseline, True, completed_weeks=11
    ) == 6.0
    assert calculate_c_avi(forward_plus_ten, True, completed_weeks=11) - calculate_c_avi(
        baseline, True, completed_weeks=11
    ) == 1.5


def test_preseason_formula_stays_unchanged():
    example = CAVIComponents(70, 80, 90, 75, 50)
    assert calculate_c_avi(example, False) == 76.5
