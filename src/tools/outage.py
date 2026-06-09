"""Network outage checking tool.

This module provides the check_network_outage function, which checks for
active network outages affecting a specific ZIP code area.
"""

import json
import re
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Outage(BaseModel):
    """An active network outage."""

    outage_id: str = Field(description="Unique outage identifier")
    type: Literal["mobile", "home_internet"] = Field(
        description="Type of service affected: mobile or home_internet"
    )
    zip_codes: list[str] = Field(
        description="List of ZIP codes affected by this outage"
    )
    service_affected: str = Field(
        description="Specific service affected (e.g., mobile_data_and_voice, home_internet, mobile_data)"
    )
    started_at: str = Field(
        description="Outage start time in ISO 8601 format (UTC)"
    )
    estimated_resolution: str = Field(
        description="Estimated resolution time in ISO 8601 format (UTC)"
    )
    status: Literal["active", "resolved", "monitoring"] = Field(
        description="Current outage status"
    )
    description: str = Field(
        description="Human-readable description of the outage cause and impact"
    )


class OutageCheckResult(BaseModel):
    """Collection of outages affecting a ZIP code."""

    zip_code: str = Field(description="ZIP code that was checked")
    has_outage: bool = Field(
        description="True if one or more active outages affect this ZIP code"
    )
    outages: list[Outage] = Field(
        description="List of active outages affecting this ZIP code (empty if none)"
    )
    total_outages: int = Field(
        description="Number of active outages affecting this ZIP code"
    )


class CheckNetworkOutageResult(BaseModel):
    """Result of a network outage check.

    Returns either success with outage data, or an error with reason.
    The agent should check success=True before using outage data.
    """

    success: bool = Field(
        description="True if check completed, False if error occurred"
    )
    outage_check: Optional[OutageCheckResult] = Field(
        default=None, description="Outage check result if success=True, null otherwise"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Error code if success=False: invalid_format or data_unavailable",
    )
    error_message: Optional[str] = Field(
        default=None, description="Human-readable error explanation if success=False"
    )


def check_network_outage(zip_code: str) -> CheckNetworkOutageResult:
    """Check for active network outages affecting a specific ZIP code.

    This tool checks the network status for a given ZIP code and returns any
    active outages affecting mobile or home internet service in that area.

    Use this tool when:
    - The customer reports service issues and you need to check for known outages
    - The customer asks if there are any outages in their area
    - You need to determine if a technical issue is due to a network outage
    - The customer asks when service will be restored in their area

    Args:
        zip_code: A 5-digit US ZIP code (e.g., "10001", "94103").
                  Must be exactly 5 numeric digits.

    Returns:
        CheckNetworkOutageResult with either:
        - success=True and outage_check containing outage information
        - success=False with error_code and error_message explaining the failure

    Examples:
        Check for outages in a ZIP code:
            result = check_network_outage("10001")
            if result.success:
                if result.outage_check.has_outage:
                    for outage in result.outage_check.outages:
                        print(f"Outage: {outage.description}")
                        print(f"ETA: {outage.estimated_resolution}")
                else:
                    print("No active outages in this area")

        Invalid ZIP code format:
            result = check_network_outage("123")
            # Returns: success=False, error_code="invalid_format"

        ZIP code with no outages:
            result = check_network_outage("99999")
            # Returns: success=True, has_outage=False, outages=[]
    """
    # Validate zip_code format (must be exactly 5 digits)
    zip_code_pattern = re.compile(r"^\d{5}$")
    if not zip_code_pattern.match(zip_code):
        return CheckNetworkOutageResult(
            success=False,
            error_code="invalid_format",
            error_message=(
                f"Invalid zip_code format: '{zip_code}'. "
                "Expected format: 5-digit US ZIP code (e.g., 10001, 94103)"
            ),
        )

    # Load outage data
    data_path = Path(__file__).parent.parent.parent / "mock-data" / "outages.json"
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            all_outages = json.load(f)
    except FileNotFoundError:
        return CheckNetworkOutageResult(
            success=False,
            error_code="data_unavailable",
            error_message=f"Outage database file not found at {data_path}",
        )
    except json.JSONDecodeError as e:
        return CheckNetworkOutageResult(
            success=False,
            error_code="data_unavailable",
            error_message=f"Failed to parse outage database: {e}",
        )

    # Filter outages affecting this ZIP code
    # Only include active outages
    affecting_outages = [
        outage
        for outage in all_outages
        if zip_code in outage.get("zip_codes", []) and outage.get("status") == "active"
    ]

    # Parse into Pydantic models
    try:
        parsed_outages = [Outage(**outage_data) for outage_data in affecting_outages]
        outage_check = OutageCheckResult(
            zip_code=zip_code,
            has_outage=len(parsed_outages) > 0,
            outages=parsed_outages,
            total_outages=len(parsed_outages),
        )
        return CheckNetworkOutageResult(success=True, outage_check=outage_check)
    except Exception as e:
        return CheckNetworkOutageResult(
            success=False,
            error_code="data_invalid",
            error_message=f"Failed to parse outage records: {e}",
        )
