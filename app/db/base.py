from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models after Base has been defined.
from app.models.tenant import Tenant
from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.usage_event import UsageEvent