import pytest

from avi.calculate_avi import (
    calculate_age_career_horizon,
    calculate_position_liquidity,
)
from avi.valuation.calculator import (
    DAVIComponents,
    calculate_d_avi,
)


def test_d_avi_uses_revised_components() -> None:
    value = calculate_d_avi(
        DAVIComponents(
            dynasty_market=95.0,
            age_career_horizon=99.0,
            long_term_security=90.0,
            position_liquidity=92.0,
            current_c_avi=88.0,
            health_outlook=85.0,
            long_term_ceiling=96.0,
        )
    )

    assert value == 93.6


def test_d_avi_redistributes_missing_weights() -> None:
    value = calculate_d_avi(
        DAVIComponents(
            dynasty_market=90.0,
            age_career_horizon=80.0,
            long_term_security=None,
            position_liquidity=70.0,
            current_c_avi=60.0,
            health_outlook=None,
            long_term_ceiling=50.0,
        )
    )

    assert value == 78.8


def test_d_avi_requires_verified_input() -> None:
    with pytest.raises(ValueError):
        calculate_d_avi(
            DAVIComponents(
                dynasty_market=None,
                age_career_horizon=None,
                long_term_security=None,
                position_liquidity=None,
                current_c_avi=None,
                health_outlook=None,
                long_term_ceiling=None,
            )
        )


def test_wr_age_curve_is_not_flat() -> None:
    assert calculate_age_career_horizon(
        22.0,
        "WR",
    ) == 99.0

    assert calculate_age_career_horizon(
        26.0,
        "WR",
    ) == 96.0

    assert calculate_age_career_horizon(
        30.0,
        "WR",
    ) == 76.0


def test_rb_age_curve_declines_faster() -> None:
    assert calculate_age_career_horizon(
        22.0,
        "RB",
    ) == 100.0

    assert calculate_age_career_horizon(
        27.0,
        "RB",
    ) == 72.0

    assert calculate_age_career_horizon(
        30.0,
        "RB",
    ) == 31.0


def test_one_qb_liquidity_is_capped() -> None:
    value = calculate_position_liquidity(
        position="QB",
        team_count=16,
        starter_demand={
            "QB": 16,
        },
        flex_allocations={},
    )

    assert value == 60.0


def test_flex_positions_receive_liquidity_credit() -> None:
    value = calculate_position_liquidity(
        position="WR",
        team_count=16,
        starter_demand={
            "WR": 32,
        },
        flex_allocations={
            "WR": 16,
        },
    )

    assert value == 100.0
