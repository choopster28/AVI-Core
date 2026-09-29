# AVI Methodology 2026.3

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
| Actual current-season production | 25% |
| Refreshed current-season projection | 30% |
| Autobots league context | 10% |
| Public market | 25% |
| Elite upside | 10% |

### Actual production

Actual production is measured as current-season PPR points per game and scored relative to the player's position. Using per-game production prevents bye weeks and short injury absences from being counted twice; availability is handled separately by the injury layer. The current-season production component therefore answers how well the player has actually performed when active.

### Public market

C-AVI's current-season public-market score prioritizes current redraft value over dynasty value:

- 80% FantasyPros redraft consensus
- 20% FantasyPros dynasty consensus

If only one verified ranking source is available for a player, that verified source is used rather than inventing a neutral value. D-AVI remains the primary dynasty valuation model.

### Autobots league context

League context is now independent from the player's projection score. It is driven by Autobots-format positional liquidity using the verified 16-team lineup requirements and FLEX demand. This prevents the projection component from being counted again under a different label.

### Elite upside

During the regular season, elite upside is the player's best completed-week PPR output scored relative to the player's position. This captures demonstrated spike-week / league-winning ceiling rather than reusing the season projection.

Before completed-week production is available, preseason elite upside uses a top-tail transformation of the verified redraft market score so only genuinely elite current-season market positions receive strong upside credit.

### Completed-week and freshness guard

Current-season production and weekly ceiling are not consumed mid-week or from a stale prior-season payload. During the regular season, the player-points feed must contain at least one completed week, may not contain weeks beyond the latest completed NFL week, and must contain a minimum viable mapped player population. Sleeper NFL state and the ESPN NFL scoreboard independently verify week completion.

### Injury and availability adjustment

Routine injuries are handled automatically after the refreshed in-season calculation and before exceptional manual risk adjustments. The availability layer reads current Sleeper injury status plus FantasyPros injury/timeline data and converts explicit missed-time signals into a championship-horizon availability ceiling through fantasy Week 17.

The adjustment is deliberately projection-aware. It is a ceiling, not a multiplier. Refreshed projections, rankings, and actual production get the first opportunity to price the injury. The availability layer only reduces C-AVI when the calculated value still exceeds the maximum contribution supported by the player's verified remaining availability. If projections have already reduced C-AVI below that ceiling, the automatic injury adjustment is exactly zero.

Exceptional current-season risks not represented by routine injury feeds may still receive a transparent manual C-AVI adjustment. These adjustments must state the football-value reason and review trigger, are idempotent, and are applied after the automatic injury layer.

## D-AVI

D-AVI remains the long-term dynasty model:

| Component | Weight |
|---|---:|
| Live dynasty-market consensus | 35% |
| Position-adjusted age and career horizon | 20% |
| Long-term role and talent security | 15% |
| Autobots positional scarcity and liquidity | 10% |
| Current C-AVI | 10% |
| Health and availability outlook | 5% |
| Long-term ceiling and trajectory | 5% |

After all automatic availability and exceptional C-AVI risk adjustments are applied, D-AVI is recalculated from the final C-AVI.

## Verified-input policy

Missing optional components do not receive invented neutral values. Their weights are redistributed proportionally across verified components available for the player.

## Autobots format adjustment

Quarterback liquidity is capped for the Autobots 1QB, non-Superflex format. RB, WR, and TE liquidity use verified mandatory-starter and FLEX demand.
