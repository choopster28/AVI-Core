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
    assert calculate_c_avi(low_points, True) == 72.0
    assert calculate_c_avi(high_points, True) == 82.0


def test_d_avi_weights() -> None:
    components = DAVIComponents(80, 80, 80, 80, 80, 80, 80)
    assert calculate_d_avi(components) == 80.0
