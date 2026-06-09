"""Speed and signal diagnostic tool.

This module provides the run_speed_diagnostic function, which retrieves
network speed test results and signal strength data for a customer account.
"""

import json
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


class HomeInternetDiagnostic(BaseModel):
    """Home internet speed test results."""

    wired_download_mbps: float = Field(
        description="Wired connection download speed in Mbps"
    )
    wired_upload_mbps: float = Field(
        description="Wired connection upload speed in Mbps"
    )
    wifi_download_mbps: float = Field(
        description="WiFi connection download speed in Mbps"
    )
    wifi_upload_mbps: float = Field(description="WiFi connection upload speed in Mbps")


class MobileDiagnostic(BaseModel):
    """Mobile service signal and data usage information."""

    signal_strength_dbm: int = Field(
        description="Signal strength in dBm (typical range: -50 to -120, higher is better)"
    )
    data_used_gb_this_cycle: float = Field(
        description="Mobile data used in current billing cycle (GB)"
    )


class SpeedDiagnostic(BaseModel):
    """Complete diagnostic results for an account."""

    account_id: str = Field(description="Account identifier")
    last_test_date: str = Field(
        description="Date of last diagnostic test (YYYY-MM-DD)"
    )
    home_internet: Optional[HomeInternetDiagnostic] = Field(
        default=None,
        description="Home internet speed test results, null if account has no home internet service",
    )
    mobile: Optional[MobileDiagnostic] = Field(
        default=None,
        description="Mobile signal and data usage, null if account has no mobile service",
    )


class RunSpeedDiagnosticResult(BaseModel):
    """Result of a speed diagnostic test.

    Returns either success with diagnostic data, or an error with reason.
    The agent should check success=True before using diagnostic data.
    """

    success: bool = Field(
        description="True if diagnostic completed, False if error occurred"
    )
    diagnostic: Optional[SpeedDiagnostic] = Field(
        default=None, description="Diagnostic data if success=True, null otherwise"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if success=False: invalid_format, not_found, or data_unavailable",
    )
    error_message: Optional[str] = Field(
        default=None, description="Human-readable error explanation if success=False"
    )


def run_speed_diagnostic(account_id: str) -> RunSpeedDiagnosticResult:
    """Run speed and signal diagnostic for a customer account.

    This tool retrieves the most recent network diagnostic results for an account,
    including home internet speed tests (wired and WiFi) and mobile signal strength
    and data usage information.

    Use this tool when:
    - The customer reports slow internet speeds and you need to check actual performance
    - The customer asks about their signal strength or coverage
    - You need to verify if speeds match the customer's plan (e.g., Fiber 1000 should get ~1000 Mbps)
    - The customer asks how much mobile data they have used this billing cycle
    - You need to diagnose WiFi vs wired speed differences
    - The customer reports poor mobile reception and you want to check signal strength

    Signal strength interpretation:
    - -50 to -70 dBm: Excellent signal
    - -70 to -85 dBm: Good signal
    - -85 to -100 dBm: Fair signal (may experience slower speeds)
    - Below -100 dBm: Poor signal (likely to have issues)

    Args:
        account_id: The account identifier in format "ACC-XXXXX" (e.g., "ACC-10001").
                    Must be exactly 5 digits after the "ACC-" prefix.

    Returns:
        RunSpeedDiagnosticResult with either:
        - success=True and diagnostic data showing speed test results and signal info
        - success=False with error_code and error_message explaining the failure

    Examples:
        Run diagnostic for account with home internet:
            result = run_speed_diagnostic("ACC-10002")
            if result.success:
                if result.diagnostic.home_internet:
                    print(f"Download: {result.diagnostic.home_internet.wired_download_mbps} Mbps")
                    print(f"WiFi: {result.diagnostic.home_internet.wifi_download_mbps} Mbps")
                if result.diagnostic.mobile:
                    print(f"Signal: {result.diagnostic.mobile.signal_strength_dbm} dBm")

        Mobile-only account:
            result = run_speed_diagnostic("ACC-10001")
            if result.success:
                # home_internet will be null, mobile will have data
                print(f"Signal: {result.diagnostic.mobile.signal_strength_dbm} dBm")
                print(f"Data used: {result.diagnostic.mobile.data_used_gb_this_cycle} GB")

        Invalid account ID:
            result = run_speed_diagnostic("ACC10001")
            # Returns: success=False, error_code="invalid_format"

        Account not found:
            result = run_speed_diagnostic("ACC-99999")
            # Returns: success=False, error_code="not_found"
    """
    # Validate account_id format
    account_id_pattern = re.compile(r"^ACC-\d{5}$")
    if not account_id_pattern.match(account_id):
        return RunSpeedDiagnosticResult(
            success=False,
            error_code="invalid_format",
            error_message=(
                f"Invalid account_id format: '{account_id}'. "
                "Expected format: ACC-XXXXX (e.g., ACC-10001)"
            ),
        )

    # Load diagnostic data
    data_path = Path(__file__).parent.parent.parent / "mock-data" / "diagnostics.json"
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            all_diagnostics = json.load(f)
    except FileNotFoundError:
        return RunSpeedDiagnosticResult(
            success=False,
            error_code="data_unavailable",
            error_message=f"Diagnostic database file not found at {data_path}",
        )
    except json.JSONDecodeError as e:
        return RunSpeedDiagnosticResult(
            success=False,
            error_code="data_unavailable",
            error_message=f"Failed to parse diagnostic database: {e}",
        )

    # Find diagnostic for this account
    if account_id not in all_diagnostics:
        return RunSpeedDiagnosticResult(
            success=False,
            error_code="not_found",
            error_message=f"No diagnostic data found for account: {account_id}",
        )

    diagnostic_data = all_diagnostics[account_id]

    # Parse into Pydantic models
    try:
        # Parse home internet data if present
        home_internet = None
        if diagnostic_data.get("home_internet") is not None:
            home_internet = HomeInternetDiagnostic(**diagnostic_data["home_internet"])

        # Parse mobile data if present
        mobile = None
        if diagnostic_data.get("mobile") is not None:
            mobile = MobileDiagnostic(**diagnostic_data["mobile"])

        diagnostic = SpeedDiagnostic(
            account_id=account_id,
            last_test_date=diagnostic_data["last_test_date"],
            home_internet=home_internet,
            mobile=mobile,
        )
        return RunSpeedDiagnosticResult(success=True, diagnostic=diagnostic)
    except Exception as e:
        return RunSpeedDiagnosticResult(
            success=False,
            error_code="data_invalid",
            error_message=f"Failed to parse diagnostic record: {e}",
        )
