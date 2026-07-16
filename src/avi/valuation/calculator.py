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
    dynasty_market: float
    current_c_avi: float
    age_lifecycle: float
    role_stability: float
    prior_d_avi: float
    health: float
    long_term_ceiling: float


def calculate_c_avi(
    components: CAVIComponents,
    player_points_active: bool,
) -> float:
    if player_points_active:
        value = (
            0.10 * components.player_points
            + 0.40 * components.projections
            + 0.10 * components.league_context
            + 0.30 * components.public_market
            + 0.10 * components.elite_upside
        )
    else:
        value = (
            0.50 * components.projections
            + 0.10 * components.league_context
            + 0.30 * components.public_market
            + 0.10 * components.elite_upside
        )
    return round(clamp(value), 1)


def calculate_d_avi(components: DAVIComponents) -> float:
    value = (
        0.35 * components.dynasty_market
        + 0.20 * components.current_c_avi
        + 0.15 * components.age_lifecycle
        + 0.10 * components.role_stability
        + 0.10 * components.prior_d_avi
        + 0.05 * components.health
        + 0.05 * components.long_term_ceiling
    )
    return round(clamp(value), 1)
