# Franchise Executive Summaries

This directory is the website-facing source for Franchise HQ executive summaries.

## Source policy

- Generation may read only files under `knowledge/`.
- Franchise roster facts must come from the matching file in `knowledge/teams/`.
- No conversation history, model memory, public web data, or hard-coded player/pick narratives may be used.
- Unsupported claims are omitted or explicitly marked unavailable.

## Refresh schedule

The GitHub Actions workflow runs every Wednesday at 11:00 AM in `America/Denver`. It checks both possible UTC hours and enforces Mountain local time to remain stable through daylight-saving changes.

## Output contract

- One JSON file per franchise, named by franchise slug.
- `manifest.json` lists the available files.
- Preseason summaries emphasize verified lineup strength, pressure points, depth, availability, and attached draft assets.
- Regular-season summaries add matchup recap and standings sections only when those facts exist in approved `knowledge/` files.
