import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import logger
from app.db.session import SessionLocal
from app.integrations.stripe import get_stripe_client
from app.services.reconciliation_service import ReconciliationService


async def _reconciliation_loop() -> None:
    """Periodic background job syncing our DB with Stripe's view.

    Runs off the request path; transient failures are retried inside
    ReconciliationService and logged as the alert channel.
    """
    logger.info(
        "Reconciliation loop started (every %ss)",
        settings.RECONCILE_INTERVAL_SECONDS,
    )
    while True:
        try:
            with SessionLocal() as db:
                synced = ReconciliationService(
                    db, get_stripe_client()
                ).run_once()
            if synced:
                logger.info("Reconciliation synced %s subscription(s)", synced)
        except Exception:  # noqa: BLE001 - the loop must never die
            logger.exception("Reconciliation run failed")
        await asyncio.sleep(settings.RECONCILE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Metering Billing Engine...")

    reconcile_task = None
    if settings.RECONCILE_INTERVAL_SECONDS > 0:
        reconcile_task = asyncio.create_task(_reconciliation_loop())

    yield

    if reconcile_task is not None:
        reconcile_task.cancel()
        try:
            await reconcile_task
        except asyncio.CancelledError:
            pass
    logger.info("Shutting down Metering Billing Engine...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}"
    }
