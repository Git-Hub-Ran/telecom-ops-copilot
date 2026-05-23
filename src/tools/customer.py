"""Customer account lookup tool.

This module provides the get_customer_account function, which retrieves
customer profile, plan, and status information from the mock customer database.
"""

import json
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Service(BaseModel):
    """A service line on the customer account (mobile or home internet)."""

    line_id: str = Field(description="Unique identifier for this service line")
    type: Literal["mobile", "home_internet"] = Field(
        description="Service type: mobile or home_internet"
    )
    plan_id: str = Field(
        description="Plan identifier (essential, connect, unlimited, internet_100, fiber_1000)"
    )
    phone_number: Optional[str] = Field(
        description="Phone number for mobile lines, null for home internet"
    )
    status: str = Field(description="Service status (active, suspended, pending)")
    activated_on: str = Field(description="Activation date in YYYY-MM-DD format")


class Payment(BaseModel):
    """Payment method information."""

    method: str = Field(
        description="Payment method: autopay_card, autopay_bank, or manual"
    )
    card_last_four: Optional[str] = Field(
        description="Last four digits of card, null for bank or manual"
    )


class CustomerAccount(BaseModel):
    """Complete customer account profile."""

    account_id: str = Field(description="Account identifier (ACC-XXXXX format)")
    name: str = Field(description="Customer name on file")
    email: str = Field(description="Customer email address")
    phone_contact: str = Field(description="Customer contact phone number")
    billing_zip: str = Field(description="Billing ZIP code")
    join_date: str = Field(description="Account creation date in YYYY-MM-DD format")
    status: str = Field(
        description="Account status: active, suspended, pending, or cancelled"
    )
    services: list[Service] = Field(
        description="List of service lines (mobile and/or home internet)"
    )
    payment: Payment = Field(description="Payment method details")
    discounts: list[str] = Field(
        description="Active discount codes (autopay, bundle, family, senior, military)"
    )


class GetCustomerAccountResult(BaseModel):
    """Result of a customer account lookup.

    Returns either success with account data, or an error with reason.
    The agent should check success=True before using account data.
    """

    success: bool = Field(
        description="True if account was found, False if error occurred"
    )
    account: Optional[CustomerAccount] = Field(
        default=None, description="Account data if success=True, null otherwise"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if success=False: invalid_format or not_found",
    )
    error_message: Optional[str] = Field(
        default=None, description="Human-readable error explanation if success=False"
    )


def get_customer_account(account_id: str) -> GetCustomerAccountResult:
    """Look up a customer account by account ID.

    This tool retrieves the complete customer profile, including account status,
    active service lines (mobile and home internet), plan assignments, payment
    method, and active discounts.

    Use this tool when:
    - The customer asks about their plan or account details
    - You need to verify account status before performing other operations
    - The customer provides an account ID and you need to look up their information
    - You need to check what services are active on an account

    Args:
        account_id: The account identifier in format "ACC-XXXXX" (e.g., "ACC-10001").
                    Must be exactly 5 digits after the "ACC-" prefix.

    Returns:
        GetCustomerAccountResult with either:
        - success=True and account data in the account field
        - success=False with error_code and error_message explaining the failure

    Examples:
        Valid lookup:
            result = get_customer_account("ACC-10001")
            if result.success:
                print(f"Customer: {result.account.name}")
                print(f"Status: {result.account.status}")
                print(f"Services: {len(result.account.services)}")

        Invalid format:
            result = get_customer_account("ACC10001")  # missing dash
            # Returns: success=False, error_code="invalid_format"

        Not found:
            result = get_customer_account("ACC-99999")
            # Returns: success=False, error_code="not_found"
    """
    # Validate account_id format
    account_id_pattern = re.compile(r"^ACC-\d{5}$")
    if not account_id_pattern.match(account_id):
        return GetCustomerAccountResult(
            success=False,
            error_code="invalid_format",
            error_message=(
                f"Invalid account_id format: '{account_id}'. "
                "Expected format: ACC-XXXXX (e.g., ACC-10001)"
            ),
        )

    # Load customer data
    data_path = Path(__file__).parent.parent.parent / "mock-data" / "customers.json"
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            customers = json.load(f)
    except FileNotFoundError:
        return GetCustomerAccountResult(
            success=False,
            error_code="data_unavailable",
            error_message=f"Customer database file not found at {data_path}",
        )
    except json.JSONDecodeError as e:
        return GetCustomerAccountResult(
            success=False,
            error_code="data_unavailable",
            error_message=f"Failed to parse customer database: {e}",
        )

    # Find the customer
    for customer_data in customers:
        if customer_data["account_id"] == account_id:
            try:
                account = CustomerAccount(**customer_data)
                return GetCustomerAccountResult(success=True, account=account)
            except Exception as e:
                return GetCustomerAccountResult(
                    success=False,
                    error_code="data_invalid",
                    error_message=f"Failed to parse customer record: {e}",
                )

    # Account not found
    return GetCustomerAccountResult(
        success=False,
        error_code="not_found",
        error_message=f"No customer account found with ID: {account_id}",
    )
