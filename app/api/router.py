from fastapi import APIRouter

from app.api.v1.endpoints import health, tenants, plans, subscriptions, usage, billing
from app.api.v1.endpoints import invoices
api_router = APIRouter()

api_router.include_router(
    health.router,
)
api_router.include_router(tenants.router)

api_router.include_router(plans.router)
api_router.include_router(subscriptions.router)

api_router.include_router(usage.router)

api_router.include_router(
    billing.router
)

api_router.include_router(
    invoices.router,
    prefix="/invoices",
    tags=["Invoices"],
)