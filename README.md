# Metering & Billing Engine

A production-style **usage metering and billing engine** for AI API platforms.
It meters two kinds of billable activity — API calls and AI tokens — enforces
per-plan quotas, computes usage-based bills with overage pricing, generates
monthly invoices, and manages subscriptions through **Stripe** (test mode),
including signed webhooks and a nightly reconciliation job.

The engine is designed for **multi-tenant** use: every tenant-scoped request
identifies itself via an `X-Tenant-Id` header and is verified against
subscription ownership before any action.

---

## Table of Contents

- [Highlights](#highlights)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Data Model](#data-model)
- [Pricing Model](#pricing-model)
- [Getting Started](#getting-started)
- [Configuration Reference](#configuration-reference)
- [API Reference](#api-reference)
- [Stripe Integration](#stripe-integration)
- [Background Jobs](#background-jobs)
- [Error Handling](#error-handling)
- [Idempotency & Exactly-Once Semantics](#idempotency--exactly-once-semantics)
- [Testing & Quality](#testing--quality)
- [Deployment](#deployment)
- [Security Considerations](#security-considerations)
- [Evidence](#evidence)
- [License](#license)

---

## Highlights

- **Per-type metering** — plans meter `API_CALL` and `TOKENS` usage separately,
  each with its own monthly limit (`api_call_limit`, `tokens_limit`).
- **Exactly-once usage recording** — idempotency keys plus a database unique
  constraint guarantee retries never double-count, even under concurrency.
- **Float-free money** — all money is stored and computed as integers
  (cents in the invoice/billing layer, micro-units in the cost engine).
  No `float` ever enters the money path.
- **Overage billing** — bills include base plan price plus per-unit overage
  beyond the included allowance.
- **Tenant isolation** — `X-Tenant-Id` header + ownership checks enforce
  403 on cross-tenant access.
- **Stripe (test mode)** — hosted Checkout, signed webhooks with replay
  protection, plan/status sync, and a resilient reconciliation loop.
- **Honest API boundaries** — HTTP status codes and `Retry-After` headers
  communicate quota exhaustion (429), inactive subscriptions (402), and
  missing resources (404) instead of leaking 500s.

---

## Features

### Usage Metering

- Record **API-call usage** with `POST /api/v1/usage`.
- Record **AI token usage** with `POST /api/v1/generate` (a dummy billable
  endpoint that meters one AI response). Token categories are validated so
  callers cannot record token usage under the API-call type.
- List usage for a tenant, and get a per-subscription monthly **rollup**
  (`used` / `limit` / `cost`) via `GET /api/v1/usage/{subscription_id}`.

### Quota Enforcement

- Each plan defines independent monthly limits for API calls and tokens.
- Requests that **exceed** a limit are rejected with `429 Too Many Requests`
  and a `Retry-After` header. Requests landing *exactly* on the limit are
  allowed (boundary rule).
- Inactive (cancelled / past-due) subscriptions are rejected with
  `402 Payment Required`.

### Billing & Invoicing

- `GET /api/v1/billing/{subscription_id}` computes the current month's bill:
  plan price + overage × overage rate.
- One **invoice per subscription per billing period**; the billing period is
  the current calendar month. Recomputing the same period returns the stored
  invoice instead of creating a duplicate.
- Tenant-scoped invoice listing via `GET /api/v1/invoices`.

### Stripe Integration

- `GET /api/v1/stripe/checkout/{tenant_id}/{plan_id}` returns a hosted Stripe
  Checkout URL that creates a subscription.
- `POST /api/v1/webhooks/stripe` verifies the `Stripe-Signature`, deduplicates
  events by `event.id` (persisted in a `webhook_events` table), and syncs the
  tenant's plan and subscription status.
- A **nightly reconciliation job** re-reads every Stripe-linked subscription
  and syncs status/plan from Stripe — catching webhooks that were missed.

---

## Architecture

The application follows a **layered** architecture with dependency injection:

```
            ┌────────────────────────────── HTTP ──────────────────────────────┐
            │                                                                 │
            ▼                                                                 │
┌───────────────────────┐    ┌──────────────────────┐    ┌────────────────────┐
│   API Layer            │    │   Service Layer       │    │ Repository Layer  │
│ FastAPI routers        │──▶ │ business rules        │──▶ │ SQLAlchemy queries│
│ auth via dependencies  │    │ quotas, billing, cost │    │ single-table access│
└───────────────────────┘    └──────────────────────┘    └────────────────────┘
            │                                                  │
            │ tenant isolation                                 │
            ▼                                                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                                PostgreSQL (Neon)                             │
│  tenants · plans · subscriptions · usage_events · invoices · webhook_events  │
└──────────────────────────────────────────────────────────────────────────────┘
            ▲
            │ background task (asyncio)
┌───────────────────────┐
│  Reconciliation loop   │  every RECONCILE_INTERVAL_SECONDS
│  syncs DB ↔ Stripe     │  retries w/ exponential backoff, logs failures
└───────────────────────┘
```

**Request flow** (example: `POST /api/v1/generate`):

1. FastAPI dependency extracts `X-Tenant-Id` from the header (400 if invalid
   UUID).
2. The route verifies the caller owns the referenced subscription
   (403 otherwise).
3. `GenerateService` records a token usage event through `UsageService`.
4. `UsageService` short-circuits on a duplicate idempotency key, validates the
   subscription is active (402), and enforces the plan's token quota (429).
5. `CostService` converts the metered token categories into a price using
   integer micro-unit rates (reasoning tokens billed as output, cached input
   cheaper, per-1k blocks rounded up).
6. The response returns the recorded event plus the computed cost.

---

## Tech Stack

| Concern       | Technology                                              |
| ------------- | ------------------------------------------------------- |
| API framework | FastAPI + Pydantic v2                                   |
| ORM           | SQLAlchemy 2.0 (typed `Mapped`/`mapped_column`)         |
| Migrations    | Alembic                                                 |
| Database      | PostgreSQL (development against Neon serverless PG)     |
| Payments      | Stripe SDK (test mode)                                  |
| Background    | asyncio task inside FastAPI lifespan                    |
| Language      | Python 3.14+                                            |
| Tooling       | uv, ruff (lint + format), mypy, pytest                  |

---

## Project Structure

```
.
├── alembic/
│   ├── versions/                # schema migrations (6 revisions)
│   └── env.py
├── app/
│   ├── api/v1/endpoints/        # HTTP routes
│   │   ├── health.py            #   GET /health
│   │   ├── tenants.py           #   tenants CRUD
│   │   ├── plans.py             #   plans CRUD
│   │   ├── subscriptions.py     #   subscriptions CRUD
│   │   ├── generate.py          #   POST /generate (billable endpoint)
│   │   ├── usage.py             #   metering + rollup
│   │   ├── billing.py           #   bill calculation
│   │   ├── invoices.py          #   tenant-scoped invoices
│   │   └── stripe.py            #   checkout + webhook
│   ├── constants/               # pricing, usage types, subscription status
│   ├── core/                    # config (pydantic-settings), exceptions, logging
│   ├── db/                      # engine, session, Base
│   ├── dependencies/            # X-Tenant-Id auth + ownership checks
│   ├── integrations/            # Stripe client construction
│   ├── models/                  # SQLAlchemy ORM models
│   ├── repositories/            # data-access layer
│   ├── schemas/                 # Pydantic request/response models
│   ├── services/                # business logic
│   └── utils/                   # date helpers (month bounds)
├── scripts/
│   └── seed.py                  # idempotent demo-data seeder
├── tests/                       # 35 pytest tests
├── capstone.yaml                # exported OpenAPI specification
├── BUILDLOG.md                  # incremental build record
├── EVIDENCE.md                  # probe results against the live system
├── .env.example                 # environment variable template
└── pyproject.toml
```

---

## Data Model

```
tenants
  id (PK, UUID), name, email (unique), is_active, created_at*

plans
  id (PK, UUID), name (unique), price (cents), usage_limit,
  api_call_limit, tokens_limit, stripe_price_id, stripe_product_id,
  is_active, created_at*

subscriptions
  id (PK, UUID), tenant_id (FK), plan_id (FK), status (enum),
  stripe_customer_id, stripe_subscription_id (unique),
  started_at, created_at*

usage_events
  id (PK, UUID), subscription_id (FK), usage_type (enum),
  quantity, cached_input_tokens, input_tokens, output_tokens,
  reasoning_tokens, idempotency_key (unique), created_at

invoices
  id (PK, UUID), subscription_id (FK), plan_price, usage_limit,
  total_usage, overage, amount_due, period_start, period_end, created_at

webhook_events
  id (PK, UUID), event_id (unique), event_type, created_at
```

- **money as integers**: `price`, `plan_price`, `amount_due`, `overage`, and
  the cost-engine outputs are integer cents / micro-units — never floats.
- **cost is recomputable**: token usage events store the raw token breakdown
  (`cached_input_tokens`, `input_tokens`, `output_tokens`,
  `reasoning_tokens`) so cost is always derivable from metered data using the
  pricing rules in the cost engine, rather than from stored money.

---

## Pricing Model

Rates are pinned in `app/constants/pricing.py` and converted once to integer
**micro-units** (1/10,000 of a cent) so cost math never touches floats.

| Item                    | Rate (per 1k) |
| ----------------------- | ------------- |
| Cached input tokens     | $0.10         |
| Fresh input tokens      | $0.30         |
| Output tokens           | $0.60         |
| Reasoning tokens        | $0.60 (billed as output) |
| API calls               | $2.00         |

Pricing rules:

- **Reasoning tokens are billed as output tokens** — they are added to the
  output bucket *before* pricing, at the output rate.
- **Cached input is cheaper** than fresh input and is priced separately.
- **Per-category pricing** — each token category is priced with its own
  per-1k rate and then summed; raw token counts are never added together
  across categories.
- **Whole-block rounding** — per-1k blocks round *up* (`ceil`), so a partial
  block pays the full block rate. Exact at block boundaries.

### Billing (invoice layer)

`GET /api/v1/billing/{subscription_id}` computes, for the current calendar
month:

```
total_usage = Σ usage_events.quantity (in period)
overage     = max(total_usage − plan.usage_limit, 0)
amount_due  = plan.price + overage × OVERAGE_PRICE      # OVERAGE_PRICE = 10 cents
```

The result is persisted as an invoice; repeating the calculation for the same
subscription and period returns the stored invoice (deduplication).

---

## Getting Started

### Prerequisites

- Python 3.14+
- PostgreSQL (or a compatible service such as Neon)
- Optional: a Stripe **test-mode** account (for checkout/webhook/reconciliation)

### Setup

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment
cp .env.example .env
#   set DATABASE_URL to your Postgres connection string
#   optionally add STRIPE_API_KEY and STRIPE_WEBHOOK_SECRET (test mode)

# 3. Apply database migrations
uv run alembic upgrade head

# 4. Seed demo data (Free/Pro plans, demo tenant, active subscription)
uv run python scripts/seed.py
#   prints the demo tenant id — use it as the X-Tenant-Id header value

# 5. Start the server
uv run uvicorn app.main:app --reload
```

Interactive API docs: <http://localhost:8000/docs>
OpenAPI specification: <http://localhost:8000/openapi.json> (also exported to
`capstone.yaml`).

### Demo walkthrough

```bash
# --- 1. Create a tenant -----------------------------------------------------
TENANT=$(curl -s -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "Acme Corp", "email": "acme@example.com"}' | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# --- 2. Create a plan -------------------------------------------------------
PRO_PLAN=$(curl -s -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -d '{"name":"Pro","price":5000,"usage_limit":10000,"api_call_limit":10000,"tokens_limit":5000000}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# --- 3. Subscribe the tenant ------------------------------------------------
SUBSCRIPTION=$(curl -s -X POST http://localhost:8000/api/v1/subscriptions \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"$TENANT\",\"plan_id\":\"$PRO_PLAN\"}" \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# --- 4. Record 500 API-call usages (idempotent) -----------------------------
curl -X POST http://localhost:8000/api/v1/usage \
  -H "Content-Type: application/json" -H "X-Tenant-Id: $TENANT" \
  -d "{\"subscription_id\":\"$SUBSCRIPTION\",\"usage_type\":\"API_CALL\",\"quantity\":500,\"idempotency_key\":\"demo-1\"}"

# --- 5. Record one AI response (token usage) --------------------------------
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" -H "X-Tenant-Id: $TENANT" \
  -d "{\"subscription_id\":\"$SUBSCRIPTION\",\"cached_input_tokens\":1000,\"input_tokens\":2000,\"output_tokens\":1500,\"reasoning_tokens\":500,\"idempotency_key\":\"demo-2\"}"

# --- 6. Inspect usage rollup, the bill, and invoices ------------------------
curl -H "X-Tenant-Id: $TENANT" http://localhost:8000/api/v1/usage/$SUBSCRIPTION
curl -H "X-Tenant-Id: $TENANT" http://localhost:8000/api/v1/billing/$SUBSCRIPTION
curl -H "X-Tenant-Id: $TENANT" http://localhost:8000/api/v1/invoices
```

---

## Configuration Reference

All settings are read from environment variables (`.env` supported) via
`app/core/config.py`. There is **no default for `DATABASE_URL`** so a missing
configuration fails fast on startup.

| Variable                     | Default                  | Description                                    |
| ---------------------------- | ------------------------ | ---------------------------------------------- |
| `APP_NAME`                   | `Metering Billing Engine`| Application display name                       |
| `APP_VERSION`                | `1.0.0`                  | API version                                    |
| `DEBUG`                      | `true`                   | Enables SQL echo / FastAPI debug mode          |
| `DATABASE_URL`               | *(required)*             | SQLAlchemy URL, e.g. `postgresql+psycopg://…`  |
| `STRIPE_API_KEY`             | *(optional)*             | Stripe test-mode secret key                    |
| `STRIPE_WEBHOOK_SECRET`      | *(optional)*             | Stripe webhook signing secret (`whsec_…`)      |
| `STRIPE_SUCCESS_URL`         | `http://localhost:8000/success` | Redirect after successful checkout      |
| `STRIPE_CANCEL_URL`          | `http://localhost:8000/cancel`  | Redirect after cancelled checkout       |
| `RECONCILE_INTERVAL_SECONDS` | `86400`                  | Reconciliation loop period (0 disables it)     |

> Stripe settings are intentionally optional: the application boots and all
> non-Stripe endpoints work without a Stripe account. Checkout and webhook
> endpoints return a clear `500` with a descriptive message when keys are
> missing.

---

## API Reference

All routes are mounted under the `/api/v1` prefix. Tenant-scoped endpoints
require the `X-Tenant-Id` header (a UUID).

### Health

| Method | Path          | Auth      | Description         |
| ------ | ------------- | --------- | ------------------- |
| GET    | `/`           | none      | Welcome message     |
| GET    | `/api/v1/health` | none   | Liveness probe      |

`GET /api/v1/health`
```json
{ "status": "healthy", "message": "Billing Engine is running" }
```

### Tenants

| Method | Path                | Auth | Description                         |
| ------ | ------------------- | ---- | ----------------------------------- |
| POST   | `/api/v1/tenants`   | none | Create a tenant                     |
| GET    | `/api/v1/tenants`   | none | List tenants                        |

`POST /api/v1/tenants` — request:
```json
{ "name": "Acme Corp", "email": "acme@example.com" }
```
Response:
```json
{ "id": "…uuid…", "name": "Acme Corp", "email": "acme@example.com", "is_active": true }
```
`400` if the email already exists.

### Plans

| Method | Path              | Auth | Description                       |
| ------ | ----------------- | ---- | --------------------------------- |
| POST   | `/api/v1/plans`   | none | Create a plan                     |
| GET    | `/api/v1/plans`   | none | List plans                        |

`POST /api/v1/plans` — request:
```json
{
  "name": "Pro",
  "price": 5000,
  "usage_limit": 10000,
  "api_call_limit": 10000,
  "tokens_limit": 5000000,
  "stripe_price_id": null,
  "stripe_product_id": null
}
```
`400` if the plan name already exists.

### Subscriptions

| Method | Path                      | Auth | Description              |
| ------ | ------------------------- | ---- | ------------------------ |
| POST   | `/api/v1/subscriptions`   | none | Create a subscription    |
| GET    | `/api/v1/subscriptions`   | none | List subscriptions       |

`POST /api/v1/subscriptions` — request:
```json
{ "tenant_id": "…uuid…", "plan_id": "…uuid…" }
```
Response: `{ "id": "…", "tenant_id": "…", "plan_id": "…", "status": "active" }`

### Generate (billable endpoint)

| Method | Path                 | Auth | Description                          |
| ------ | -------------------- | ---- | ------------------------------------ |
| POST   | `/api/v1/generate`   | `X-Tenant-Id` | Meter one AI response + compute cost |

`POST /api/v1/generate` — request:
```json
{
  "subscription_id": "…uuid…",
  "cached_input_tokens": 1000,
  "input_tokens": 2000,
  "output_tokens": 1500,
  "reasoning_tokens": 500,
  "idempotency_key": "req-123"
}
```
`quantity` is derived automatically from the token categories (total tokens).
Response:
```json
{
  "usage_event": { "id": "…", "subscription_id": "…", "usage_type": "tokens", "quantity": 5000 },
  "cost_micro": 19000,
  "cost_cents": 1.9
}
```
(`quantity` = 5000 total tokens. Cost: cached 1×$0.10 + fresh 2×$0.30 +
output/reasoning 2×$0.60 = $1.90 = 19,000 micro-units.)

### Usage

| Method | Path                           | Auth | Description                          |
| ------ | ------------------------------ | ---- | ------------------------------------ |
| POST   | `/api/v1/usage`                | `X-Tenant-Id` | Record API-call usage      |
| GET    | `/api/v1/usage`                | `X-Tenant-Id` | List tenant usage          |
| GET    | `/api/v1/usage/{subscription_id}` | `X-Tenant-Id` | Monthly rollup (used/limit/cost) |

`POST /api/v1/usage` — request:
```json
{
  "subscription_id": "…uuid…",
  "usage_type": "API_CALL",
  "quantity": 100,
  "idempotency_key": "req-456"
}
```

`GET /api/v1/usage/{subscription_id}` — response:
```json
{
  "subscription_id": "…",
  "plan_id": "…",
  "used_api_calls": 500,
  "api_call_limit": 10000,
  "used_tokens": 5000,
  "tokens_limit": 5000000,
  "cost_micro": 1000,
  "cost_cents": 0.1
}
```

### Billing

| Method | Path                              | Auth | Description                    |
| ------ | --------------------------------- | ---- | ------------------------------ |
| GET    | `/api/v1/billing/{subscription_id}` | `X-Tenant-Id` | Compute current month's bill |

Response:
```json
{
  "subscription_id": "…",
  "plan_price": 5000,
  "usage_limit": 10000,
  "total_usage": 12345,
  "overage": 2345,
  "amount_due": 28450
}
```

### Invoices

| Method | Path                | Auth | Description          |
| ------ | ------------------- | ---- | -------------------- |
| GET    | `/api/v1/invoices`  | `X-Tenant-Id` | List the tenant's invoices |

Response (array):
```json
[
  {
    "id": "…",
    "subscription_id": "…",
    "plan_price": 5000,
    "usage_limit": 10000,
    "total_usage": 12345,
    "overage": 2345,
    "amount_due": 28450,
    "created_at": "2026-08-13T12:00:00"
  }
]
```

### Stripe

| Method | Path                                        | Auth | Description                    |
| ------ | ------------------------------------------- | ---- | ------------------------------ |
| GET    | `/api/v1/stripe/checkout/{tenant_id}/{plan_id}` | `X-Tenant-Id` | Create a Checkout session, return hosted URL |
| POST   | `/api/v1/webhooks/stripe`                   | none (signature-verified) | Receive Stripe events |

`GET /api/v1/stripe/checkout/{tenant_id}/{plan_id}` — the path tenant must
match the `X-Tenant-Id` header (403 otherwise). Returns the hosted Checkout
URL as a plain string.

`POST /api/v1/webhooks/stripe` — Stripe posts signed JSON with a
`Stripe-Signature` header. The signature is verified (400 on mismatch),
events are deduplicated by id, and handled event types are:
`checkout.session.completed`, `customer.subscription.updated`,
`customer.subscription.deleted`.

---

## Stripe Integration

The engine works against Stripe **test mode** (e.g. the Stripe CLI):

1. Create test-mode products and prices in the Stripe dashboard.
2. Set `plan.stripe_price_id` (and optionally `stripe_product_id`) on each
   plan.
3. Set `STRIPE_API_KEY` and `STRIPE_WEBHOOK_SECRET` in `.env`.
4. Point a webhook endpoint at `POST /api/v1/webhooks/stripe`.
5. `GET /api/v1/stripe/checkout/{tenant_id}/{plan_id}` returns the hosted
   checkout URL; completing it fires `checkout.session.completed`, which
   creates/updates the tenant's subscription and stores the Stripe customer
   and subscription ids.

Webhook handling is **atomic and idempotent**:

- A marker row is inserted into `webhook_events` (unique on `event_id`)
  *in the same transaction* as the subscription changes. If processing
  fails, the whole transaction rolls back and Stripe's automatic retry
  reprocesses safely.
- Replayed event ids are no-ops, even across process restarts.

The `StripeService` and `ReconciliationService` accept an injected client,
so tests exercise the full flow against a fake.

---

## Background Jobs

**Reconciliation loop** (`app/services/reconciliation_service.py`):

- Runs as an asyncio task during the FastAPI lifespan, every
  `RECONCILE_INTERVAL_SECONDS` (default 24h).
- Re-reads every subscription that has a `stripe_subscription_id` and syncs
  its status/plan from Stripe, catching webhooks that were missed or dropped.
- Retries transient Stripe errors with exponential backoff (3 attempts,
  doubling delay) and logs every failure as the alert channel.
- Idempotent — safe to run twice.
- `RECONCILE_INTERVAL_SECONDS=0` disables it entirely.

---

## Error Handling

| Status | Meaning                                        | Typical source                       |
| ------ | ---------------------------------------------- | ------------------------------------ |
| 400    | Bad request / invalid `X-Tenant-Id` / duplicate plan or email | header validation, uniqueness |
| 402    | Payment required — subscription not active     | `SubscriptionNotActiveException`     |
| 403    | Cross-tenant access attempt                    | ownership check                      |
| 404    | Subscription or plan not found                 | `ResourceNotFoundException`          |
| 429    | Quota exceeded (includes `Retry-After: 3600`)  | `QuotaExceededException`             |
| 500    | Missing Stripe configuration or unexpected failure | checkout/webhook with no keys   |

`Retry-After` defaults to `3600` seconds (one hour) until a real billing-period
reset can be computed.

---

## Idempotency & Exactly-Once Semantics

Usage recording is exactly-once:

1. **Application layer** — `UsageService.record_usage` short-circuits when an
   event with the same `idempotency_key` already exists, returning the
   original event (no new row, no quota re-check, no double count).
2. **Database layer** — a unique constraint on `usage_events.idempotency_key`
   is the real guard under concurrency. If two requests race the insert, the
   winner's row wins and the loser re-reads the committed row instead of
   failing (`UsageRepository.create` catches `IntegrityError`).

Retrying `POST /api/v1/generate` with the same idempotency key returns the
original event with cost recomputed from the stored token breakdown — a mirror
response with identical values.

---

## Testing & Quality

```bash
uv run pytest                # 35 tests
uv run ruff check .          # lint
uv run ruff format --check . # formatting
uv run mypy app              # static type checking
```

Current status: **35 passed**, ruff clean, mypy clean (64 source files).

Test coverage focuses on the business-critical paths:

- `test_usage_service.py` — quota enforcement, boundary rule, active-status
  requirement, idempotency deduplication.
- `test_cost_service.py` — micro-unit pricing, per-category rates, reasoning
  billed as output, cached-input discount, whole-block rounding.
- `test_billing_service.py` — bill math, overage, invoice deduplication per
  period.
- `test_generate_service.py` — end-to-end metering + cost for one response.
- `test_stripe_service.py` — signature verification, replay dedup, checkout
  mapping, subscription status/plan sync, cancellation.
- `test_reconciliation_service.py` — retry/backoff, status sync, failure
  isolation between subscriptions.

Tests use an in-memory database and injected fakes; no external services are
required.

---

## Deployment

The app is a standard FastAPI/uvicorn service that can run anywhere Python is
available:

```bash
# Production-style start (no reload, multiple workers)
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

Considerations for production:

- Set `DEBUG=false` to disable SQL echo.
- Run `alembic upgrade head` as part of the deploy pipeline before starting
  workers.
- Store secrets in your platform's secret manager; `DATABASE_URL` should not
  be committed.
- Set `RECONCILE_INTERVAL_SECONDS` to the desired cadence (or `0` to run
  reconciliation as an external cron job instead of an in-process task).
- For multi-worker deployments, in-process asyncio jobs run once per worker;
  prefer an external scheduler (e.g. cron/APScheduler) for the reconciliation
  job to avoid duplicate runs.

---

## Security Considerations

- **Multi-tenant isolation** — every tenant-scoped endpoint requires the
  `X-Tenant-Id` header; `get_owned_subscription` rejects access to another
  tenant's subscription with `403`.
- **Webhook signature verification** — Stripe webhooks are verified against
  `STRIPE_WEBHOOK_SECRET`; forged signatures are rejected with `400`.
- **No secrets in code** — all configuration lives in environment variables;
  `.env` is gitignored.
- **Integer money** — monetary math uses integers, eliminating float
  rounding/representation errors in billing.

---

## Evidence

`EVIDENCE.md` records probe results against the deployed app and shared Neon
database: the migration chain applied to head, seeded demo data, app boot and
route registration, live tenant-scoped API calls (including a concrete overage
example — 4,503 calls against a 1,000-call allowance produced 3,503 overage
calls billed at $0.01 each = $35.03), and Stripe integration tests.

`BUILDLOG.md` documents the incremental build history.

---

## License

MIT — see [`LICENSE`](LICENSE).
