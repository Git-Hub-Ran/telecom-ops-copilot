"""State context model for orchestrator state machine.

This module defines StateContext, the data carrier that flows through the
state machine. Each state reads the fields it needs from context and populates
its output slot for downstream states to consume.

StateContext is an internal implementation detail, not specified by any FR.
The individual state input requirements are defined in FR-008, FR-010, FR-012,
FR-014, and FR-016, but the unified context wrapper is an orchestrator design
decision.
"""

from typing import Optional

from pydantic import BaseModel, Field

from .act import ActOutput
from .classify import ClassifyOutput
from .route import RoutingDecision
from .session import SessionState


class StateContext(BaseModel):
    """Context passed to each state's run() method.

    Internal model, not specified by an FR. This is the data carrier that flows
    through the state machine, accumulating state outputs as execution progresses.

    The StateMachine builds an initial context with session_state and customer_message,
    then passes it through the state chain. Each state reads the fields it needs and
    populates its output slot:

    - ClassifyState reads customer_message and session_state, populates classify_output
    - RouteState reads classify_output, populates routing_decision
    - ActState reads routing_decision and customer_message, populates act_output
    - EscalateState reads classify_output and act_output (if triggered)
    - RespondState reads all fields to generate the final response

    Required fields are populated at context creation. Optional fields start as None
    and are populated by their corresponding states during execution.
    """

    session_state: SessionState = Field(
        description="Session state with conversation history, account info, and correlation ID"
    )
    customer_message: str = Field(
        description="Current customer message being processed"
    )
    classify_output: Optional[ClassifyOutput] = Field(
        default=None,
        description="Classification result from ClassifyState (None until ClassifyState runs)"
    )
    routing_decision: Optional[RoutingDecision] = Field(
        default=None,
        description="Routing decision from RouteState (None until RouteState runs)"
    )
    act_output: Optional[ActOutput] = Field(
        default=None,
        description="Act result from ActState (None until ActState runs)"
    )
