from __future__ import annotations

import json
import re
from typing import TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from sv_llm.retrieval.examples import FewShotExample, render_examples, select_examples
from sv_llm.retrieval.store import SpecStore

T = TypeVar("T", bound=BaseModel)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class AgentOutputError(RuntimeError):
    """Raised when the model never produced output matching the agent's schema."""


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply, tolerating code fences and prose."""
    candidates = [m.group(1) for m in _FENCE.finditer(text)] or [text]
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end > start:
            try:
                data = json.loads(candidate[start : end + 1])
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
    raise ValueError("no JSON object found in model output")


def _content_to_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    parts = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "\n".join(parts)


class BaseAgent:
    """Shared plumbing: prompt assembly, retrieval, structured output with one repair retry."""

    name: str = "agent"
    system_prompt: str = ""

    def __init__(
        self,
        llm: BaseChatModel,
        store: SpecStore | None = None,
        examples: list[FewShotExample] | None = None,
        retriever_k: int = 6,
        max_repair_attempts: int = 1,
    ) -> None:
        self.llm = llm
        self.store = store
        self.examples = examples or []
        self.retriever_k = retriever_k
        self.max_repair_attempts = max_repair_attempts

    def retrieve(self, query: str, kind: str | None = None) -> list:
        if self.store is None or self.store.size == 0:
            return []
        return self.store.search(query, k=self.retriever_k, kind=kind)

    def few_shot_block(self, text: str, limit: int = 2) -> str:
        chosen = select_examples(self.examples, self.name, text, limit=limit)
        rendered = render_examples(chosen)
        if not rendered:
            return ""
        return "Worked examples of the expected analysis and output format:\n\n" + rendered

    def structured_call(self, schema: type[T], user_prompt: str) -> tuple[T, list[BaseMessage]]:
        """Invoke the model and validate its reply against ``schema``.

        On a parse/validation failure the error is fed back once so the model can repair
        its output. Both turns are returned so they can be appended to the graph trace.
        """
        messages: list[BaseMessage] = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]
        last_error: Exception | None = None
        for _attempt in range(self.max_repair_attempts + 1):
            reply = self.llm.invoke(messages)
            ai = reply if isinstance(reply, AIMessage) else AIMessage(content=str(reply))
            messages.append(ai)
            try:
                data = extract_json(_content_to_text(ai))
                return schema.model_validate(data), messages
            except (ValueError, ValidationError) as exc:
                last_error = exc
                messages.append(
                    HumanMessage(
                        content=(
                            "Your previous reply was not valid for the required schema. "
                            f"Error: {exc}. Reply again with only a JSON object matching "
                            f"this schema:\n{json.dumps(schema.model_json_schema())}"
                        )
                    )
                )
        raise AgentOutputError(f"{self.name}: {last_error}")
