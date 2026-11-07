from langgraph.graph import END

from sv_llm.agents.supervisor import THREAT_MODEL, VALIDATE, VULN_DETECT, route


def test_route_starts_with_threat_model():
    assert route({"threats": [], "iteration": 0}) == THREAT_MODEL


def test_route_detects_after_threats():
    assert route({"threats": [{"id": "T1"}], "iteration": 0, "validation": None}) == VULN_DETECT


def test_route_validates_fresh_findings():
    state = {
        "threats": [{"id": "T1"}],
        "findings": [{"id": "F1"}],
        "iteration": 1,
        "validation": None,
    }
    assert route(state) == VALIDATE


def test_route_loops_on_revision_within_budget():
    state = {
        "threats": [{"id": "T1"}],
        "findings": [],
        "iteration": 1,
        "validation": {"needs_revision": True},
    }
    assert route(state, max_iterations=2) == VULN_DETECT
    assert route({**state, "iteration": 2}, max_iterations=2) == END


def test_route_finishes_when_validated():
    state = {
        "threats": [{"id": "T1"}],
        "findings": [{"id": "F1"}],
        "iteration": 1,
        "validation": {"needs_revision": False},
    }
    assert route(state) == END
