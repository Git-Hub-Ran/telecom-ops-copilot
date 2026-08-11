"""Tests for billing information lookup tool."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import PROJECT_ROOT
from src.tools.billing import get_billing_info

_CREATE_BILLS_TABLE = """
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

_SQLITE_FIXTURE_ROW = (
    "BILL-10001-202605", "ACC-10001",
    "2026-05-04", "2026-06-03", "2026-05-04", "2026-05-25",
    25.0, -5.0, 2.0, 22.0, "paid", "2026-05-22",
    json.dumps([{"description": "Essential plan", "amount": 25.0}]),
)


class TestGetBillingInfo:
    """Test suite for get_billing_info function."""

    def test_valid_account_returns_success_with_default_months(self):
        """Test that a valid account_id returns success with 3 bills by default."""
        result = get_billing_info("ACC-10001")

        assert result.success is True
        assert result.billing_info is not None
        assert result.error_code is None
        assert result.error_message is None

        # Verify billing info structure
        assert result.billing_info.account_id == "ACC-10001"
        assert result.billing_info.total_bills == 3
        assert len(result.billing_info.bills) == 3

        # Verify bills are sorted by issue_date descending (most recent first)
        bills = result.billing_info.bills
        assert bills[0].issue_date >= bills[1].issue_date
        assert bills[1].issue_date >= bills[2].issue_date

    def test_bill_structure_contains_all_fields(self):
        """Test that returned bills contain all expected fields."""
        result = get_billing_info("ACC-10001")

        assert result.success is True
        bill = result.billing_info.bills[0]

        # Verify all bill fields are present
        assert bill.bill_id.startswith("BILL-")
        assert bill.account_id == "ACC-10001"
        assert bill.billing_period_start is not None
        assert bill.billing_period_end is not None
        assert bill.issue_date is not None
        assert bill.due_date is not None
        assert isinstance(bill.subtotal, (int, float))
        assert isinstance(bill.discounts, (int, float))
        assert isinstance(bill.taxes, (int, float))
        assert isinstance(bill.total, (int, float))
        assert bill.status in ["paid", "unpaid", "overdue", "scheduled"]
        assert len(bill.line_items) > 0

    def test_line_items_structure(self):
        """Test that line items have correct structure."""
        result = get_billing_info("ACC-10001")

        assert result.success is True
        line_items = result.billing_info.bills[0].line_items

        for item in line_items:
            assert isinstance(item.description, str)
            assert isinstance(item.amount, (int, float))

    def test_custom_months_parameter(self):
        """Test retrieving different numbers of months."""
        # Request 1 month
        result = get_billing_info("ACC-10001", months=1)
        assert result.success is True
        assert result.billing_info.total_bills == 1
        assert len(result.billing_info.bills) == 1

        # Request 2 months
        result = get_billing_info("ACC-10001", months=2)
        assert result.success is True
        assert result.billing_info.total_bills == 2
        assert len(result.billing_info.bills) == 2

    def test_months_parameter_exceeds_available_bills(self):
        """Test requesting more months than available bills."""
        result = get_billing_info("ACC-10001", months=12)

        assert result.success is True
        # Should return all available bills (3 for ACC-10001), not 12
        assert result.billing_info.total_bills == 3
        assert len(result.billing_info.bills) == 3

    def test_account_with_overdue_bills(self):
        """Test account with overdue bill status."""
        result = get_billing_info("ACC-10004")

        assert result.success is True
        assert result.billing_info.total_bills == 3

        # ACC-10004 has overdue bills
        statuses = [bill.status for bill in result.billing_info.bills]
        assert "overdue" in statuses

    def test_account_with_unpaid_bills(self):
        """Test account with unpaid bill status."""
        result = get_billing_info("ACC-10003")

        assert result.success is True
        bills = result.billing_info.bills

        # Find unpaid bill
        unpaid_bills = [b for b in bills if b.status == "unpaid"]
        assert len(unpaid_bills) > 0

        # Unpaid bills should have null paid_date
        for bill in unpaid_bills:
            assert bill.paid_date is None

    def test_account_with_paid_bills(self):
        """Test that paid bills have paid_date set."""
        result = get_billing_info("ACC-10001")

        assert result.success is True
        bills = result.billing_info.bills

        # Find paid bills
        paid_bills = [b for b in bills if b.status == "paid"]
        assert len(paid_bills) > 0

        # Paid bills should have paid_date
        for bill in paid_bills:
            assert bill.paid_date is not None

    def test_account_with_scheduled_bills(self):
        """Test account with scheduled (future) bills."""
        result = get_billing_info("ACC-10001")

        assert result.success is True
        bills = result.billing_info.bills

        # ACC-10001 has a scheduled bill
        scheduled_bills = [b for b in bills if b.status == "scheduled"]
        assert len(scheduled_bills) > 0

        # Scheduled bills should have null paid_date
        for bill in scheduled_bills:
            assert bill.paid_date is None

    def test_bill_with_autopay_discount(self):
        """Test that autopay discounts appear in line items."""
        result = get_billing_info("ACC-10001")

        assert result.success is True
        bill = result.billing_info.bills[0]

        # Check for autopay discount in line items
        autopay_items = [
            item for item in bill.line_items if "autopay" in item.description.lower()
        ]
        assert len(autopay_items) > 0

        # Discount should be negative
        for item in autopay_items:
            assert item.amount < 0

    def test_bill_with_bundle_discount(self):
        """Test account with bundle discount."""
        result = get_billing_info("ACC-10002")

        assert result.success is True
        bill = result.billing_info.bills[0]

        # Check for bundle discount
        bundle_items = [
            item for item in bill.line_items if "bundle" in item.description.lower()
        ]
        assert len(bundle_items) > 0

        # Discount should be negative
        for item in bundle_items:
            assert item.amount < 0

    def test_bill_with_military_discount(self):
        """Test account with military discount."""
        result = get_billing_info("ACC-10019")

        assert result.success is True
        bill = result.billing_info.bills[0]

        # Check for military discount
        military_items = [
            item for item in bill.line_items if "military" in item.description.lower()
        ]
        assert len(military_items) > 0

        # Discount should be negative
        for item in military_items:
            assert item.amount < 0

    def test_bill_with_senior_discount(self):
        """Test account with senior discount."""
        result = get_billing_info("ACC-10007")

        assert result.success is True
        bill = result.billing_info.bills[0]

        # Check for senior discount
        senior_items = [
            item for item in bill.line_items if "senior" in item.description.lower()
        ]
        assert len(senior_items) > 0

        # Discount should be negative
        for item in senior_items:
            assert item.amount < 0

    def test_account_with_no_billing_history(self):
        """Test account ID with no billing records returns not_found."""
        result = get_billing_info("ACC-99999")

        assert result.success is False
        assert result.billing_info is None
        assert result.error_code == "not_found"
        assert "No billing history" in result.error_message

    def test_malformed_account_id_missing_dash(self):
        """Test that account_id without dash returns format error."""
        result = get_billing_info("ACC10001")

        assert result.success is False
        assert result.billing_info is None
        assert result.error_code == "invalid_format"
        assert "Invalid account_id format" in result.error_message
        assert "ACC-XXXXX" in result.error_message

    def test_malformed_account_id_wrong_prefix(self):
        """Test that account_id with wrong prefix returns format error."""
        result = get_billing_info("XYZ-10001")

        assert result.success is False
        assert result.billing_info is None
        assert result.error_code == "invalid_format"

    def test_malformed_account_id_wrong_length(self):
        """Test that account_id with wrong digit count returns format error."""
        result = get_billing_info("ACC-123")

        assert result.success is False
        assert result.billing_info is None
        assert result.error_code == "invalid_format"

    def test_invalid_months_zero(self):
        """Test that months=0 returns error."""
        result = get_billing_info("ACC-10001", months=0)

        assert result.success is False
        assert result.billing_info is None
        assert result.error_code == "invalid_months"
        assert "between 1 and 12" in result.error_message

    def test_invalid_months_negative(self):
        """Test that negative months returns error."""
        result = get_billing_info("ACC-10001", months=-1)

        assert result.success is False
        assert result.billing_info is None
        assert result.error_code == "invalid_months"

    def test_invalid_months_too_large(self):
        """Test that months > 12 returns error."""
        result = get_billing_info("ACC-10001", months=13)

        assert result.success is False
        assert result.billing_info is None
        assert result.error_code == "invalid_months"

    def test_bill_total_calculation_correct(self):
        """Test that bill total matches subtotal + discounts + taxes."""
        result = get_billing_info("ACC-10001")

        assert result.success is True
        for bill in result.billing_info.bills:
            # Allow small floating point rounding error
            expected_total = bill.subtotal + bill.discounts + bill.taxes
            assert abs(bill.total - expected_total) < 0.01

    def test_bills_sorted_by_issue_date_descending(self):
        """Test that bills are returned with most recent first."""
        result = get_billing_info("ACC-10002", months=3)

        assert result.success is True
        bills = result.billing_info.bills
        assert len(bills) == 3

        # Verify descending order
        for i in range(len(bills) - 1):
            assert bills[i].issue_date >= bills[i + 1].issue_date

    def test_account_with_multiple_line_items(self):
        """Test account with complex billing (multiple plans and discounts)."""
        result = get_billing_info("ACC-10002")

        assert result.success is True
        bill = result.billing_info.bills[0]

        # ACC-10002 has mobile + home internet + bundle + autopay
        assert len(bill.line_items) >= 4

        # Should have plan charges
        plan_items = [
            item
            for item in bill.line_items
            if "plan" in item.description.lower() and item.amount > 0
        ]
        assert len(plan_items) >= 2  # At least 2 plans

        # Should have discounts
        discount_items = [item for item in bill.line_items if item.amount < 0]
        assert len(discount_items) >= 2  # At least 2 discounts

    def test_empty_account_id_returns_format_error(self):
        """Test that empty account_id returns format error."""
        result = get_billing_info("")

        assert result.success is False
        assert result.billing_info is None
        assert result.error_code == "invalid_format"


