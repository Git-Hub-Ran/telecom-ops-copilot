"""Tests for BaseState abstract class."""

import inspect

import pytest

from src.orchestrator.states.base import BaseState


class TestBaseState:
    """Test suite for BaseState abstract class."""

    def test_cannot_instantiate_basestate_directly(self) -> None:
        """Test that BaseState cannot be instantiated directly."""
        # Attempting to instantiate BaseState should raise TypeError
        # because it has abstract methods
        with pytest.raises(TypeError) as exc_info:
            BaseState()

        # Verify error message mentions abstract methods
        assert "abstract" in str(exc_info.value).lower()

    def test_concrete_subclass_without_run_raises_typeerror(self) -> None:
        """Test that concrete subclass without run() implementation raises TypeError."""

        # Define a subclass that does NOT implement run()
        class IncompleteState(BaseState):
            pass

        # Attempting to instantiate should raise TypeError
        with pytest.raises(TypeError) as exc_info:
            IncompleteState()

        # Verify error mentions abstract method
        assert "abstract" in str(exc_info.value).lower()

    def test_concrete_subclass_with_run_can_be_instantiated(self) -> None:
        """Test that concrete subclass with run() implementation can be instantiated."""

        # Define a complete concrete subclass
        class CompleteState(BaseState[str, str]):
            async def run(self, context: str) -> str:
                return f"Processed: {context}"

        # Should instantiate without error
        state = CompleteState()
        assert isinstance(state, BaseState)
        assert isinstance(state, CompleteState)

    def test_run_method_is_async(self) -> None:
        """Test that run() method is a coroutine function (async)."""

        # Define a concrete state with async run()
        class AsyncState(BaseState[dict, dict]):
            async def run(self, context: dict) -> dict:
                return {"result": "done"}

        state = AsyncState()

        # Verify run() is a coroutine function
        assert inspect.iscoroutinefunction(state.run)
