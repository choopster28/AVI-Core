from avi.trades.ledger import build_completed_trade_ledger


def test_trade_ledger_filters_and_deduplicates() -> None:
    trade = {
        "transaction_id": "abc",
        "type": "trade",
        "status": "complete",
        "created": 1,
    }
    waiver = {
        "transaction_id": "def",
        "type": "waiver",
        "status": "complete",
        "created": 2,
    }
    assert build_completed_trade_ledger([trade, trade, waiver]) == [trade]
