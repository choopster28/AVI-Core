from pathlib import Path

path = Path("generate_weekly_executive_summary_filtered.py")
source = path.read_text(encoding="utf-8")

anchor = '''def rival_snapshot_with_latest_activity(
'''
helper = '''def latest_verified_trade(
    team: dict[str, Any],
    ledger: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any] | None:
    """Return the newest verified trade, independent of newer non-trade activity."""
    cutoff_ms = int(
        (now.astimezone(generator.UTC) - timedelta(days=365)).timestamp()
        * 1000
    )
    roster_id = int(team["roster_id"])
    sleeper_record = next(
        (
            record
            for record in VERIFIED_TRANSACTIONS
            if transaction_created_ms(record) >= cutoff_ms
            and str(record.get("type") or "").casefold() == "trade"
            and roster_id in transaction_roster_ids(record)
        ),
        None,
    )
    ledger_trade = latest_non_blacklisted_trade(team, ledger, now)

    sleeper_ms = transaction_created_ms(sleeper_record) if sleeper_record else 0
    ledger_ms = 0
    if ledger_trade and ledger_trade.get("created_at"):
        try:
            ledger_ms = int(
                datetime.fromisoformat(
                    str(ledger_trade["created_at"]).replace("Z", "+00:00")
                ).timestamp()
                * 1000
            )
        except ValueError:
            ledger_ms = 0

    if sleeper_record and sleeper_ms >= ledger_ms:
        return {
            "transaction_id": str(
                sleeper_record.get("transaction_id")
                or sleeper_record.get("id")
            ),
            "created_at": datetime.fromtimestamp(
                sleeper_ms / 1000,
                tz=generator.UTC,
            ).isoformat(),
            "type": "trade",
            "summary": summarize_transaction(sleeper_record, team),
            "source_file": sleeper_record.get("_source_file"),
        }
    if ledger_trade:
        return {**ledger_trade, "type": "trade"}
    return None


'''
if helper not in source:
    if anchor not in source:
        raise SystemExit("rival snapshot anchor not found")
    source = source.replace(anchor, helper + anchor, 1)

summary_anchor = '''    summary["schema_version"] = 6
'''
summary_insert = '''    verified_trade = latest_verified_trade(team, ledger, now)
    summary["latest_trade"] = verified_trade

    summary["schema_version"] = 7
'''
if summary_anchor in source:
    source = source.replace(summary_anchor, summary_insert, 1)
elif summary_insert not in source:
    raise SystemExit("summary schema anchor not found")

loop_anchor = '''        if section.get("id") == "close-the-gap":
'''
loop_replacement = '''        if section.get("id") == "latest-trade-impact":
            section["body"] = (
                verified_trade["summary"]
                if verified_trade
                else "No verified franchise trade was found in the last 365 days."
            )
        elif section.get("id") == "close-the-gap":
'''
if loop_replacement not in source:
    if loop_anchor not in source:
        raise SystemExit("section loop anchor not found")
    source = source.replace(loop_anchor, loop_replacement, 1)

path.write_text(source, encoding="utf-8")
print("Patched latest trade impact to use verified Sleeper and ledger trades.")
