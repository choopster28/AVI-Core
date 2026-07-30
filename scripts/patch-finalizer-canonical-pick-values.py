from pathlib import Path

path = Path("finalize_franchise_summaries.py")
source = path.read_text(encoding="utf-8")

number_anchor = '''def latest_traded_picks_path() -> Path | None:
'''
helpers = '''def round_to_tenth(value: float) -> float:
    return round(value * 10) / 10


def first_round_pick_value(slot: int) -> float:
    if slot <= 4:
        return round_to_tenth(91 - (slot - 1) * 1.2)
    if slot <= 11:
        return round_to_tenth(87.4 - (slot - 4) * 1.7)
    return round_to_tenth(75.5 - (slot - 11) * 2)


def first_round_average_value() -> float:
    return round_to_tenth(
        sum(first_round_pick_value(slot) for slot in range(1, 17)) / 16
    )


def projected_draft_pick_value(season: int, round_value: int) -> float:
    if round_value == 1:
        return first_round_average_value()
    base = {2: 54.0, 3: 34.0}.get(round_value, 22.0)
    years_out = max(0, season - CURRENT_SEASON)
    return min(95.0, max(8.0, round_to_tenth(base - years_out * 6)))


'''
if helpers not in source:
    if number_anchor not in source:
        raise SystemExit("helper anchor not found")
    source = source.replace(number_anchor, helpers + number_anchor, 1)

source = source.replace(
    '    """Rebuild the exact current/future pick ledger used by Autobots HQ."""',
    '    """Rebuild the exact 2027+ pick ledger and canonical values used by Autobots HQ."""',
)

current_start = source.find("    # Current slotted class: use live Sleeper ownership first, then processed owner.\n")
future_start = source.find("    # Future classes: native ownership for every round, then apply verified trades.\n")
if current_start >= 0 and future_start > current_start:
    source = source[:current_start] + source[future_start:]
elif current_start >= 0:
    raise SystemExit("could not locate future ledger anchor")

old_values = '''    round_average = {
        key: round(sum(values) / len(values), 1) if values else 0.0
        for key, values in round_values.items()
    }
    for (season, round_value, _original_id), owner_id in future_ledger.items():
        totals[owner_id] += round_average.get((season, round_value), 0.0)
'''
new_values = '''    for (season, round_value, _original_id), owner_id in future_ledger.items():
        totals[owner_id] += projected_draft_pick_value(season, round_value)
'''
if old_values in source:
    source = source.replace(old_values, new_values, 1)
elif new_values not in source:
    raise SystemExit("future value block not found")

source = source.replace(
    '"plus the reconstructed live 2027+ pick ledger using native picks, "\n                "historical trades, raw Sleeper ownership, and round-average AVI"',
    '"plus the reconstructed live 2027+ pick ledger using native picks, "\n                "historical trades, raw Sleeper ownership, and the canonical "\n                "projected-pick valuation curve"',
)

path.write_text(source, encoding="utf-8")
print("Patched finalizer to use 2027+ only and canonical projected pick values.")
