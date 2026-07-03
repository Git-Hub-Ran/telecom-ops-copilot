import json
import sqlite3
from pathlib import Path


class SQLiteBillingDataSource:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def get_bills(self, account_id: str) -> list[dict]:
        """Return all bills for account_id as plain dicts, issue_date DESC."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM bills WHERE account_id = ? ORDER BY issue_date DESC",
                (account_id,),
            ).fetchall()
            result = []
            for row in rows:
                record = dict(row)
                record["line_items"] = json.loads(record["line_items"])
                result.append(record)
            return result
        finally:
            conn.close()
