from __future__ import annotations

import generate_weekly_executive_summary as generator

# These entries are a reversed/administrative transaction chain and must never
# appear in franchise executive summaries or rival-watch sections.
BLACKLISTED_TRANSACTION_IDS = {
    "1384427332722233344",  # related pick-only reversal
    "1384401342625226752",  # Mayfield/Brissett plus related picks
    "1384338064138043392",  # Mayfield/Brissett reversal
}

_original_latest_trade = generator.latest_trade


def latest_non_blacklisted_trade(team: dict, ledger: list[dict], now):
    filtered_ledger = [
        trade
        for trade in ledger
        if trade.get("transaction_id") not in BLACKLISTED_TRANSACTION_IDS
    ]
    return _original_latest_trade(team, filtered_ledger, now)


generator.latest_trade = latest_non_blacklisted_trade


if __name__ == "__main__":
    generator.main()
