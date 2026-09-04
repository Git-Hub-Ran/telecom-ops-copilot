"""Unit tests for JSONBillingDataSource."""

from pathlib import Path

import pytest

from src.data.json_billing_data_source import JSONBillingDataSource

JSON_PATH = Path(__file__).resolve().parent.parent.parent / "mock-data" / "billing.json"


@pytest.fixture
def source() -> JSONBillingDataSource:
    return JSONBillingDataSource(JSON_PATH)


class TestJSONBillingDataSource:
    def test_returns_bills_for_known_account(self, source):
        bills = source.get_bills("ACC-10001")
        assert len(bills) > 0
        assert all(b["account_id"] == "ACC-10001" for b in bills)

    def test_returns_empty_for_unknown_account(self, source):
        assert source.get_bills("ACC-99999") == []

    def test_returned_records_are_dicts(self, source):
        bills = source.get_bills("ACC-10001")
        assert all(isinstance(b, dict) for b in bills)

    def test_line_items_are_lists(self, source):
        bills = source.get_bills("ACC-10001")
        assert all(isinstance(b["line_items"], list) for b in bills)

    def test_does_not_filter_other_accounts(self, source):
        bills_1 = source.get_bills("ACC-10001")
        bills_2 = source.get_bills("ACC-10002")
        ids_1 = {b["bill_id"] for b in bills_1}
        ids_2 = {b["bill_id"] for b in bills_2}
        assert ids_1.isdisjoint(ids_2)
