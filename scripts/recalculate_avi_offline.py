"""Recalculate AVI solely from committed data files (no source API calls)."""
from avi.valuation.in_season import apply_in_season_transition
from avi.valuation.availability_adjustments import (
    apply_injury_availability_adjustments,
    recalculate_davi_from_final_cavi,
)
from avi.valuation.risk_adjustments import apply_cavi_risk_adjustments
from avi.reports.team_profiles import build_team_profiles
from avi.reports.player_lookup import build_player_lookup

def main() -> None:
    print("Recomputing C-AVI with cached, verified completed-week stats...")
    transition = apply_in_season_transition(offline=True)
    if transition.get("status") != "passed" and transition.get("status") != "active":
        raise RuntimeError(f"Offline in-season AVI calculation did not run: {transition}")
    print("In-season result:", transition)
    print("Cached injury availability:", apply_injury_availability_adjustments())
    print("Current manual risk registry:", apply_cavi_risk_adjustments())
    print("Recalculate D-AVI:", recalculate_davi_from_final_cavi())
    print("Rebuild team profiles:", build_team_profiles())
    print("Rebuild player lookup:", build_player_lookup())

if __name__ == "__main__":
    main()
