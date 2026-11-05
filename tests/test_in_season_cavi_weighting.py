from avi.valuation.calculator import CAVIComponents, calculate_c_avi, in_season_cavi_weights


def test_in_season_weights_shift_to_observed_results():
    opening = in_season_cavi_weights(2)
    mature = in_season_cavi_weights(8)
    late = in_season_cavi_weights(13)
    assert opening == {
        "player_points": 0.40,
        "projections": 0.25,
        "league_context": 0.10,
        "public_market": 0.15,
        "elite_upside": 0.10,
    }
    assert mature == late
    assert mature["player_points"] == 0.60
    assert mature["projections"] == 0.15
    assert mature["public_market"] == 0.05
    for week in range(0, 19):
        assert abs(sum(in_season_cavi_weights(week).values()) - 1.0) < 1e-9


def test_in_season_performance_overtakes_stale_preseason_market_assumptions():
    # Real Week 8 component snapshots: Chase Brown's prior expectations were
    # stronger, but Chuba Hubbard had materially more verified PPR production.
    # This is a regression example, NOT a player-specific override.
    chase = CAVIComponents(
        player_points=59.5,
        projections=96.71043521266073,
        league_context=91.2,
        public_market=96.40028840954156,
        elite_upside=33,
    )
    chuba = CAVIComponents(
        player_points=86.4,
        projections=43.616783562629266,
        league_context=91.2,
        public_market=83.50117166376255,
        elite_upside=61.7,
    )
    chase_score = calculate_c_avi(chase, True, completed_weeks=8)
    chuba_score = calculate_c_avi(chuba, True, completed_weeks=8)
    assert chase_score == 67.4
    assert chuba_score == 77.8
    assert chuba_score - chase_score > 10


def test_preseason_formula_stays_unchanged():
    example = CAVIComponents(70, 80, 90, 75, 50)
    assert calculate_c_avi(example, False) == 77.5
