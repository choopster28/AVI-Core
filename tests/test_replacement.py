from avi.league.loader import LeagueStructure
from avi.valuation.replacement import calculate_replacement_levels


def test_calculate_replacement_levels() -> None:
    league = LeagueStructure(
        league_id="test",
        league_name="Autobots",
        season=2026,
        team_count=2,
        roster_positions=(
            "QB",
            "RB",
            "RB",
            "WR",
            "WR",
            "TE",
            "FLEX",
        ),
        starter_counts={
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 1,
        },
        bench_spots=0,
        reserve_spots=0,
        playoff_teams=0,
        playoff_start_week=0,
        trade_deadline_week=0,
        scoring_settings={},
    )

    projections = {
        "QB": [
            {"projected_ppr_points": 300.0},
            {"projected_ppr_points": 280.0},
        ],
        "RB": [
            {"projected_ppr_points": value}
            for value in (
                250.0,
                240.0,
                230.0,
                220.0,
                210.0,
                200.0,
            )
        ],
        "WR": [
            {"projected_ppr_points": value}
            for value in (
                260.0,
                250.0,
                240.0,
                230.0,
                220.0,
                210.0,
            )
        ],
        "TE": [
            {"projected_ppr_points": value}
            for value in (
                200.0,
                190.0,
                180.0,
                170.0,
            )
        ],
    }

    levels = calculate_replacement_levels(
        projections_by_position=projections,
        league=league,
    )

    assert levels.starter_demand["RB"] == 4
    assert levels.starter_demand["WR"] == 4
    assert levels.starter_demand["TE"] == 2

    assert sum(
        levels.flex_allocations.values()
    ) == 2

    assert levels.replacement_ranks["RB"] >= 4
    assert levels.replacement_ranks["WR"] >= 4
    assert levels.replacement_ranks["TE"] >= 2