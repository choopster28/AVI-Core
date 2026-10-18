import pytest

from avi.reports.power_rankings_2026 import rank_2026_teams


def team(roster_id=1, wins=6, losses=4, ties=0, starters=80, roster=50):
    return dict(roster_id=roster_id, team_name=f"Team {roster_id}",
                wins=wins, losses=losses, ties=ties,
                projected_starters_c_avi=starters,
                entire_roster_c_avi=roster)


def test_exact_weights():
    result = rank_2026_teams([team()])[0]
    assert result["record_score"] == 60
    assert result["power_score"] == 65.6


def test_full_roster_changes_score_even_with_same_starters():
    results = rank_2026_teams([team(1), team(2, roster=100)])
    assert results[0]["roster_id"] == 2
    assert results[0]["power_score"] - results[1]["power_score"] == pytest.approx(4)


def test_ties_count_as_half_win():
    result = rank_2026_teams([team(wins=4, losses=4, ties=2)])[0]
    assert result["record_score"] == 50


@pytest.mark.parametrize("changes", [
    {"projected_starters_c_avi": None},
    {"entire_roster_c_avi": None},
    {"wins": 0, "losses": 0, "ties": 0},
    {"wins": -1},
])
def test_unverified_or_invalid_data_fails_closed(changes):
    with pytest.raises(ValueError):
        rank_2026_teams([{**team(), **changes}])
