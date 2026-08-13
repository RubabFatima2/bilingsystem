from fastapi import APIRouter

from app.api.v1.endpoints import (
    billing,
    generate,
    health,
    invoices,
    plans,
    stripe,
    subscriptions,
    tenants,
    usage,
)

api_router = APIRouter()

api_router.include_router(health.router)

api_router.include_router(tenants.router)
api_router.include_router(plans.router)
api_router.include_router(subscriptions.router)

api_router.include_router(generate.router)
api_router.include_router(usage.router)

api_router.include_router(billing.router)

api_router.include_router(
    invoices.router,
    prefix="/invoices",
    tags=["Invoices"],
)

api_router.include_router(stripe.router)
api_router.include_router(stripe.webhook_router)
