# AVI Core v0.2.0

AVI Core automates the existing Autobots Value Index update process without changing the approved AVI methodology.

## What this release does

- Downloads the current Sleeper league and linked league seasons back through 2024.
- Downloads users, rosters, drafts, traded picks, weekly transactions, and the NFL player directory.
- Builds a deduplicated completed-trade ledger using Sleeper `transaction_id`.
- Connects to the FantasyPros API through configurable endpoint paths.
- Stores raw source responses separately from processed outputs.
- Runs locally with the `avi` command or in GitHub Actions.
- Blocks publication when validation fails.

## Methodology lock

This repository does **not invent or modify** C-AVI, D-AVI, draft-pick, or Market Reality formulas.

The included methodology adapter intentionally refuses to calculate official AVI values until the exact currently approved formula is placed in:

`src/avi/methodology/current.py`

This protects the existing methodology from accidental reinterpretation. The Sleeper and FantasyPros automation can be tested independently before that final formula-porting step.

## Windows setup

Open PowerShell in the repository directory:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env` and add your values.

Then run:

```powershell
avi sleeper-update
avi fantasypros-update
avi validate-sleeper
```

## Required environment variables

```text
SLEEPER_LEAGUE_ID=
FANTASYPROS_API_KEY=
```

Optional variables are documented in `.env.example`.

## GitHub secrets

Add these repository secrets:

- `SLEEPER_LEAGUE_ID`
- `FANTASYPROS_API_KEY`

FantasyPros endpoint paths may also be set as repository variables if your API account uses paths different from the defaults in `.env.example`.

## Output structure

```text
data/
  raw/
    sleeper/
      leagues/
        2024_<league_id>/
        2025_<league_id>/
        2026_<league_id>/
      nfl_players.json
      manifest.json
    fantasypros/
      players.json
      projections.json
      rankings.json
      injuries.json
      news.json
      manifest.json
  processed/
    trades/
      all_completed_trades.json
    transactions/
      all_transactions.json
    validation/
      sleeper_validation.json
```

## Full trade-history rule

AVI tracks linked Sleeper league seasons from the current league backward, but publishes only seasons from 2024 onward.

Completed trades are:

- restricted to `type == "trade"`
- restricted to `status == "complete"`
- deduplicated by `transaction_id`
- sorted chronologically
- validated so the ledger cannot silently shrink below an optional baseline

Set this optional environment variable to enforce the current verified minimum:

```text
AVI_MINIMUM_COMPLETED_TRADES=61
```

Adjust that value only after verifying that new completed trades have legitimately increased the ledger.

## FantasyPros API

FantasyPros API access can vary by account. AVI Core therefore keeps endpoint paths configurable:

```text
FANTASYPROS_PLAYERS_PATH=
FANTASYPROS_PROJECTIONS_PATH=
FANTASYPROS_RANKINGS_PATH=
FANTASYPROS_INJURIES_PATH=
FANTASYPROS_NEWS_PATH=
```

The client sends the API key using the `x-api-key` header by default.

If an endpoint is not enabled for your account, leave its path blank and AVI will skip it rather than fabricate data.
