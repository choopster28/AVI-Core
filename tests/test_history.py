from avi.sleeper.history import normalize_previous_league_id


def test_normalize_previous_league_id() -> None:
    assert normalize_previous_league_id(None) is None
    assert normalize_previous_league_id("") is None
    assert normalize_previous_league_id("0") is None
    assert normalize_previous_league_id(" 123 ") == "123"
