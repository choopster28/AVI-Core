from __future__ import annotations

from typing import Any


def completed_trade_ledger(
    transactions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}

    for transaction in transactions:
        if transaction.get("type") != "trade":
            continue
        if transaction.get("status") != "complete":
            continue

        transaction_id = str(transaction.get("transaction_id", "")).strip()
        if not transaction_id:
            raise RuntimeError("Completed trade missing transaction_id.")

        existing = by_id.get(transaction_id)
        if existing is not None and existing != transaction:
            raise RuntimeError(f"Conflicting trade records: {transaction_id}")
        by_id[transaction_id] = transaction

    return sorted(
        by_id.values(),
        key=lambda row: (row.get("created", 0), row.get("transaction_id", "")),
    )
