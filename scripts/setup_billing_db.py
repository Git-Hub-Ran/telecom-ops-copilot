"""Seed data/billing.db from mock-data/billing.json.

Creates the bills table with full-fidelity schema matching the Bill model.
Safe to run multiple times (uses INSERT OR REPLACE).

Usage:
    python scripts/setup_billing_db.py
"""

import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = PROJECT_ROOT / "mock-data" / "billing.json"
DB_PATH = PROJECT_ROOT / "data" / "billing.db"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS bills (
    bill_id                TEXT PRIMARY KEY,
    account_id             TEXT NOT NULL,
    billing_period_start   TEXT NOT NULL,
    billing_period_end     TEXT NOT NULL,
    issue_date             TEXT NOT NULL,
    due_date               TEXT NOT NULL,
    subtotal               REAL NOT NULL,
    discounts              REAL NOT NULL,
    taxes                  REAL NOT NULL,
    total                  REAL NOT NULL,
    status                 TEXT NOT NULL,
    paid_date              TEXT,
    line_items             TEXT NOT NULL
);
"""

CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_bills_account_date
    ON bills (account_id, issue_date DESC);
"""

INSERT = """
INSERT OR REPLACE INTO bills (
    bill_id, account_id, billing_period_start, billing_period_end,
    issue_date, due_date, subtotal, discounts, taxes, total,
    status, paid_date, line_items
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        records: list[dict] = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(CREATE_TABLE)
        conn.execute(CREATE_INDEX)
        conn.executemany(
            INSERT,
            [
                (
                    r["bill_id"],
                    r["account_id"],
                    r["billing_period_start"],
                    r["billing_period_end"],
                    r["issue_date"],
                    r["due_date"],
                    r["subtotal"],
                    r["discounts"],
                    r["taxes"],
                    r["total"],
                    r["status"],
                    r.get("paid_date"),
                    json.dumps(r["line_items"]),
                )
                for r in records
            ],
        )
        conn.commit()
        print(f"Seeded {len(records)} records into {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
