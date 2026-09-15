from avi.reports.lineup import build_championship_lineup


def test_build_championship_lineup() -> None:
    players = [
        {
            "avi_id": "qb-1",
            "canonical_name": "QB One",
            "position": "QB",
            "c_avi": 90.0,
        },
        {
            "avi_id": "rb-1",
            "canonical_name": "RB One",
            "position": "RB",
            "c_avi": 95.0,
        },
        {
            "avi_id": "rb-2",
            "canonical_name": "RB Two",
            "position": "RB",
            "c_avi": 85.0,
        },
        {
            "avi_id": "rb-3",
            "canonical_name": "RB Three",
            "position": "RB",
            "c_avi": 70.0,
        },
        {
            "avi_id": "wr-1",
            "canonical_name": "WR One",
            "position": "WR",
            "c_avi": 92.0,
        },
        {
            "avi_id": "wr-2",
            "canonical_name": "WR Two",
            "position": "WR",
            "c_avi": 82.0,
        },
        {
            "avi_id": "wr-3",
            "canonical_name": "WR Three",
            "position": "WR",
            "c_avi": 75.0,
        },
        {
            "avi_id": "te-1",
            "canonical_name": "TE One",
            "position": "TE",
            "c_avi": 88.0,
        },
        {
            "avi_id": "k-1",
            "canonical_name": "Kicker",
            "position": "K",
            "c_avi": 100.0,
        },
    ]

    lineup = build_championship_lineup(
        players=players,
        starter_counts={
            "QB": 1,
            "RB": 2,
            "WR": 2,
            "TE": 1,
            "FLEX": 2,
            "K": 1,
        },
    )

    assert len(lineup.slots) == 8

    selected_names = {
        slot.player["canonical_name"]
        for slot in lineup.slots
    }

    assert "Kicker" not in selected_names
    assert "RB Three" in selected_names
    assert "WR Three" in selected_names

    assert lineup.c_avi_sum == 677.0
    assert lineup.c_avi_average == 84.62


def test_inactive_players_are_excluded() -> None:
    players = [
        {
            "avi_id": "qb-1",
            "canonical_name": "Active QB",
            "position": "QB",
            "c_avi": 80.0,
        },
        {
            "avi_id": "qb-2",
            "canonical_name": "Inactive QB",
            "position": "QB",
            "c_avi": 99.0,
            "status": "inactive",
        },
    ]

    lineup = build_championship_lineup(
        players=players,
        starter_counts={
            "QB": 1,
        },
    )

    assert len(lineup.slots) == 1
    assert (
        lineup.slots[0].player["canonical_name"]
        == "Active QB"
    )


def test_injured_reserve_player_is_not_a_projected_starter() -> None:
    players = [
        {
            "avi_id": "wr-ir",
            "canonical_name": "IR Star",
            "position": "WR",
            "c_avi": 90.0,
            "c_avi_availability_adjustment": {
                "reason_code": "injured_reserve",
                "status": "ir inactive",
                "adjusted_c_avi": 75.0,
            },
        },
        {
            "avi_id": "wr-healthy",
            "canonical_name": "Healthy WR",
            "position": "WR",
            "c_avi": 68.0,
        },
    ]

    lineup = build_championship_lineup(
        players=players,
        starter_counts={
            "WR": 1,
        },
    )

    assert len(lineup.slots) == 1
    assert lineup.slots[0].player["canonical_name"] == "Healthy WR"


def test_questionable_player_remains_projected_lineup_eligible() -> None:
    players = [
        {
            "avi_id": "rb-q",
            "canonical_name": "Questionable RB",
            "position": "RB",
            "c_avi": 80.0,
            "c_avi_availability_adjustment": {
                "reason_code": "questionable",
                "status": "questionable",
                "adjusted_c_avi": 80.0,
            },
        },
        {
            "avi_id": "rb-2",
            "canonical_name": "Healthy RB",
            "position": "RB",
            "c_avi": 70.0,
        },
    ]

    lineup = build_championship_lineup(
        players=players,
        starter_counts={
            "RB": 1,
        },
    )

    assert lineup.slots[0].player["canonical_name"] == "Questionable RB"