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

### Injury and availability adjustment

Routine injuries are handled automatically after the refreshed in-season calculation and before exceptional manual risk adjustments. The availability layer reads current Sleeper injury status plus FantasyPros injury/timeline data and converts explicit missed-time signals into a championship-horizon availability ceiling through fantasy Week 17.

The adjustment is deliberately projection-aware. It is a **ceiling, not a multiplier**. Refreshed projections, rankings, and actual production get the first opportunity to price the injury. The availability layer only reduces C-AVI when the calculated value still exceeds the maximum contribution supported by the player's verified remaining availability. If projections have already reduced C-AVI below that ceiling, the automatic injury adjustment is exactly zero. This prevents routine injuries from being double penalized.

Examples of actionable signals include injured reserve/PUP/NFI, Out, Doubtful, Questionable with an available probability-of-playing estimate, explicit IR-week timelines, and season-ending language. IR without a more specific verified timeline uses a conservative four-week minimum absence. Every applied adjustment stores the pre-adjustment C-AVI, availability ceiling, estimated missed weeks, status/reason code, adjustment amount, and final C-AVI for auditability.

Exceptional current-season availability risks that are not routine injury designations or are not represented by the automatic feeds may still receive a transparent manual C-AVI risk adjustment. These adjustments must state the football-value reason and review trigger, are idempotent, and are applied after the automatic injury layer.

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

After all automatic availability and exceptional C-AVI risk adjustments are applied, D-AVI is recalculated from the final C-AVI. Because current C-AVI is only 10% of D-AVI, a normal short-term injury can materially reduce championship value without creating an equally large dynasty-value penalty.

## Verified-Input Policy

Missing optional components do not receive invented neutral values.

Their weights are redistributed proportionally across verified components
available for the player.

## Current Implemented Inputs

The repository currently implements:

- FantasyPros dynasty consensus as the verified dynasty-market score
- continuous position-specific age and career-horizon curves
- Autobots league-specific positional liquidity
- current C-AVI, including projection-aware current-season availability effects
- a verified long-term ceiling blend

Long-term role security and a standalone long-term health-outlook source remain unavailable until verified source data is stored in the repository. Their weights are redistributed. Current-season injury effects still reach D-AVI indirectly through its 10% current-C-AVI component.

## Removed Circular Inputs

The revised model removes:

- prior D-AVI feedback
- role stability copied from market score
- health copied from market score
- redraft consensus from the D-AVI dynasty-market component

## Autobots Format Adjustment

Quarterback liquidity is capped for the Autobots 1QB, non-Superflex format.
RB, WR, and TE liquidity use verified mandatory-starter and FLEX demand.
