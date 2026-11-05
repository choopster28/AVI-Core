from __future__ import annotations

from dataclasses import dataclass

from avi.valuation.scaling import clamp


@dataclass(frozen=True)
class CAVIComponents:
    player_points: float
    projections: float
    league_context: float
    public_market: float
    elite_upside: float


@dataclass(frozen=True)
class DAVIComponents:
    dynasty_market: float | None
    age_career_horizon: float | None
    long_term_security: float | None
    position_liquidity: float | None
    current_c_avi: float | None
    health_outlook: float | None
    long_term_ceiling: float | None


DAVI_WEIGHTS: dict[str, float] = {
    "dynasty_market": 0.35,
    "age_career_horizon": 0.20,
    "long_term_security": 0.15,
    "position_liquidity": 0.10,
    "current_c_avi": 0.10,
    "health_outlook": 0.05,
    "long_term_ceiling": 0.05,
}


def in_season_cavi_weights(completed_weeks: int = 0) -> dict[str, float]:
    """The verified in-season 40% production policy.

    Actual PPR output gets the largest single component, but does not
    displace forward projection and market information halfway through the
    season. This is a uniform model-wide weight, not a player exception.
    Individual observed-game reliability and injury availability remain
    separate adjustments in the in-season valuation pipeline.
    """
    return {
        "player_points": 0.40,
        "projections": 0.25,
        "league_context": 0.10,
        "public_market": 0.15,
        "elite_upside": 0.10,
    }


def calculate_c_avi(
    components: CAVIComponents,
    player_points_active: bool,
    *,
    completed_weeks: int = 0,
) -> float:
    if player_points_active:
        weights = in_season_cavi_weights(completed_weeks)
        value = (
            weights["player_points"] * components.player_points
            + weights["projections"] * components.projections
            + weights["league_context"] * components.league_context
            + weights["public_market"] * components.public_market
            + weights["elite_upside"] * components.elite_upside
        )
    else:
        value = (
            0.50 * components.projections
            + 0.10 * components.league_context
            + 0.30 * components.public_market
            + 0.10 * components.elite_upside
        )

    return round(clamp(value), 1)


def calculate_d_avi(
    components: DAVIComponents,
) -> float:
    """
    Calculate D-AVI from independent verified dynasty components.

    Optional inputs that are unavailable are not assigned invented
    neutral values. Their weights are redistributed proportionally
    across the verified components that are present.
    """
    values: dict[str, float | None] = {
        "dynasty_market": components.dynasty_market,
        "age_career_horizon": components.age_career_horizon,
        "long_term_security": components.long_term_security,
        "position_liquidity": components.position_liquidity,
        "current_c_avi": components.current_c_avi,
        "health_outlook": components.health_outlook,
        "long_term_ceiling": components.long_term_ceiling,
    }

    available = {
        name: clamp(float(value))
        for name, value in values.items()
        if value is not None
    }

    if not available:
        raise ValueError(
            "At least one verified D-AVI component is required."
        )

    available_weight = sum(
        DAVI_WEIGHTS[name]
        for name in available
    )

    weighted_value = sum(
        DAVI_WEIGHTS[name] * value
        for name, value in available.items()
    )

    return round(
        clamp(weighted_value / available_weight),
        1,
    )
