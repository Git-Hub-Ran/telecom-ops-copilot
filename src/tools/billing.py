"""Billing information lookup tool.

This module provides the get_billing_info function, which retrieves
recent billing history for a customer account.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

from src.config import PROJECT_ROOT, get_config
from src.data import BillingDataSource
from src.data.json_billing_data_source import JSONBillingDataSource
from src.data.sqlite_billing_data_source import SQLiteBillingDataSource


class LineItem(BaseModel):
    """A single line item on a bill."""

    description: str = Field(description="Line item description (plan, discount, tax)")
    amount: float = Field(description="Line item amount (negative for discounts)")


class Bill(BaseModel):
    """A single bill record."""

    bill_id: str = Field(description="Unique bill identifier (BILL-XXXXX-YYYYMM)")
    account_id: str = Field(description="Account identifier")
    billing_period_start: str = Field(
        description="Billing period start date (YYYY-MM-DD)"
    )
    billing_period_end: str = Field(description="Billing period end date (YYYY-MM-DD)")
    issue_date: str = Field(description="Bill issue date (YYYY-MM-DD)")
    due_date: str = Field(description="Payment due date (YYYY-MM-DD)")
    subtotal: float = Field(description="Subtotal before discounts and taxes")
    discounts: float = Field(description="Total discounts applied (negative value)")
    taxes: float = Field(description="Total taxes and fees")
    total: float = Field(description="Final total amount due")
    status: Literal["paid", "unpaid", "overdue", "scheduled"] = Field(
        description="Bill payment status"
    )
    paid_date: Optional[str] = Field(
        description="Date bill was paid (YYYY-MM-DD), null if unpaid"
    )
    line_items: list[LineItem] = Field(
        description="Detailed breakdown of charges and discounts"
    )


class BillingInfo(BaseModel):
    """Collection of bills for an account."""

    account_id: str = Field(description="Account identifier")
    bills: list[Bill] = Field(description="List of bills, most recent first")
    total_bills: int = Field(description="Number of bills returned")


class GetBillingInfoResult(BaseModel):
    """Result of a billing information lookup.

    Returns either success with billing data, or an error with reason.
    The agent should check success=True before using billing data.
    """

    success: bool = Field(
        description="True if billing info was found, False if error occurred"
    )
    billing_info: Optional[BillingInfo] = Field(
        default=None, description="Billing data if success=True, null otherwise"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if success=False: invalid_format, not_found, or invalid_months",
    )
    error_message: Optional[str] = Field(
        default=None, description="Human-readable error explanation if success=False"
    )


def _get_data_source() -> BillingDataSource:
    cfg = get_config()
    if cfg.BILLING_DATA_SOURCE == "sqlite":
        return SQLiteBillingDataSource(PROJECT_ROOT / cfg.BILLING_DB_PATH)
    return JSONBillingDataSource(cfg.MOCK_DATA_DIR / "billing.json")


def get_billing_info(account_id: str, months: int = 3) -> GetBillingInfoResult:
    """Retrieve recent billing history for a customer account.

    This tool retrieves billing records for the specified account, including
    bill totals, payment status, due dates, and detailed line items showing
    plan charges, discounts, and taxes.

    Use this tool when:
    - The customer asks about their bill or billing history
    - The customer wants to know what they owe or when payment is due
    - The customer asks why their bill changed or what charges are on their bill
    - You need to check if there are any overdue or unpaid bills
    - The customer disputes a charge and you need to see the breakdown

    Args:
        account_id: The account identifier in format "ACC-XXXXX" (e.g., "ACC-10001").
                    Must be exactly 5 digits after the "ACC-" prefix.
        months: Number of recent months of billing history to retrieve (1-12).
                Defaults to 3 months. Returns bills from most recent to oldest.

    Returns:
        GetBillingInfoResult with either:
        - success=True and billing_info containing recent bills
        - success=False with error_code and error_message explaining the failure

    Examples:
        Get last 3 months (default):
            result = get_billing_info("ACC-10001")
            if result.success:
                for bill in result.billing_info.bills:
                    print(f"{bill.bill_id}: ${bill.total} ({bill.status})")

        Get last 6 months:
            result = get_billing_info("ACC-10001", months=6)

        Invalid account ID:
            result = get_billing_info("ACC10001")
            # Returns: success=False, error_code="invalid_format"

        Account with no billing history:
            result = get_billing_info("ACC-99999")
            # Returns: success=True, billing_info.bills=[]
    """
    # Validate account_id format
    account_id_pattern = re.compile(r"^ACC-\d{5}$")
    if not account_id_pattern.match(account_id):
        return GetBillingInfoResult(
            success=False,
            error_code="invalid_format",
            error_message=(
                f"Invalid account_id format: '{account_id}'. "
                "Expected format: ACC-XXXXX (e.g., ACC-10001)"
            ),
        )

    # Validate months parameter
    if not isinstance(months, int) or months < 1 or months > 12:
        return GetBillingInfoResult(
            success=False,
            error_code="invalid_months",
            error_message=(
                f"Invalid months parameter: {months}. "
                "Must be an integer between 1 and 12."
            ),
        )

    # Load billing data
    data_path = Path(__file__).parent.parent.parent / "mock-data" / "billing.json"
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            all_bills = json.load(f)
    except FileNotFoundError:
        return GetBillingInfoResult(
            success=False,
            error_code="data_unavailable",
            error_message=f"Billing database file not found at {data_path}",
        )
    except json.JSONDecodeError as e:
        return GetBillingInfoResult(
            success=False,
            error_code="data_unavailable",
            error_message=f"Failed to parse billing database: {e}",
        )

    # Filter bills for this account
    account_bills = [bill for bill in all_bills if bill["account_id"] == account_id]

    # Sort by issue_date descending (most recent first)
    account_bills.sort(key=lambda b: b["issue_date"], reverse=True)

    # Limit to requested number of months
    limited_bills = account_bills[:months]

    # Parse into Pydantic models
    try:
        parsed_bills = [Bill(**bill_data) for bill_data in limited_bills]
        billing_info = BillingInfo(
            account_id=account_id,
            bills=parsed_bills,
            total_bills=len(parsed_bills),
        )
        return GetBillingInfoResult(success=True, billing_info=billing_info)
    except Exception as e:
        return GetBillingInfoResult(
            success=False,
            error_code="data_invalid",
            error_message=f"Failed to parse billing records: {e}",
        )
