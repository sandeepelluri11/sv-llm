"""Supervisor: deterministic routing over the shared state.

The supervisor does not call a model. Routing on typed state keeps the loop auditable and
makes the stop condition (max iterations) impossible for a model to talk its way past.
"""

from __future__ import annotations

from langgraph.graph import END

from sv_llm.state import VerificationState

THREAT_MODEL = "threat_model"
VULN_DETECT = "vuln_detect"
VALIDATE = "validate"


def route(state: VerificationState, max_iterations: int = 2) -> str:
    """Decide which agent runs next.

    1. No threats yet            -> threat_model
    2. No findings yet           -> vuln_detect
    3. Findings not validated    -> validate
    4. Validator asked for a revision and budget remains -> vuln_detect
    5. Otherwise                 -> END
    """
    if not state.get("threats"):
        return THREAT_MODEL
    if state.get("iteration", 0) == 0:
        return VULN_DETECT
    validation = state.get("validation")
    if validation is None:
        return VALIDATE
    if validation.get("needs_revision") and state.get("iteration", 0) < max_iterations:
        return VULN_DETECT
    return END


def supervisor_node(max_iterations: int = 2):
    def _node(state: VerificationState) -> dict:
        decision = route(state, max_iterations)
        label = "finish" if decision == END else decision
        return {"next_agent": decision, "trace": [f"supervisor: route -> {label}"]}

    return _node
