# AVI Methodology 2026.2

## C-AVI

C-AVI measures current-season championship value in the Autobots non-Superflex league.

### Preseason weighting

| Component | Weight |
|---|---:|
| Refreshed current-season projection | 50% |
| Autobots league context | 10% |
| Public market | 30% |
| Elite upside | 10% |
| Actual current-season player points | 0% |

### In-season weighting

After at least one complete 2026 regular-season week is verified in the current FantasyPros player-points feed, the model transitions globally to:

| Component | Weight |
|---|---:|
| Actual current-season player points | 10% |
| Refreshed current-season projection | 40% |
| Autobots league context | 10% |
| Public market | 30% |
| Elite upside | 10% |

The transition applies to every supported offensive player, not selected players. Actual production is scored relative to the player's position. The daily pipeline refreshes projections and player-point data before recalculation.

### Completed-week and freshness guard

Current-season production is not consumed mid-week or from a stale prior-season payload. During the regular season, the player-points feed must contain at least one completed week, may not contain weeks beyond the latest completed NFL week, and must contain a minimum viable mapped player population. This prevents old or partial data from falsely activating the in-season model.

Exceptional current-season availability risks that are not represented by public projections/rankings may receive a transparent post-model C-AVI risk adjustment. These adjustments must state the football-value reason and review trigger, are idempotent, and are applied before downstream team/player reports are generated.

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
