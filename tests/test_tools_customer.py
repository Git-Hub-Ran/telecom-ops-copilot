"""Tests for customer account lookup tool."""

import pytest

from src.tools.customer import get_customer_account


class TestGetCustomerAccount:
    """Test suite for get_customer_account function."""

    def test_valid_account_returns_success(self):
        """Test that a valid account_id returns success with complete data."""
        result = get_customer_account("ACC-10001")

        assert result.success is True
        assert result.account is not None
        assert result.error_code is None
        assert result.error_message is None

        # Verify account fields
        assert result.account.account_id == "ACC-10001"
        assert result.account.name == "John Smith"
        assert result.account.email == "john.smith@example.com"
        assert result.account.phone_contact == "+1-555-100-0001"
        assert result.account.billing_zip == "10001"
        assert result.account.join_date == "2023-11-04"
        assert result.account.status == "active"

        # Verify services
        assert len(result.account.services) == 1
        service = result.account.services[0]
        assert service.line_id == "LINE-10001-1"
        assert service.type == "mobile"
        assert service.plan_id == "essential"
        assert service.phone_number == "+1-555-001-1000"
        assert service.status == "active"

        # Verify payment
        assert result.account.payment.method == "autopay_card"
        assert result.account.payment.card_last_four == "0007"

        # Verify discounts
        assert result.account.discounts == ["autopay"]

    def test_suspended_account_returns_suspended_status(self):
        """Test that suspended accounts are correctly identified."""
        result = get_customer_account("ACC-10004")

        assert result.success is True
        assert result.account is not None
        assert result.account.status == "suspended"
        assert result.account.name == "David Lee"

    def test_multi_service_account_returns_all_services(self):
        """Test that accounts with multiple services return all lines."""
        result = get_customer_account("ACC-10002")

        assert result.success is True
        assert result.account is not None
        assert len(result.account.services) == 2

        # Verify both service types are present
        service_types = [s.type for s in result.account.services]
        assert "mobile" in service_types
        assert "home_internet" in service_types

        # Verify bundle discount
        assert "bundle" in result.account.discounts
        assert "autopay" in result.account.discounts

    def test_account_with_family_discount(self):
        """Test account with multiple mobile lines and family discount."""
        result = get_customer_account("ACC-10006")

        assert result.success is True
        assert result.account is not None
        assert len(result.account.services) == 3
        assert all(s.type == "mobile" for s in result.account.services)
        assert "family" in result.account.discounts

    def test_non_existent_account_returns_not_found(self):
        """Test that a non-existent account_id returns not_found error."""
        result = get_customer_account("ACC-99999")

        assert result.success is False
        assert result.account is None
        assert result.error_code == "not_found"
        assert "No customer account found" in result.error_message
        assert "ACC-99999" in result.error_message

    def test_malformed_account_id_missing_dash_returns_format_error(self):
        """Test that account_id without dash returns format error."""
        result = get_customer_account("ACC10001")

        assert result.success is False
        assert result.account is None
        assert result.error_code == "invalid_format"
        assert "Invalid account_id format" in result.error_message
        assert "ACC-XXXXX" in result.error_message

    def test_malformed_account_id_wrong_prefix_returns_format_error(self):
        """Test that account_id with wrong prefix returns format error."""
        result = get_customer_account("XYZ-10001")

        assert result.success is False
        assert result.account is None
        assert result.error_code == "invalid_format"

    def test_malformed_account_id_too_few_digits_returns_format_error(self):
        """Test that account_id with insufficient digits returns format error."""
        result = get_customer_account("ACC-123")

        assert result.success is False
        assert result.account is None
        assert result.error_code == "invalid_format"

    def test_malformed_account_id_too_many_digits_returns_format_error(self):
        """Test that account_id with too many digits returns format error."""
        result = get_customer_account("ACC-123456")

        assert result.success is False
        assert result.account is None
        assert result.error_code == "invalid_format"

    def test_malformed_account_id_non_numeric_returns_format_error(self):
        """Test that account_id with non-numeric suffix returns format error."""
        result = get_customer_account("ACC-ABCDE")

        assert result.success is False
        assert result.account is None
        assert result.error_code == "invalid_format"

    def test_empty_account_id_returns_format_error(self):
        """Test that empty account_id returns format error."""
        result = get_customer_account("")

        assert result.success is False
        assert result.account is None
        assert result.error_code == "invalid_format"

    def test_pending_status_account(self):
        """Test account with pending status."""
        result = get_customer_account("ACC-10020")

        assert result.success is True
        assert result.account is not None
        assert result.account.status == "pending"
        assert result.account.name == "Lisa Robinson"

    def test_manual_payment_no_card_last_four(self):
        """Test account with manual payment has null card_last_four."""
        result = get_customer_account("ACC-10003")

        assert result.success is True
        assert result.account is not None
        assert result.account.payment.method == "manual"
        assert result.account.payment.card_last_four is None

    def test_home_internet_only_account(self):
        """Test account with only home internet service (no mobile)."""
        result = get_customer_account("ACC-10009")

        assert result.success is True
        assert result.account is not None
        assert len(result.account.services) == 1
        assert result.account.services[0].type == "home_internet"
        assert result.account.services[0].plan_id == "fiber_1000"
        assert result.account.services[0].phone_number is None

    def test_military_discount_present(self):
        """Test account with military discount."""
        result = get_customer_account("ACC-10008")

        assert result.success is True
        assert result.account is not None
        assert "military" in result.account.discounts
        assert "autopay" in result.account.discounts

    def test_senior_discount_present(self):
        """Test account with senior discount."""
        result = get_customer_account("ACC-10007")

        assert result.success is True
        assert result.account is not None
        assert "senior" in result.account.discounts
        assert "autopay" in result.account.discounts
