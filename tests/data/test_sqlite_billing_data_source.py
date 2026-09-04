"""Unit tests for SQLiteBillingDataSource."""

import json
import sqlite3
from pathlib import Path

import pytest

from src.data.sqlite_billing_data_source import SQLiteBillingDataSource

CREATE_TABLE = """
CREATE TABLE bills (
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

FIXTURE_ROWS = [
    (
        "BILL-10001-202605", "ACC-10001",
        "2026-05-04", "2026-06-03", "2026-05-04", "2026-05-25",
        25.0, -5.0, 2.0, 22.0, "paid", "2026-05-22",
        json.dumps([{"description": "Essential plan", "amount": 25.0}]),
    ),
    (
        "BILL-10001-202604", "ACC-10001",
        "2026-04-04", "2026-05-03", "2026-04-04", "2026-04-25",
        25.0, -5.0, 2.0, 22.0, "paid", "2026-04-22",
        json.dumps([{"description": "Essential plan", "amount": 25.0}]),
    ),
    (
        "BILL-10002-202605", "ACC-10002",
        "2026-05-04", "2026-06-03", "2026-05-04", "2026-05-25",
        60.0, -10.0, 4.0, 54.0, "unpaid", None,
        json.dumps([{"description": "Premium plan", "amount": 60.0}]),
    ),
]

INSERT = """
INSERT INTO bills VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test_billing.db"
    conn = sqlite3.connect(path)
    conn.execute(CREATE_TABLE)
    conn.executemany(INSERT, FIXTURE_ROWS)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def source(db_path: Path) -> SQLiteBillingDataSource:
    return SQLiteBillingDataSource(db_path)


class TestSQLiteBillingDataSource:
    def test_returns_bills_for_known_account(self, source):
        bills = source.get_bills("ACC-10001")
        assert len(bills) == 2
        assert all(b["account_id"] == "ACC-10001" for b in bills)

    def test_returns_empty_for_unknown_account(self, source):
        assert source.get_bills("ACC-99999") == []

    def test_returns_bills_in_issue_date_desc_order(self, source):
        bills = source.get_bills("ACC-10001")
        assert bills[0]["issue_date"] >= bills[1]["issue_date"]

    def test_line_items_deserialized_as_list(self, source):
        bills = source.get_bills("ACC-10001")
        assert all(isinstance(b["line_items"], list) for b in bills)

    def test_returned_records_are_dicts(self, source):
        bills = source.get_bills("ACC-10001")
        assert all(isinstance(b, dict) for b in bills)

    def test_does_not_return_other_accounts(self, source):
        bills = source.get_bills("ACC-10001")
        assert all(b["account_id"] == "ACC-10001" for b in bills)

    def test_nullable_paid_date_is_none(self, source):
        bills = source.get_bills("ACC-10002")
        assert len(bills) == 1
        assert bills[0]["paid_date"] is None
