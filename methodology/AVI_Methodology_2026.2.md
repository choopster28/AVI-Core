# AVI Methodology 2026.2

## D-AVI

D-AVI measures long-term dynasty value in the Autobots non-Superflex league.

| Component | Weight |
|---|---:|
| Live dynasty-market consensus | 35% |
| Position-adjusted age and career horizon | 20% |
| Long-term role and talent security | 15% |
| Autobots positional scarcity and liquidity | 10% |
| Current C-AVI | 10% |
| Health and availability outlook | 5% |
| Long-term ceiling and trajectory | 5% |

## Verified-Input Policy

Missing optional components do not receive invented neutral values.

Their weights are redistributed proportionally across verified components
available for the player.

## Current Implemented Inputs

The repository currently implements:

- FantasyPros dynasty consensus as the verified dynasty-market score
- continuous position-specific age and career-horizon curves
- Autobots league-specific positional liquidity
- current C-AVI
- a verified long-term ceiling blend

Role security and health remain unavailable until verified source data is
stored in the repository. Their weights are redistributed.

## Removed Circular Inputs

The revised model removes:

- prior D-AVI feedback
- role stability copied from market score
- health copied from market score
- redraft consensus from the D-AVI dynasty-market component

## Autobots Format Adjustment

Quarterback liquidity is capped for the Autobots 1QB, non-Superflex format.
RB, WR, and TE liquidity use verified mandatory-starter and FLEX demand.
