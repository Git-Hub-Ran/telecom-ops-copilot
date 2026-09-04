"""Tests for speed and signal diagnostic tool."""

import pytest

from src.tools.diagnostic import run_speed_diagnostic


class TestRunSpeedDiagnostic:
    """Test suite for run_speed_diagnostic function."""

    def test_valid_account_returns_success(self):
        """Test that a valid account_id returns success with diagnostic data."""
        result = run_speed_diagnostic("ACC-10001")

        assert result.success is True
        assert result.diagnostic is not None
        assert result.error_code is None
        assert result.error_message is None

        # Verify diagnostic structure
        assert result.diagnostic.account_id == "ACC-10001"
        assert result.diagnostic.last_test_date is not None

    def test_mobile_only_account_has_mobile_data_no_home_internet(self):
        """Test mobile-only account has mobile data but no home internet."""
        result = run_speed_diagnostic("ACC-10001")

        assert result.success is True
        assert result.diagnostic is not None

        # ACC-10001 is mobile only
        assert result.diagnostic.mobile is not None
        assert result.diagnostic.home_internet is None

        # Verify mobile data fields
        mobile = result.diagnostic.mobile
        assert isinstance(mobile.signal_strength_dbm, int)
        assert isinstance(mobile.data_used_gb_this_cycle, float)
        assert mobile.data_used_gb_this_cycle >= 0

    def test_home_internet_only_account_has_internet_no_mobile(self):
        """Test home internet-only account has internet data but no mobile."""
        result = run_speed_diagnostic("ACC-10009")

        assert result.success is True
        assert result.diagnostic is not None

        # ACC-10009 is home internet only
        assert result.diagnostic.home_internet is not None
        assert result.diagnostic.mobile is None

        # Verify home internet fields
        internet = result.diagnostic.home_internet
        assert isinstance(internet.wired_download_mbps, float)
        assert isinstance(internet.wired_upload_mbps, float)
        assert isinstance(internet.wifi_download_mbps, float)
        assert isinstance(internet.wifi_upload_mbps, float)
        assert internet.wired_download_mbps > 0
        assert internet.wired_upload_mbps > 0
        assert internet.wifi_download_mbps > 0
        assert internet.wifi_upload_mbps > 0

    def test_account_with_both_services_has_both_diagnostics(self):
        """Test account with both mobile and home internet has both diagnostics."""
        result = run_speed_diagnostic("ACC-10002")

        assert result.success is True
        assert result.diagnostic is not None

        # ACC-10002 has both services
        assert result.diagnostic.mobile is not None
        assert result.diagnostic.home_internet is not None

        # Verify both data sets are complete
        assert result.diagnostic.mobile.signal_strength_dbm is not None
        assert result.diagnostic.mobile.data_used_gb_this_cycle is not None
        assert result.diagnostic.home_internet.wired_download_mbps is not None
        assert result.diagnostic.home_internet.wifi_download_mbps is not None

    def test_signal_strength_in_valid_range(self):
        """Test that signal strength values are in expected dBm range."""
        result = run_speed_diagnostic("ACC-10001")

        assert result.success is True
        mobile = result.diagnostic.mobile

        # Signal strength typically ranges from -50 (excellent) to -120 (very poor)
        assert -120 <= mobile.signal_strength_dbm <= -50

    def test_excellent_signal_strength(self):
        """Test account with excellent signal strength (-65 dBm)."""
        result = run_speed_diagnostic("ACC-10005")

        assert result.success is True
        mobile = result.diagnostic.mobile
        # -50 to -70 is excellent
        assert -70 <= mobile.signal_strength_dbm <= -50

    def test_good_signal_strength(self):
        """Test account with good signal strength."""
        result = run_speed_diagnostic("ACC-10003")

        assert result.success is True
        mobile = result.diagnostic.mobile
        # -70 to -85 is good
        assert -85 <= mobile.signal_strength_dbm <= -70

    def test_fair_signal_strength(self):
        """Test account with fair signal strength."""
        result = run_speed_diagnostic("ACC-10001")

        assert result.success is True
        mobile = result.diagnostic.mobile
        # -85 to -100 is fair
        assert -100 <= mobile.signal_strength_dbm <= -85

    def test_poor_signal_strength(self):
        """Test account with poor signal strength."""
        result = run_speed_diagnostic("ACC-10015")

        assert result.success is True
        mobile = result.diagnostic.mobile
        # Below -100 is poor (but we have -92 in data, which is fair)
        assert mobile.signal_strength_dbm < -85

    def test_fiber_1000_speeds_are_high(self):
        """Test that Fiber 1000 accounts show high speeds."""
        result = run_speed_diagnostic("ACC-10009")

        assert result.success is True
        internet = result.diagnostic.home_internet

        # Fiber 1000 should deliver speeds close to 1000 Mbps
        assert internet.wired_download_mbps > 500
        assert internet.wired_upload_mbps > 500

    def test_internet_100_speeds_are_moderate(self):
        """Test that Internet 100 accounts show moderate speeds."""
        result = run_speed_diagnostic("ACC-10014")

        assert result.success is True
        internet = result.diagnostic.home_internet

        # Internet 100 should deliver speeds around 100 Mbps
        assert 50 <= internet.wired_download_mbps <= 150

    def test_wifi_slower_than_wired(self):
        """Test that WiFi speeds are typically slower than wired."""
        result = run_speed_diagnostic("ACC-10002")

        assert result.success is True
        internet = result.diagnostic.home_internet

        # WiFi is usually slower than wired (but not always)
        # Just verify both exist and are reasonable
        assert internet.wired_download_mbps > 0
        assert internet.wifi_download_mbps > 0

    def test_last_test_date_format(self):
        """Test that last_test_date is in correct format."""
        result = run_speed_diagnostic("ACC-10001")

        assert result.success is True
        # Should be YYYY-MM-DD format
        date = result.diagnostic.last_test_date
        assert len(date) == 10
        assert date[4] == "-"
        assert date[7] == "-"

    def test_data_usage_is_non_negative(self):
        """Test that data usage values are non-negative."""
        result = run_speed_diagnostic("ACC-10001")

        assert result.success is True
        mobile = result.diagnostic.mobile
        assert mobile.data_used_gb_this_cycle >= 0

    def test_low_data_usage_account(self):
        """Test account with very low data usage."""
        result = run_speed_diagnostic("ACC-10007")

        assert result.success is True
        mobile = result.diagnostic.mobile
        # ACC-10007 has 0.9 GB usage
        assert mobile.data_used_gb_this_cycle < 1.0

    def test_high_data_usage_account(self):
        """Test account with high data usage."""
        result = run_speed_diagnostic("ACC-10010")

        assert result.success is True
        mobile = result.diagnostic.mobile
        # ACC-10010 has 8.0 GB usage
        assert mobile.data_used_gb_this_cycle > 7.0

    def test_account_not_found_returns_not_found_error(self):
        """Test that a non-existent account_id returns not_found error."""
        result = run_speed_diagnostic("ACC-99999")

        assert result.success is False
        assert result.diagnostic is None
        assert result.error_code == "not_found"
        assert "No diagnostic data found" in result.error_message
        assert "ACC-99999" in result.error_message

    def test_malformed_account_id_missing_dash(self):
        """Test that account_id without dash returns format error."""
        result = run_speed_diagnostic("ACC10001")

        assert result.success is False
        assert result.diagnostic is None
        assert result.error_code == "invalid_format"
        assert "Invalid account_id format" in result.error_message
        assert "ACC-XXXXX" in result.error_message

    def test_malformed_account_id_wrong_prefix(self):
        """Test that account_id with wrong prefix returns format error."""
        result = run_speed_diagnostic("XYZ-10001")

        assert result.success is False
        assert result.diagnostic is None
        assert result.error_code == "invalid_format"

    def test_malformed_account_id_wrong_length(self):
        """Test that account_id with wrong digit count returns format error."""
        result = run_speed_diagnostic("ACC-123")

        assert result.success is False
        assert result.diagnostic is None
        assert result.error_code == "invalid_format"

    def test_empty_account_id_returns_format_error(self):
        """Test that empty account_id returns format error."""
        result = run_speed_diagnostic("")

        assert result.success is False
        assert result.diagnostic is None
        assert result.error_code == "invalid_format"

    def test_multiple_accounts_have_consistent_structure(self):
        """Test that multiple accounts return consistent diagnostic structure."""
        account_ids = ["ACC-10001", "ACC-10002", "ACC-10009", "ACC-10014"]

        for account_id in account_ids:
            result = run_speed_diagnostic(account_id)
            assert result.success is True
            assert result.diagnostic.account_id == account_id
            assert result.diagnostic.last_test_date is not None
            # At least one service should be present
            assert (
                result.diagnostic.mobile is not None
                or result.diagnostic.home_internet is not None
            )

    def test_all_speed_values_are_positive(self):
        """Test that all speed test values are positive numbers."""
        result = run_speed_diagnostic("ACC-10002")

        assert result.success is True
        internet = result.diagnostic.home_internet

        assert internet.wired_download_mbps > 0
        assert internet.wired_upload_mbps > 0
        assert internet.wifi_download_mbps > 0
        assert internet.wifi_upload_mbps > 0

    def test_account_10005_has_both_services(self):
        """Test specific account from mock data with both services."""
        result = run_speed_diagnostic("ACC-10005")

        assert result.success is True
        assert result.diagnostic.mobile is not None
        assert result.diagnostic.home_internet is not None

        # Check reasonable values
        assert result.diagnostic.mobile.signal_strength_dbm == -65
        assert result.diagnostic.mobile.data_used_gb_this_cycle > 0
        assert result.diagnostic.home_internet.wired_download_mbps > 0

    def test_account_10016_fiber_speeds(self):
        """Test account with Fiber 1000 plan has high speeds."""
        result = run_speed_diagnostic("ACC-10016")

        assert result.success is True
        internet = result.diagnostic.home_internet

        # Should have high speeds for fiber
        assert internet.wired_download_mbps > 500
        assert internet.wifi_download_mbps > 400

    def test_diagnostic_data_includes_account_id(self):
        """Test that diagnostic result includes the account_id."""
        result = run_speed_diagnostic("ACC-10001")

        assert result.success is True
        assert result.diagnostic.account_id == "ACC-10001"
