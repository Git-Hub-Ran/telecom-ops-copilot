import json
from pathlib import Path


class JSONBillingDataSource:
    def __init__(self, json_path: Path) -> None:
        self._json_path = json_path

    def get_bills(self, account_id: str) -> list[dict]:
        """Return all bills for account_id as plain dicts, unsorted."""
        with open(self._json_path, "r", encoding="utf-8") as f:
            all_bills: list[dict] = json.load(f)
        return [b for b in all_bills if b["account_id"] == account_id]
