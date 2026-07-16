from avi.trades.ledger import completed_trade_ledger


def test_trade_filter_and_dedupe() -> None:
    trade = {
        "transaction_id": "x",
        "type": "trade",
        "status": "complete",
        "created": 1,
    }
    waiver = {
        "transaction_id": "y",
        "type": "waiver",
        "status": "complete",
        "created": 2,
    }
    assert completed_trade_ledger([trade, trade, waiver]) == [trade]
