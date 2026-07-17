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