# AVI Methodology Revision --- Market Reality v2

## Core Principle

AVI measures player value.

Recommendations measure **trade completion probability**.

Never confuse value with availability.

------------------------------------------------------------------------

## Market Reality Engine (Revised)

### Step 1 --- Manager First

Do **not** begin with players.

Begin by identifying managers who have: - surplus at RB - a competitive
window matching the proposed package - a reason to move an RB

Managers without a compelling motivation are eliminated before
evaluating players.

------------------------------------------------------------------------

### Step 2 --- Availability Filter

Classify every candidate:

-   Publicly Available
-   Unknown
-   Protected Asset

Protected Assets include: - recently acquired players (within 30 days) -
franchise cornerstones - elite young players - foundational starters -
players essential to a contender's lineup

Protected Assets are automatically rejected unless there is verified
evidence they are actively being shopped.

------------------------------------------------------------------------

### Step 3 --- Opposing GM Motivation

Answer all three:

1.  Why would this manager move this player?
2.  What problem does my package solve?
3.  Would a reasonable dynasty manager seriously consider accepting?

If any answer is "No" or "Probably not":

**Reject the player.**

------------------------------------------------------------------------

### Step 4 --- Lineup Replacement

Determine whether the manager can replace the departing player
internally.

If not:

**Reject the player.**

------------------------------------------------------------------------

### Step 5 --- Competitive Window

Support the classification using the verified team file.

Allowed classifications: - Contender - Balanced - Retool - Rebuild -
Unknown

Unknown managers cannot receive recommendations.

------------------------------------------------------------------------

### Step 6 --- Package Match

Evaluate: - market demand - scarcity - positional value - age -
perceived dynasty value - current league environment

Do not rely on summed AVI.

------------------------------------------------------------------------

### Step 7 --- Acceptance Probability

Score:

  Factor                     Weight
  ------------------------ --------
  Availability                   30
  Opposing GM Motivation         25
  Package Match                  20
  Lineup Replacement             15
  Competitive Window             10

Classification:

-   90--100 Highly Realistic
-   70--89 Realistic
-   50--69 Stretch
-   30--49 Unlikely
-   0--29 Impossible

------------------------------------------------------------------------

## Elimination Rule

Market Reality is an elimination process.

Evaluate every plausible target.

Reject players one by one.

Only after every rejection is complete may recommendations be produced.

------------------------------------------------------------------------

## Empty Result Rule

If no player satisfies every requirement:

-   Acceptance Probability ≥70%
-   Availability passed
-   Opposing GM Validation passed
-   Competitive Window aligned
-   Lineup Replacement passed

Do **not** relax the standards.

Do **not** recommend stretch targets.

Instead report:

> Based on current Market Reality, there are no realistic acquisition
> targets for this package.

This is considered a successful analysis.

------------------------------------------------------------------------

# Delivery Format

## Verification Report

    =========================
    AVI VERIFICATION REPORT
    =========================

    User Team Verified
    Analysis Goal Verified
    Required Files Retrieved
    All Players Verified
    All Picks Verified
    Official AVI Retrieved
    Public Analysis Retrieved
    Ready For Analysis

------------------------------------------------------------------------

## Executive Summary

One concise paragraph describing: - package strength - market outlook -
expected number of realistic targets

------------------------------------------------------------------------

## Market Reality Summary

Summarize: - managers evaluated - managers eliminated - reasons for
elimination

------------------------------------------------------------------------

## Realistic Targets

Display only players with: - Acceptance Probability ≥70% - All
validation checks passed

For each:

-   Why this manager would trade the player
-   What your package solves
-   Lineup replacement
-   Acceptance Probability
-   Championship Impact
-   Dynasty Impact

------------------------------------------------------------------------

## Rejected Targets

Do not list rejected players unless the user specifically asks why a
player was excluded.

------------------------------------------------------------------------

## Final Recommendation

If one or more targets remain:

Recommend only those players.

If zero remain:

> Based on current Market Reality, there are no realistic acquisition
> targets for this package.

Never substitute lower-quality recommendations simply to produce a list.


------------------------------------------------------------------------

# Weekly Valuation Protocol — 2026-07-13

## C-AVI (Championship AVI)

C-AVI measures current championship-winning value on a 0–100 scale.

- 50% FantasyPros 2026 full-season projection score
- 10% Autobots league context and positional scarcity
- 30% live public-market consensus, benchmarked against FantasyPros dynasty/redraft rankings, KeepTradeCut rankings, ESPN analysis, and current NFL reporting
- 10% elite league-winning upside

## D-AVI (Dynasty AVI)

D-AVI measures expected 2–6 year dynasty value on a 0–100 scale. It blends current C-AVI, prior dynasty value, age/position lifecycle, health and role stability, and live dynasty-market consensus.

## Update Rules

- Values are bounded from 0 to 100.
- Current Sleeper roster ownership overrides historical trade inference.
- FantasyPros projection matches are refreshed automatically.
- IDP and other players without compatible supplied projections preserve their approved baseline pending position-specific projections.
- Free-agent values are generated using the same C-AVI framework and a dynasty market/longevity adjustment.

---

# Offseason Efficiency Engine

