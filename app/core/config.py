from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Metering Billing Engine"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str

    # Stripe test-mode. Both are optional so the app boots (and unit tests
    # run) without a Stripe account; checkout/webhook endpoints fail with a
    # clear 500 until they are configured.
    STRIPE_API_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    STRIPE_SUCCESS_URL: str = "http://localhost:8000/success"
    STRIPE_CANCEL_URL: str = "http://localhost:8000/cancel"

    # Background reconciliation loop. Set to 0 to disable.
    RECONCILE_INTERVAL_SECONDS: int = 86400

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
    )


# DATABASE_URL comes from .env at runtime (or pytest's conftest in tests);
# there is intentionally no default so a missing config fails fast.
settings = Settings()  # type: ignore[call-arg]