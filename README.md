# Metering & Billing Engine

A usage-based metering and billing API for an AI API gateway. It records
metered usage events, enforces per-plan limits, computes usage-based bills
with overage pricing, generates monthly invoices, and integrates with Stripe
(test mode) for checkout, webhooks, and nightly reconciliation.

Built with **FastAPI**, **SQLAlchemy 2.0**, **Alembic**, **PostgreSQL**
(Neon), and **Stripe**.

## Feature summary

- **Usage metering** — record API-call and token usage events per subscription
  (`POST /api/v1/usage`, `POST /api/v1/generate`), with idempotency keys.
- **Per-type limits** — plans meter `API_CALL` and `TOKENS` usage separately
  (`api_call_limit`, `tokens_limit`).
- **Billing engine** — compute a bill for a subscription in the current month:
  included usage, overage, and overage cost.
- **Invoices** — generate a monthly invoice from the billing calculation,
  deduplicated per subscription + billing period, tenant-scoped listing.
- **Tenant isolation** — every tenant-scoped endpoint requires the
  `X-Tenant-Id` header and verifies ownership of the referenced subscription.
- **Stripe (test mode)** — hosted Checkout for subscriptions, signed webhooks
  (deduplicated via `webhook_events`), plan/status sync, and a background
  reconciliation loop.
- **Background reconciliation** — periodic job (default every 24h) that pulls
  the subscription from Stripe and syncs status/plan, alerting via the log on
  drift or failure.

## Project layout

```
app/
  api/v1/endpoints/   HTTP routes (usage, billing, invoices, stripe, ...)
  constants/          pricing, subscription status, usage types
  core/               config, logging, exceptions
  db/                 engine + session
  dependencies/       tenant auth dependency
  integrations/       Stripe client
  models/             SQLAlchemy ORM models
  repositories/       data-access layer
  schemas/            Pydantic request/response models
  services/           business logic
alembic/              schema migrations
scripts/seed.py       idempotent demo data seeder
tests/                pytest suite (35 tests)
```

## Prerequisites

- Python 3.14+
- PostgreSQL (or any Postgres-compatible service such as Neon)
- Optional: a Stripe test-mode account for checkout/webhook/reconciliation

## Setup

```bash
# 1. Install dependencies (uv, or pip + venv)
uv sync

# 2. Configure environment
cp .env.example .env
#   edit DATABASE_URL to point at your Postgres; add Stripe test keys if desired

# 3. Apply migrations
uv run alembic upgrade head

# 4. Seed demo data (Free/Pro plans, demo tenant, active subscription)
uv run python scripts/seed.py
#   -> prints the demo tenant id; use it as the X-Tenant-Id header

# 5. Run the server
uv run uvicorn app.main:app --reload
```

Interactive API docs: `http://localhost:8000/docs`
OpenAPI spec: `capstone.yaml` (exported from the live app).

## Quick demo

```bash
# Record 1,500 API-call usages on the demo subscription
curl -X POST http://localhost:8000/api/v1/usage \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: <demo-tenant-id>" \
  -d '{"subscription_id": "<demo-subscription-id>", "usage_type": "API_CALL", "amount": 1500}'

# See the current month's bill (Free plan = 1,000 included calls)
curl http://localhost:8000/api/v1/billing/<demo-subscription-id> \
  -H "X-Tenant-Id: <demo-tenant-id>"

# Generate an invoice from the bill
curl -X POST http://localhost:8000/api/v1/invoices \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: <demo-tenant-id>" \
  -d '{"subscription_id": "<demo-subscription-id>"}'
```

See `scripts/seed.py` for the demo Free/Pro limits and pricing.

## Stripe (test mode)

1. Create test-mode products/prices in the Stripe dashboard and set
   `plan.stripe_price_id` on each plan.
2. Set `STRIPE_API_KEY` and `STRIPE_WEBHOOK_SECRET` in `.env`.
3. Point a webhook endpoint at `POST /api/v1/webhooks/stripe`.
4. `GET /api/v1/stripe/checkout/{tenant_id}/{plan_id}` returns the hosted
   checkout URL for the tenant's subscription.

If the Stripe keys are unset the app still boots and all non-Stripe endpoints
work; checkout/webhook return a clear `500`.

## Testing

```bash
uv run pytest              # 35 tests
uv run ruff check .        # lint
uv run ruff format --check .
uv run mypy app            # type checking
```

## Evidence

`EVIDENCE.md` records probe results against the deployed app and shared Neon
database, including the migration chain, live API calls, Stripe webhook
verification, and reconciliation.
