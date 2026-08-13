from enum import Enum


class UsageType(str, Enum):
    """The two billable activity types every plan meters separately."""

    API_CALL = "api_call"
    TOKENS = "tokens"
