# site-operations

Automated SEO health checks and content expiry detection for all sites.

## Workflows

| Workflow | Schedule | What it does |
|---|---|---|
| `weekly-audit.yml` | Every Monday 02:00 UTC | Checks title/desc/canonical/H1/alt/GA4/JSON-LD for all sites |
| `content-expiry.yml` | Every Wednesday 03:00 UTC | Scans pages for stale year references, opens GitHub Issues |

## Run manually

Go to **Actions** tab → select workflow → **Run workflow** → choose site.

## Reports

Saved to `reports/audit-YYYY-MM-DD.json`. Downloadable as Actions Artifacts (kept 90 days).

## Sites monitored

See `data/sites.json`.

## Adding a new site

1. Edit `data/sites.json`
2. Edit `scripts/audit.py` → add to `SITES` list
3. Edit `scripts/expiry_check.py` → add to `SITES` list
