from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_tenant_id
from app.integrations.stripe import get_stripe_client
from app.services.stripe_service import StripeService

router = APIRouter(
    prefix="/stripe",
    tags=["Stripe"],
)

webhook_router = APIRouter(
    tags=["Stripe Webhooks"],
)


@router.get("/checkout/{tenant_id}/{plan_id}", response_model=str)
def checkout(
    tenant_id: UUID,
    plan_id: UUID,
    db: Session = Depends(get_db),
    header_tenant: UUID = Depends(get_current_tenant_id),
):
    if tenant_id != header_tenant:
        raise HTTPException(
            status_code=403,
            detail="Checkout tenant does not match X-Tenant-Id",
        )

    service = StripeService(db=db, stripe_client=get_stripe_client(required=True))
    return service.create_checkout_session(
        tenant_id=tenant_id,
        plan_id=plan_id,
    )


@webhook_router.post("/webhooks/stripe", response_model=dict)
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """Verify Stripe signature and process the event (idempotent)."""
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    service = StripeService(db=db, stripe_client=get_stripe_client(required=True))
    service.handle_webhook(payload=payload, sig_header=sig_header)
    return {"status": "ok"}
