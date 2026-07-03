from typing import Protocol, runtime_checkable


@runtime_checkable
class BillingDataSource(Protocol):
    def get_bills(self, account_id: str) -> list[dict]:
        """Return all bills for account_id as plain dicts."""
        ...
