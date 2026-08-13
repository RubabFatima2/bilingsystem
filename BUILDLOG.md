# Build Log

## 2026-08-07 — Project foundation
- `feat: initialize FastAPI project foundation` (`828811b`)
- `feat: add SQLAlchemy database foundation` (`7ae5ba9`)
- `feat: implement tenant management` (`c2f9224`)
- `feat: implement tenant, plan, and subscription modules` (`a979a5d`)
- `feat: implement billing calculation engine` (`21d32c2`)
- `feat: configure database schema and initial migrations` (`d246bcb`)
- `feat: set up database migrations` (`0bc5b5c`)
- `fix SQLAlchemy model imports` (`3e3b6d8`)

## 2026-08-11 — Invoice lifecycle
- `feat: add invoice repository` (`53b3087`)
- `feat: create invoice from billing calculation` (`584e876`)
- `feat: add invoice repository listing` (`df40521`)
- `feat: add invoice response schema` (`34d39af`)
- `feat: add invoice service` (`14c4874`)
- `feat: add invoice listing endpoint` (`00ab82d`)
- `feat: add invoice lookup by subscription` (`92370ee`)
- `feat: prevent duplicate invoices` (`d59bd2e`)
- `feat: add billing period to invoices` (`5d19f2b`)

## 2026-08-13 — Metering, billing, Stripe, tests
- `feat: implement usage metering` (`04b6e6b`)
- `feat: implement billing and cost calculation` (`e9672a3`)
- `feat: Add Stripe integration` (`bdd1953`) — checkout, signed webhooks,
  webhook-event dedup table
- `feat: Add generate endpoint` (`2eacc36`)
- `feat: Add tenant dependencies and utilities` (`d87a9f7`) — `X-Tenant-Id`
  auth + subscription ownership checks
- `feat: Add service tests` (`052d4c4`) — 35 tests
- `feat: Update project configuration` (`7e9d8dc`) — ruff/mypy config

## 2026-08-13 — Capstone polish
- Migration chain applied to Neon: initial schema -> invoices -> billing
  period -> usage types + per-type plan limits -> Stripe fields +
  `webhook_events`
- Tenant-scoped invoice listing, per-type plan limits in models/schemas/
  repositories, Stripe ID lookups
- Seeded demo data (Free/Pro plans, demo tenant, active subscription)
- Export OpenAPI spec to `capstone.yaml`
- Added `README.md`, `EVIDENCE.md`, `LICENSE`