## Purpose

Measure how efficiently each Autobots manager transformed the franchise's verified end-of-2025 roster and traded-pick position into its current roster and current draft-pick position.

This engine evaluates offseason results. It must not invent historical values or claim that a move was optimal based on information available at the time unless a dated valuation source is present.

## Data Authority

Use sources in this order:

1. The locked end-of-2025 baseline embedded in each team file.
2. The current roster and current player cards in each team file.
3. The current draft-pick ownership file.
4. The locked append-only historical trade ledger to explain asset movement and manager tendencies.
5. Live public market analysis for present-day dynasty sentiment.
6. Verified dated historical valuation sources only when decision-time analysis is requested.

Historical roster membership never overrides current ownership.

## Required Comparison Modes

### Current-Value Retrospective

Apply current C-AVI and D-AVI values to both the end-of-2025 baseline assets and current assets.

This answers:

"Which manager converted the end-of-2025 asset base into the strongest collection of assets today?"

This is the default offseason-efficiency mode.

### Decision-Time Process Review

Use only when dated historical AVI or verified dated public-market values are available for each material asset at the time of acquisition or sale.

This answers:

"Which manager made the strongest decisions based on the information available at the time?"

If dated values are incomplete, label this analysis unavailable rather than estimating.

## Mandatory Verification

Before producing a league-wide offseason ranking, verify:

- All 16 team files contain the locked end-of-2025 baseline.
- Every baseline roster is matched by roster ID.
- Current player ownership comes from current team files.
- Current pick ownership comes from the current draft-pick file.
- Baseline traded-pick deviations come from the supplied 2025 traded-picks snapshot.
- Player comparison uses Sleeper player IDs, not name-only matching.
- No player is counted twice on the same side of a comparison.
- No traded pick is counted both as retained and acquired.
- Current live public-market research is complete.

If any required source cannot be verified, stop and identify the missing source.

## Offseason Asset Reconciliation

For each team, classify every baseline and current asset:

- Retained player
- Acquired player
- Departed player
- Retained original pick
- Acquired pick
- Departed original pick
- Converted asset, where a departed asset directly funded an acquired asset through a verified trade
- Unexplained ownership change, which must be flagged for verification

Use the transaction ID in the historical ledger whenever a change can be tied to a completed trade.

## Scoring Framework

Score each team from 0 to 100 using the following components:

| Component | Weight |
|---|---:|
| Championship lineup improvement | 30 |
| Dynasty asset improvement | 25 |
| Trade value efficiency | 20 |
| Positional need resolution | 10 |
| Roster flexibility and pick preservation | 10 |
| Dead-asset reduction | 5 |

### Championship Lineup Improvement

Compare the optimal current starting lineup with the optimal lineup drawn from the end-of-2025 baseline, using current C-AVI values for both groups.

C-AVI means Championship AVI: current championship-winning value.

### Dynasty Asset Improvement

Compare the current offensive roster and verified draft assets with the end-of-2025 baseline, using current D-AVI values and the approved current draft-pick curve.

D-AVI means Dynasty AVI: long-term dynasty value.

Do not simply total all roster values. Account for lineup usability, asset quality, age curve, positional scarcity, concentration risk, and replacement value.

### Trade Value Efficiency

Evaluate verified assets surrendered against verified assets acquired.

Consider:

- Package quality
- Consolidation or fragmentation
- Opportunity cost
- Market liquidity
- Current public consensus
- Whether value gains resulted from intentional transactions or passive market movement

### Positional Need Resolution

Measure whether the team improved weak starting positions or created a more complete championship lineup.

### Roster Flexibility and Pick Preservation

Evaluate future draft capital, tradable depth, roster spots, liquidity, and the ability to pivot between competing and rebuilding.

### Dead-Asset Reduction

Credit the conversion of non-starting, declining, injured, or low-liquidity assets into usable players or picks. Do not credit simple removal unless replacement value improved.

## Efficiency Versus Raw Improvement

A team may improve substantially without being efficient if it spent disproportionate draft capital or premium players.

A team may be highly efficient with a smaller raw gain if the gain required little cost.

Always report both:

- Raw offseason improvement
- Offseason efficiency

## Required League-Wide Output

When asked who had the most efficient offseason, include:

- Rank for all 16 teams
- Offseason Efficiency Score
- Championship lineup change
- Dynasty asset change
- Draft-capital change
- Best move
- Largest cost
- Current market trend
- Confidence level
- Letter grade

Use the following visual classifications:

- 🟢 85-100: Elite offseason
- 🟢 70-84: Strong offseason
- 🟡 55-69: Mixed-positive offseason
- 🟡 40-54: Mixed-negative offseason
- 🔴 0-39: Poor offseason

## Required Caveats

State whether the analysis is:

- Current-value retrospective
- Fully dated decision-time review
- Partial decision-time review

Never treat current value appreciation as proof that the original decision process was correct.

## Final Verdict

Identify:

- 🏆 Most efficient offseason
- 📈 Most improved championship roster
- 🌱 Most improved dynasty asset base
- 💰 Best value creator
- ⚠️ Highest-cost improvement
- 🔴 Least efficient offseason

Include a confidence level based on source completeness.

