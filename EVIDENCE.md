# Evidence

Probe results captured against the deployed app and the shared Neon database.

## Probe 1 — Test suite, lint, and type checking

```
$ uv run pytest
35 passed in 2.93s

$ uv run ruff check .
All checks passed!

$ uv run ruff format --check .
(55 files reformatted, 24 left unchanged; now clean)

$ uv run mypy app
Success: no issues found in 64 source files
```

## Probe 2 — Migration chain applied to Neon

```
$ alembic current
c1d0e2f3a4b5 (head)

$ alembic_version rows: ['c1d0e2f3a4b5']
```

Migration chain (oldest -> head):

```
43dca0c47b44  create_initial_schema
53.../8b0e3e7d8039  add_invoices
4c4dce7abd0f  add_billing_period_to_invoices
2a29408dbf7d  add_usage_types_and_per_type_plan_limits
c1d0e2f3a4b5  add_stripe_fields_and_webhook_events  (head)
```

Public tables now present:

```
['alembic_version', 'invoices', 'plans', 'subscriptions', 'tenants',
 'usage_events', 'webhook_events']
```

`subscriptions` columns include the Stripe fields:

```
id, tenant_id, plan_id, status, started_at, stripe_customer_id, stripe_subscription_id
```

## Probe 3 — Seeded demo data (idempotent seed)

```
PLANS:
  Free | price 0 | usage_limit 1000 | api_call_limit 1000 | tokens_limit 100000
  Pro  | price 5000 | usage_limit 10000 | api_call_limit 10000 | tokens_limit 5000000

TENANTS:
  16c57711-e45e-4efa-8249-bf948057d7f5  Demo Tenant  demo@example.com

SUBSCRIPTIONS:
  acc55c3c-4d6b-4dd5-b523-5c0117fec06d | tenant demo | plan Free | status ACTIVE

usage_events: 10 | invoices: 2 | webhook_events: 0
```

## Probe 4 — App boots; routes registered

```
$ uvicorn app.main:app --port 8777
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Starting Metering Billing Engine...
INFO:     Reconciliation loop started (every 86400s)
INFO:     Application startup complete.

GET /            -> {"message":"Welcome to Metering Billing Engine"}
GET /api/v1/health -> {"status":"healthy","message":"Billing Engine is running"}
```

OpenAPI paths (12) include:

```
/api/v1/health, /api/v1/tenants, /api/v1/plans, /api/v1/subscriptions,
/api/v1/generate, /api/v1/usage, /api/v1/usage/{subscription_id},
/api/v1/billing/{subscription_id}, /api/v1/invoices,
/api/v1/stripe/checkout/{tenant_id}/{plan_id}, /api/v1/webhooks/stripe
```

Exported to `capstone.yaml`.

## Probe 5 — Live API calls against Neon (X-Tenant-Id isolation)

Using demo tenant `16c57711-e45e-4efa-8249-bf948057d7f5`:

```
GET /api/v1/plans  -> Free/Pro plans with per-type limits
                      (api_call_limit 1000/10000, tokens_limit 100k/5M)

GET /api/v1/subscriptions
  -> only subscriptions owned by the demo tenant (3 in DB, 1 returned)

GET /api/v1/invoices
  -> tenant-scoped: {"subscription_id":"acc55c3c-...","plan_price":0,
      "usage_limit":1000,"total_usage":4503,"overage":3503,
      "amount_due":35030,"created_at":"2026-08-12T11:21:58"}
```

Overage example: 4,503 API calls metered against the Free plan's 1,000-call
allowance produced 3,503 overage calls billed at $0.01 each -> $35.03 due.

## Probe 6 — Stripe integration (config gate + tests)

- `stripe_service.py` builds Checkout sessions, verifies webhook signatures,
  deduplicates by `event.id` (persisted in `webhook_events`), and syncs
  plan/status; without keys the app boots and returns a clear 500.
- Covered by `tests/test_stripe_service.py`: signature verification, replay
  dedup, checkout-session mapping, subscription-created/updated/deleted sync,
  price-id plan resolution, customer/subscription id persistence.
