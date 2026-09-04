"""Tests for RoutingDecision enum."""

from src.orchestrator.models.route import RoutingDecision


class TestRoutingDecision:
    """Test suite for RoutingDecision enum."""

    def test_billing_path_has_correct_value(self) -> None:
        """Test that RoutingDecision.BILLING_PATH has value 'billing_path'."""
        assert RoutingDecision.BILLING_PATH == "billing_path"
        assert RoutingDecision.BILLING_PATH.value == "billing_path"

    def test_skip_to_escalate_has_correct_value(self) -> None:
        """Test that RoutingDecision.SKIP_TO_ESCALATE has value 'skip_to_escalate'."""
        assert RoutingDecision.SKIP_TO_ESCALATE == "skip_to_escalate"
        assert RoutingDecision.SKIP_TO_ESCALATE.value == "skip_to_escalate"

    def test_all_7_enum_values_are_unique(self) -> None:
        """Test that all 7 enum values are unique."""
        values = [decision.value for decision in RoutingDecision]
        assert len(values) == 7
        assert len(set(values)) == 7  # All unique

        # Verify all expected values are present
        expected_values = {
            "billing_path",
            "technical_path",
            "account_path",
            "info_path",
            "skip_to_escalate",
            "ask_clarifying_question",
            "refuse_off_topic"
        }
        assert set(values) == expected_values

    def test_can_compare_routing_decision_values(self) -> None:
        """Test that RoutingDecision values can be compared."""
        decision = RoutingDecision.BILLING_PATH

        # Equality comparison
        assert decision == RoutingDecision.BILLING_PATH
        assert decision != RoutingDecision.TECHNICAL_PATH

        # String comparison (str Enum allows this)
        assert decision == "billing_path"
        assert decision != "technical_path"
