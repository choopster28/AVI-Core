# AVI Core v1.0.0

AVI Core automates the Autobots Value Index update process while preserving the approved Market Reality methodology.

## Included

- Sleeper league history from 2024 onward
- Current rosters, users, drafts, traded picks, weekly transactions
- Permanent completed-trade ledger deduplicated by `transaction_id`
- Sleeper-first verified player projections, completed-week PPR stats and actionable injury designations, with per-player/per-week FantasyPros fallback
- FantasyPros players, projections, dynasty rankings, redraft rankings, injuries, news, and player points retained as fallback/market inputs
- Player points collected before the season but weighted at 0% until verified regular-season production exists
- Position-relative scoring primitives
- Approved C-AVI and D-AVI weight structures
- First-round pick values from 1.01 through 1.16
- Validation gates
- One GitHub Actions workflow
- Automated tests

## Important limitation

KeepTradeCut does not provide an official API in this project. AVI Core therefore supports a structured public-market input file and preserves the prior approved market score when a required live source is unavailable. It does not fabricate market data.

## Windows setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edit `.env`, then run:

```powershell
python -m avi.cli update-sleeper
python -m avi.cli validate-sleeper
python -m avi.cli update-fantasypros
python -m avi.cli validate-fantasypros
python -m avi.cli show-pick-values
```

## GitHub secrets

Create these repository secrets:

- `SLEEPER_LEAGUE_ID`
- `FANTASYPROS_API_KEY`

Then run **Update AVI Source Data** from the Actions tab.

## Sleeper-first valuation inputs

Daily AVI updates retrieve Sleeper NFL weekly PPR stats and season projections from its additional v1 feeds. Unlike the official league/players API, those feeds are not guaranteed; invalid, missing, malformed or implausibly small responses are discarded. AVI transparently falls back to FantasyPros **for each missing player/week or projection**, without discarding unrelated verified Sleeper inputs. The calculation records `data_sources` per player (production, projections, injuries, news and market). Injury statuses prioritize Sleeper when Sleeper has an actionable designation; otherwise FantasyPros is consulted. FantasyPros remains the source of redraft/dynasty consensus and news until comparable Sleeper feeds are verified.

The latest feed ingestion result is stored at `data/raw/sleeper/valuation/manifest.json`. A successful GitHub Actions run verifies data acquisition, tests and publication; inspect this manifest before assuming Sleeper was available for every category. Neither feed is fabricated on failure.
