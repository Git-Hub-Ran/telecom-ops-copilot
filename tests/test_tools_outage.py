"""Tests for network outage checking tool."""

import pytest

from src.tools.outage import check_network_outage


class TestCheckNetworkOutage:
    """Test suite for check_network_outage function."""

    def test_valid_zip_code_with_active_outage_returns_success(self):
        """Test that a ZIP code with an active outage returns success."""
        result = check_network_outage("10001")

        assert result.success is True
        assert result.outage_check is not None
        assert result.error_code is None
        assert result.error_message is None

        # Verify outage was found
        assert result.outage_check.zip_code == "10001"
        assert result.outage_check.has_outage is True
        assert result.outage_check.total_outages > 0
        assert len(result.outage_check.outages) > 0

    def test_outage_structure_contains_all_fields(self):
        """Test that returned outages contain all expected fields."""
        result = check_network_outage("10001")

        assert result.success is True
        outage = result.outage_check.outages[0]

        # Verify all outage fields are present
        assert outage.outage_id.startswith("OUT-")
        assert outage.type in ["mobile", "home_internet"]
        assert isinstance(outage.zip_codes, list)
        assert len(outage.zip_codes) > 0
        assert "10001" in outage.zip_codes
        assert isinstance(outage.service_affected, str)
        assert isinstance(outage.started_at, str)
        assert isinstance(outage.estimated_resolution, str)
        assert outage.status == "active"
        assert isinstance(outage.description, str)
        assert len(outage.description) > 0

    def test_zip_code_with_no_outage_returns_empty_list(self):
        """Test that a ZIP code with no outages returns empty list."""
        result = check_network_outage("99999")

        assert result.success is True
        assert result.outage_check is not None
        assert result.outage_check.zip_code == "99999"
        assert result.outage_check.has_outage is False
        assert result.outage_check.total_outages == 0
        assert len(result.outage_check.outages) == 0

    def test_zip_code_with_mobile_outage(self):
        """Test ZIP code with mobile service outage."""
        result = check_network_outage("10001")

        assert result.success is True
        assert result.outage_check.has_outage is True

        # Find mobile outage
        mobile_outages = [o for o in result.outage_check.outages if o.type == "mobile"]
        assert len(mobile_outages) > 0

        # Verify mobile outage details
        mobile_outage = mobile_outages[0]
        assert mobile_outage.type == "mobile"
        assert "mobile" in mobile_outage.service_affected.lower()

    def test_zip_code_with_home_internet_outage(self):
        """Test ZIP code with home internet service outage."""
        result = check_network_outage("94103")

        assert result.success is True
        assert result.outage_check.has_outage is True

        # Find home internet outage
        internet_outages = [
            o for o in result.outage_check.outages if o.type == "home_internet"
        ]
        assert len(internet_outages) > 0

        # Verify home internet outage details
        internet_outage = internet_outages[0]
        assert internet_outage.type == "home_internet"
        assert "internet" in internet_outage.service_affected.lower()

    def test_zip_code_in_multiple_zip_code_outage(self):
        """Test ZIP code that is part of a multi-ZIP outage."""
        # 10001, 10002, 10003 are all in the same outage
        result1 = check_network_outage("10001")
        result2 = check_network_outage("10002")
        result3 = check_network_outage("10003")

        assert result1.success is True
        assert result2.success is True
        assert result3.success is True

        # All should have the same outage
        assert result1.outage_check.has_outage is True
        assert result2.outage_check.has_outage is True
        assert result3.outage_check.has_outage is True

        # Should have at least one outage affecting all three
        outage1 = result1.outage_check.outages[0]
        outage2 = result2.outage_check.outages[0]
        outage3 = result3.outage_check.outages[0]

        assert outage1.outage_id == outage2.outage_id
        assert outage2.outage_id == outage3.outage_id

    def test_outage_has_estimated_resolution_time(self):
        """Test that outages include estimated resolution time."""
        result = check_network_outage("10001")

        assert result.success is True
        assert result.outage_check.has_outage is True

        for outage in result.outage_check.outages:
            assert outage.estimated_resolution is not None
            assert len(outage.estimated_resolution) > 0
            # Should be ISO 8601 format
            assert "T" in outage.estimated_resolution
            assert "Z" in outage.estimated_resolution

    def test_outage_has_start_time(self):
        """Test that outages include start time."""
        result = check_network_outage("10001")

        assert result.success is True
        assert result.outage_check.has_outage is True

        for outage in result.outage_check.outages:
            assert outage.started_at is not None
            assert len(outage.started_at) > 0
            # Should be ISO 8601 format
            assert "T" in outage.started_at
            assert "Z" in outage.started_at

    def test_outage_description_is_informative(self):
        """Test that outage descriptions contain useful information."""
        result = check_network_outage("10001")

        assert result.success is True
        assert result.outage_check.has_outage is True

        for outage in result.outage_check.outages:
            # Description should be meaningful
            assert len(outage.description) > 20
            assert not outage.description.isspace()

    def test_only_active_outages_returned(self):
        """Test that only active outages are returned, not resolved ones."""
        result = check_network_outage("10001")

        assert result.success is True

        # All returned outages should have status "active"
        for outage in result.outage_check.outages:
            assert outage.status == "active"

    def test_malformed_zip_code_too_short(self):
        """Test that ZIP code with too few digits returns format error."""
        result = check_network_outage("123")

        assert result.success is False
        assert result.outage_check is None
        assert result.error_code == "invalid_format"
        assert "Invalid zip_code format" in result.error_message
        assert "5-digit" in result.error_message

    def test_malformed_zip_code_too_long(self):
        """Test that ZIP code with too many digits returns format error."""
        result = check_network_outage("123456")

        assert result.success is False
        assert result.outage_check is None
        assert result.error_code == "invalid_format"

    def test_malformed_zip_code_contains_letters(self):
        """Test that ZIP code with letters returns format error."""
        result = check_network_outage("ABC12")

        assert result.success is False
        assert result.outage_check is None
        assert result.error_code == "invalid_format"

    def test_malformed_zip_code_contains_special_chars(self):
        """Test that ZIP code with special characters returns format error."""
        result = check_network_outage("10-01")

        assert result.success is False
        assert result.outage_check is None
        assert result.error_code == "invalid_format"

    def test_empty_zip_code_returns_format_error(self):
        """Test that empty ZIP code returns format error."""
        result = check_network_outage("")

        assert result.success is False
        assert result.outage_check is None
        assert result.error_code == "invalid_format"

    def test_zip_code_with_leading_zero(self):
        """Test that ZIP codes with leading zeros are handled correctly."""
        # ZIP codes like 02115 (Boston) should work
        result = check_network_outage("02115")

        assert result.success is True
        assert result.outage_check is not None
        assert result.outage_check.zip_code == "02115"

    def test_zip_code_with_spaces_returns_format_error(self):
        """Test that ZIP code with spaces returns format error."""
        result = check_network_outage("10 001")

        assert result.success is False
        assert result.outage_check is None
        assert result.error_code == "invalid_format"

    def test_different_service_types_in_same_zip(self):
        """Test handling of multiple outage types in same ZIP code if applicable."""
        # This tests the data structure can handle multiple outages
        result = check_network_outage("94103")

        assert result.success is True

        # Should be able to iterate through all outages
        for outage in result.outage_check.outages:
            assert outage.type in ["mobile", "home_internet"]
            assert outage.status == "active"

    def test_zip_code_94110_has_outage(self):
        """Test specific ZIP code from mock data."""
        result = check_network_outage("94110")

        assert result.success is True
        assert result.outage_check.has_outage is True
        assert result.outage_check.total_outages > 0

    def test_zip_code_75201_has_outage(self):
        """Test specific ZIP code from mock data."""
        result = check_network_outage("75201")

        assert result.success is True
        assert result.outage_check.has_outage is True
        assert result.outage_check.total_outages > 0

        # This is a mobile data only outage
        outage = result.outage_check.outages[0]
        assert outage.type == "mobile"
        assert "data" in outage.service_affected.lower()

    def test_total_outages_matches_list_length(self):
        """Test that total_outages count matches actual outages list length."""
        result = check_network_outage("10001")

        assert result.success is True
        assert result.outage_check.total_outages == len(result.outage_check.outages)

    def test_has_outage_flag_matches_outages_list(self):
        """Test that has_outage flag correctly reflects presence of outages."""
        # With outage
        result_with = check_network_outage("10001")
        assert result_with.success is True
        assert result_with.outage_check.has_outage == (
            len(result_with.outage_check.outages) > 0
        )

        # Without outage
        result_without = check_network_outage("99999")
        assert result_without.success is True
        assert result_without.outage_check.has_outage == (
            len(result_without.outage_check.outages) > 0
        )
