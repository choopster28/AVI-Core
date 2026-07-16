from __future__ import annotations

from typing import Any


def is_completed_trade(transaction: dict[str, Any]) -> bool:
    return (
        transaction.get("type") == "trade"
        and transaction.get("status") == "complete"
    )


def build_completed_trade_ledger(
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    trades_by_id: dict[str, dict[str, Any]] = {}

    for transaction in transactions:
        if not is_completed_trade(transaction):
            continue

        transaction_id = str(transaction.get("transaction_id", "")).strip()
        if not transaction_id:
            raise RuntimeError("A completed trade is missing transaction_id.")

        existing = trades_by_id.get(transaction_id)
        if existing is not None and existing != transaction:
            raise RuntimeError(
                f"Conflicting completed-trade records found for {transaction_id}."
            )
        trades_by_id[transaction_id] = transaction

    trades = list(trades_by_id.values())
    trades.sort(
        key=lambda trade: (
            trade.get("created", 0),
            trade.get("transaction_id", ""),
        )
    )
    return trades
