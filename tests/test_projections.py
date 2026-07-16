from avi.valuation.projections import extract_ppr_projection


def test_extract_ppr_projection() -> None:
    record = {
        "stats": {
            "points": 250.0,
            "points_half": 275.0,
            "points_ppr": 300.0,
        }
    }

    assert extract_ppr_projection(record) == 300.0


def test_extract_ppr_projection_missing() -> None:
    assert extract_ppr_projection({}) is None
    assert extract_ppr_projection({"stats": {}}) is None