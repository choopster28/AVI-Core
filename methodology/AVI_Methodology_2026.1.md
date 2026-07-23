# AVI Methodology 2026.1

## Core Principle

AVI measures player value.

Recommendations measure trade completion probability.

Never confuse value with availability.

## Market Reality Engine

The existing manager-first process, availability filter, protected-asset rules,
opposing GM motivation test, lineup replacement test, competitive-window
classification, package-match analysis, acceptance-probability weights,
elimination rule, empty-result rule, and delivery format remain preserved.

## Package Match

Evaluate: - market demand - scarcity - positional value - age -
perceived dynasty value - current league environment

Do not rely on summed AVI.

## C-AVI

Preseason:

- 50% FantasyPros full-season projection score
- 10% Autobots league context and positional scarcity
- 30% live public-market consensus
- 10% elite league-winning upside

In season, after verified regular-season player points exist:

- 10% FantasyPros current-season player-points score
- 40% FantasyPros full-season projection score
- 10% Autobots league context and positional scarcity
- 30% live public-market consensus
- 10% elite league-winning upside

Numeric field score:

- 60% positional percentile
- 40% replacement-adjusted score

Player-points score:

- 70% total-points field score
- 30% points-per-game field score

Autobots context:

- 45% value above Autobots replacement
- 30% positional scarcity
- 25% lineup leverage

Public market:

- 35% KeepTradeCut 1QB dynasty
- 30% FantasyPros dynasty consensus
- 15% FantasyPros redraft consensus
- 10% role and depth-chart consensus
- 10% current NFL news and reporting

Elite upside:

- 40% elite projection standing
- 30% weekly ceiling profile
- 20% premium-usage opportunity
- 10% contingent upside

## D-AVI

- 35% live dynasty-market consensus
- 20% current C-AVI
- 15% age and positional lifecycle
- 10% role, contract, and team stability
- 10% prior approved D-AVI
- 5% health and availability outlook
- 5% long-term ceiling and trajectory

## Draft Picks

First-round rookie-pick AVI resets to `91.0` at `1.01` for each draft year.

Depreciation curve:

- Picks `1.02` through `1.04` depreciate by `1.2` per pick.
- Picks `1.05` through `1.11` depreciate by `1.7` per pick.
- Picks `1.12` through `1.16` depreciate by `2.0` per pick.
- All picks after `1.16` continue depreciating by `2.0` per overall pick.
- Draft-pick AVI is floored at `0.0`.

Valid rounds are 1 through 10, with 16 picks per round.

## Update Rules

- All values are bounded from 0 to 100.
- Current Sleeper ownership overrides historical inference.
- Player points are collected before the season but receive zero C-AVI weight.
- Player points activate only after verified regular-season production exists.
- Missing compatible IDP projections preserve the approved baseline.
- Missing public-market inputs preserve the prior approved component rather than being fabricated.
