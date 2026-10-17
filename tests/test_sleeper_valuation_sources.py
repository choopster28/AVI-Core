from avi.sleeper.valuation_sources import _extract_map, _points, _valid_points
from avi.valuation.availability_adjustments import _status_source, _status_text


def test_sleeper_valid_ppr_value():
    assert _points({"stats": {"pts_ppr": 24.3}}) == 24.3
    assert _points({"pts_ppr": 0}) == 0
    assert _points({"stats": {"pts_std": 9}}) is None


def test_sleeper_rejects_invalid_scoring_inputs():
    assert _valid_points(None) is None
    assert _valid_points("n/a") is None
    assert _valid_points(9999) is None


def test_sleeper_normalizes_list_and_dictionary_payloads():
    assert _extract_map({"123": {"stats": {"pts_ppr": 1}}})["123"]["stats"]["pts_ppr"] == 1
    assert _extract_map([{"player_id": "456", "pts_ppr": 0}])["456"]["pts_ppr"] == 0


def test_injury_designation_prefers_actionable_sleeper():
    state = {
        "sleeper": {"injury_status": "Questionable", "status": "Active"},
        "fantasypros": {"status": "IR"},
    }
    assert _status_source(state) == "sleeper"
    assert "questionable" in _status_text(state)
    assert "ir" not in _status_text(state)


def test_injury_designation_falls_back_to_fantasypros():
    state = {
        "sleeper": {"injury_status": None, "status": "Active"},
        "fantasypros": {"status": "Out"},
    }
    assert _status_source(state) == "fantasypros"
    assert _status_text(state) == "out"
