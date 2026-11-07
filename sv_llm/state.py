"""Shared graph state.

The state is a TypedDict so LangGraph can checkpoint it. Agents write whole lists
(threats, findings) and the supervisor reads them to decide the next hop; ``trace``
and ``messages`` accumulate through reducers.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class VerificationState(TypedDict, total=False):
    design_name: str
    spec_text: str
    rtl_text: str
    context: list[str]
    threats: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    validation: dict[str, Any] | None
    iteration: int
    next_agent: str
    trace: Annotated[list[str], operator.add]
    messages: Annotated[list[AnyMessage], add_messages]


def initial_state(design_name: str, spec_text: str, rtl_text: str) -> VerificationState:
    return VerificationState(
        design_name=design_name,
        spec_text=spec_text,
        rtl_text=rtl_text,
        context=[],
        threats=[],
        findings=[],
        validation=None,
        iteration=0,
        next_agent="",
        trace=[],
        messages=[],
    )
