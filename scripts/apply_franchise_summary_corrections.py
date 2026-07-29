from pathlib import Path

path = Path("generate_weekly_executive_summary_filtered.py")
source = path.read_text(encoding="utf-8")

before = '''    for pick in record.get("draft_picks") or []:
        if not isinstance(pick, dict):
            continue
        add(pick.get("owner_id"))
        add(pick.get("previous_owner_id"))
        add(pick.get("roster_id"))
'''
after = '''    for pick in record.get("draft_picks") or []:
        if not isinstance(pick, dict):
            continue
        # Only the current and previous owners participated in the trade.
        # roster_id identifies the franchise that originally owned the pick and
        # must never be treated as a transaction counterparty.
        add(pick.get("owner_id"))
        add(pick.get("previous_owner_id"))
'''
if before not in source:
    raise RuntimeError("transaction participant block not found")
source = source.replace(before, after, 1)

before = '''        received = [*added, *picks_received]
        sent = [*dropped, *picks_sent]
        details: list[str] = []
        if received:
            details.append(f"acquired {', '.join(received)}")
        if sent:
            details.append(f"sent {', '.join(sent)}")
        return opening + (
            f" and {' while '.join(details)}."
            if details
            else "."
        )
'''
after = '''        received = [*added, *picks_received]
        sent = [*dropped, *picks_sent]
        details: list[str] = []
        if received:
            details.append(f"acquired {', '.join(received)}")
        if sent:
            details.append(f"sent {', '.join(sent)}")
        return opening + (
            f" and {' and '.join(details)}."
            if details
            else "."
        )
'''
if before not in source:
    raise RuntimeError("trade summary grammar block not found")
source = source.replace(before, after, 1)

# Add a validation that catches original-pick franchises leaking into the
# counterparty list in any future generator change.
anchor = '''        dynasty = payload.get("dynasty_power") or {}
'''
validation = '''        rival_activity = (rival or {}).get("latest_activity") or {}
        rival_summary = str(rival_activity.get("summary") or "")
        if rival_activity.get("type") == "trade" and "completed a trade with" in rival_summary:
            transaction_id = str(rival_activity.get("transaction_id") or "")
            transaction = next(
                (
                    record for record in VERIFIED_TRANSACTIONS
                    if str(record.get("transaction_id") or record.get("id") or "") == transaction_id
                ),
                None,
            )
            if transaction:
                participant_ids = transaction_roster_ids(transaction)
                original_only_ids = {
                    int(pick.get("roster_id"))
                    for pick in transaction.get("draft_picks") or []
                    if isinstance(pick, dict)
                    and pick.get("roster_id") is not None
                    and int(pick.get("roster_id")) not in participant_ids
                }
                for original_id in original_only_ids:
                    original_name = ROSTER_NAMES.get(original_id)
                    if original_name and f"with {original_name}" in rival_summary:
                        raise RuntimeError(
                            f"Original pick franchise leaked into trade counterparties in {path}"
                        )

        dynasty = payload.get("dynasty_power") or {}
'''
if anchor not in source:
    raise RuntimeError("validation anchor not found")
source = source.replace(anchor, validation, 1)

path.write_text(source, encoding="utf-8")
print("Applied franchise summary participant and grammar corrections.")
