from avi.valuation.calculator import (
    CAVIComponents,
    DAVIComponents,
    calculate_c_avi,
    calculate_d_avi,
)


def test_preseason_points_do_not_affect_c_avi() -> None:
    low_points = CAVIComponents(0, 80, 80, 80, 80)
    high_points = CAVIComponents(100, 80, 80, 80, 80)
    assert calculate_c_avi(low_points, False) == 80.0
    assert calculate_c_avi(high_points, False) == 80.0


def test_in_season_points_affect_c_avi() -> None:
    low_points = CAVIComponents(0, 80, 80, 80, 80)
    high_points = CAVIComponents(100, 80, 80, 80, 80)
    assert calculate_c_avi(low_points, True) == 60.0
    assert calculate_c_avi(high_points, True) == 85.0


def test_d_avi_weights() -> None:
    components = DAVIComponents(80, 80, 80, 80, 80, 80, 80)
    assert calculate_d_avi(components) == 80.0


from avi.calculate_avi import build_context_score, build_market_score, build_upside_score


def test_public_market_prioritizes_redraft_for_cavi() -> None:
    assert build_market_score(dynasty_score=100, redraft_score=50) == 60.0
    assert build_market_score(dynasty_score=50, redraft_score=100) == 90.0


def test_league_context_is_independent_position_liquidity() -> None:
    assert build_context_score(62.0) == 62.0
    assert build_context_score(120.0) == 100.0


def test_preseason_elite_upside_rewards_only_top_tail_redraft() -> None:
    assert build_upside_score(redraft_score=70.0, market_score=70.0) == 0.0
    assert build_upside_score(redraft_score=85.0, market_score=85.0) == 50.0
    assert build_upside_score(redraft_score=100.0, market_score=100.0) == 100.0
