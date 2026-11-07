from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from sv_llm.config import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent


class ScriptedChatModel(BaseChatModel):
    """Fake chat model that answers based on which agent is asking.

    ``scripts`` maps a substring of the agent's system prompt to a queue of replies. The
    last reply in a queue is repeated once the queue is exhausted, so loops terminate on
    the supervisor's budget rather than on the fake running dry.
    """

    scripts: dict[str, list[str]]
    calls: list[dict[str, Any]] = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        system = str(messages[0].content)
        for key, queue in self.scripts.items():
            if key in system:
                reply = queue.pop(0) if len(queue) > 1 else queue[0]
                self.calls.append({"agent": key, "n_messages": len(messages)})
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])
        raise AssertionError(f"no script matches system prompt: {system[:60]}...")


def threats_reply(n: int = 2) -> str:
    threats = [
        {
            "id": f"T{i + 1}",
            "title": f"Threat {i + 1}",
            "category": "information disclosure",
            "asset": "key register bank",
            "entry_point": "debug port",
            "description": "desc",
            "spec_refs": ["SR2"],
        }
        for i in range(n)
    ]
    return json.dumps({"threats": threats})


def findings_reply(ids: list[str], severity: str = "high") -> str:
    findings = [
        {
            "id": fid,
            "threat_id": "T1",
            "title": f"Finding {fid}",
            "severity": severity,
            "module": "aes_key_wrapper",
            "location": "dbg_rd_data",
            "description": "desc",
            "cwe": "CWE-1244",
            "recommendation": "gate it",
        }
        for fid in ids
    ]
    return json.dumps({"findings": findings})


def validation_reply(finding_ids: list[str], needs_revision: bool, notes: str = "") -> str:
    return json.dumps(
        {
            "checks": [
                {
                    "finding_id": fid,
                    "name": f"chk_{fid}",
                    "sva": "assert property (@(posedge clk) debug_lock_q |-> dbg_rd_data == 0);",
                    "description": "d",
                }
                for fid in finding_ids
            ],
            "verdicts": [
                {"finding_id": fid, "status": "confirmed", "rationale": "r"} for fid in finding_ids
            ],
            "needs_revision": needs_revision,
            "revision_notes": notes,
        }
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        max_iterations=2,
        retriever_k=4,
        examples_dir=REPO_ROOT / "examples/few_shot",
        designs_dir=REPO_ROOT / "designs",
    )


@pytest.fixture
def embeddings() -> DeterministicFakeEmbedding:
    return DeterministicFakeEmbedding(size=64)


@pytest.fixture
def designs_dir() -> Path:
    return REPO_ROOT / "designs"
