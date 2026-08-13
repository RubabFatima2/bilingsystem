from fastapi import HTTPException


class ResourceNotFoundException(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=404, detail=detail)


class QuotaExceededException(HTTPException):
    """Raised when a billable action would exceed the plan's usage limit.

    Maps to HTTP 429 Too Many Requests with a Retry-After hint, per the
    capstone brief's "honest API boundaries" requirement. Retry-After
    defaults to 3600s until a real billing-period reset can be computed.
    """

    def __init__(
        self,
        detail: str = "Usage quota exceeded",
        retry_after: int = 3600,
    ):
        super().__init__(
            status_code=429,
            detail=detail,
            headers={"Retry-After": str(retry_after)},
        )


class SubscriptionNotActiveException(HTTPException):
    """Raised when a subscription is not active (cancelled / past due).

    Maps to HTTP 402 Payment Required — the action needs an upgrade or
    payment before it can proceed.
    """

    def __init__(self, detail: str = "Subscription is not active"):
        super().__init__(status_code=402, detail=detail)