class TestGetBillingInfoBackendSwitch:
    """Verify get_billing_info routes to the correct DataSource backend."""

    def test_sqlite_backend_reads_from_db(self, tmp_path):
        db_path = tmp_path / "billing.db"
        conn = sqlite3.connect(db_path)
        conn.execute(_CREATE_BILLS_TABLE)
        conn.execute(
            "INSERT INTO bills VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);",
            _SQLITE_FIXTURE_ROW,
        )
        conn.commit()
        conn.close()

        mock_cfg = MagicMock()
        mock_cfg.BILLING_DATA_SOURCE = "sqlite"
        mock_cfg.BILLING_DB_PATH = str(db_path)

        with patch("src.tools.billing.get_config", return_value=mock_cfg):
            result = get_billing_info("ACC-10001", months=3)

        assert result.success is True
        assert result.billing_info.total_bills == 1
        assert result.billing_info.bills[0].bill_id == "BILL-10001-202605"

    def test_json_backend_reads_from_file(self):
        mock_cfg = MagicMock()
        mock_cfg.BILLING_DATA_SOURCE = "json"
        mock_cfg.MOCK_DATA_DIR = PROJECT_ROOT / "mock-data"

        with patch("src.tools.billing.get_config", return_value=mock_cfg):
            result = get_billing_info("ACC-10001", months=3)

        assert result.success is True
        assert result.billing_info.total_bills == 3
