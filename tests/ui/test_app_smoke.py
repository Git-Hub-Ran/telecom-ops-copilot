"""Smoke tests for src/ui/app.py.

Verifies the app starts without exception via Streamlit's AppTest runtime
and that get_state_machine() returns a real StateMachine instance when
its dependencies are mocked.

These tests do not exercise the full chat flow; that requires a live
Azure Foundry environment. The goal is to confirm the module is importable,
the initial render is clean, and the cache wrapper works correctly.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import get_config
from src.orchestrator.state_machine import StateMachine
from streamlit.testing.v1 import AppTest

_APP_PATH = Path(__file__).parent.parent.parent / "src" / "ui" / "app.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables for Config singleton."""
    monkeypatch.setenv(
        "AZURE_FOUNDRY_PROJECT_ENDPOINT", "https://test.ai.azure.com/api/projects/test"
    )
    monkeypatch.setenv("AZURE_TENANT_ID", "12345678-1234-1234-1234-123456789abc")
    monkeypatch.setenv("VECTOR_STORE_ID", "vs_test")
    get_config.cache_clear()


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------


def test_app_starts_without_exception() -> None:
    """App renders its initial state without raising any exception.

    Patches get_state_machine so AppTest does not need real Azure credentials.
    On initial load there is no chat input, so the orchestrator is never
    called; the patch is a safety net in case Streamlit pre-warms the cache.
    """
    with patch("src.ui.app.get_state_machine", return_value=MagicMock(spec=StateMachine)):
        at = AppTest.from_file(str(_APP_PATH))
        at.run()
    assert not at.exception


def test_get_state_machine_returns_state_machine_instance() -> None:
    """get_state_machine() returns a StateMachine when dependencies are mocked.

    Clears the st.cache_resource cache before and after the test so the
    mocked instance does not leak into other tests or a live session.
    """
    from src.ui.app import get_state_machine

    get_state_machine.clear()
    try:
        with (
            patch("src.ui.app.get_config", return_value=MagicMock()),
            patch("src.ui.app.AgentFactory", return_value=MagicMock()),
        ):
            machine = get_state_machine()
        assert isinstance(machine, StateMachine)
    finally:
        get_state_machine.clear()
