import json

import pytest

from sv_llm.agents.base import AgentOutputError, BaseAgent, extract_json
from sv_llm.schemas import ThreatList
from tests.conftest import ScriptedChatModel, threats_reply


@pytest.mark.parametrize(
    "raw",
    [
        '{"a": 1}',
        'Sure, here you go:\n```json\n{"a": 1}\n```',
        'Result: {"a": 1} hope this helps',
        '```\n{"a": 1}\n```',
    ],
)
def test_extract_json_tolerates_wrapping(raw: str):
    assert extract_json(raw) == {"a": 1}


def test_extract_json_rejects_non_objects():
    with pytest.raises(ValueError):
        extract_json("[1, 2, 3]")
    with pytest.raises(ValueError):
        extract_json("no json here")


class _Probe(BaseAgent):
    name = "probe"
    system_prompt = "PROBE"


def test_structured_call_repairs_once():
    llm = ScriptedChatModel(scripts={"PROBE": ["not json at all", threats_reply(1)]})
    agent = _Probe(llm)
    result, messages = agent.structured_call(ThreatList, "go")
    assert len(result.threats) == 1
    # system, user, bad reply, repair request, good reply
    assert len(messages) == 5
    assert "not valid" in str(messages[3].content)


def test_structured_call_gives_up_after_budget():
    llm = ScriptedChatModel(scripts={"PROBE": [json.dumps({"threats": "wrong type"})]})
    agent = _Probe(llm, max_repair_attempts=1)
    with pytest.raises(AgentOutputError):
        agent.structured_call(ThreatList, "go")
