"""Base state abstract class for orchestrator states.

All states in the orchestrator (Classify, Route, Act, Escalate, Respond) inherit
from BaseState and implement the async run() method.
"""

import re
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

# Generic type variables for input context and output result
InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")

# Opening fence with an optional language tag, and the closing fence. Matched
# independently so a single-line fence is handled the same as a multi-line one.
_FENCE_OPEN = re.compile(r"^```[A-Za-z0-9_+-]*\s*")
_FENCE_CLOSE = re.compile(r"\s*```$")


def strip_code_fence(raw: str) -> str:
    """Return `raw` stripped of whitespace and of a wrapping Markdown code fence.

    Agents are instructed to return bare JSON but sometimes wrap it in a ```json
    fence. Every state that parses an agent response calls this before handing the
    text to a JSON parser.

    Handles the fence opening and closing separately rather than splitting on the
    first newline, so a fence written on one line is stripped like any other. The
    newline-splitting version raised IndexError on those, and because every caller
    wraps this in a broad except, a parseable response was silently discarded in
    favour of the fallback path.
    """
    text = raw.strip()
    if not text.startswith("```"):
        return text
    text = _FENCE_OPEN.sub("", text)
    text = _FENCE_CLOSE.sub("", text)
    return text.strip()


class BaseState(ABC, Generic[InputT, OutputT]):
    """Abstract base class for all orchestrator states.

    Each state in the 5-state flow (Classify -> Route -> Act -> Escalate -> Respond)
    inherits from this base class and implements the run() method.

    This class uses Generic types to provide strong static typing for state inputs
    and outputs. Subclasses parameterize the base class with their specific input
    and output types.

    The state contract:
        - Input: Receives typed context via the context parameter
        - Output: Returns typed state-specific output
        - All state transitions are async to support I/O-bound operations

    Type Parameters:
        InputT: The input context type for this state
        OutputT: The output result type for this state

    Subclasses must implement:
        - async def run(self, context: InputT) -> OutputT

    Example:
        class ClassifyState(BaseState[StateContext, ClassifyOutput]):
            async def run(self, context: StateContext) -> ClassifyOutput:
                # Invoke Foundry agent, parse result
                return ClassifyOutput(intent="billing", confidence=0.92)

        # Type checker knows:
        # - context parameter must be StateContext
        # - return value must be ClassifyOutput
    """

    @abstractmethod
    async def run(self, context: InputT) -> OutputT:
        """Execute the state logic.

        This method must be implemented by all state subclasses. It receives
        typed context data and returns the state's typed output.

        Args:
            context: State-specific context data (type specified by InputT).
                     Typically a Pydantic model containing the data needed
                     for this state's execution.

        Returns:
            State-specific output (type specified by OutputT). Typically a
            Pydantic model representing the result of this state's execution.

        Raises:
            NotImplementedError: If subclass does not implement this method.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement run() method"
        )
