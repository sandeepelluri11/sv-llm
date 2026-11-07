"""Assemble the LangGraph: supervisor -> specialist agent -> supervisor ... -> END."""

from __future__ import annotations

from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from sv_llm.agents.supervisor import THREAT_MODEL, VALIDATE, VULN_DETECT, supervisor_node
from sv_llm.agents.threat_model import ThreatModelAgent
from sv_llm.agents.validate import ValidationAgent
from sv_llm.agents.vuln_detect import VulnerabilityAgent
from sv_llm.config import Settings, get_settings
from sv_llm.retrieval.examples import FewShotExample, load_examples
from sv_llm.retrieval.loader import Design
from sv_llm.retrieval.store import SpecStore
from sv_llm.state import VerificationState, initial_state

SUPERVISOR = "supervisor"


def build_store(design: Design, embeddings: Embeddings) -> SpecStore:
    store = SpecStore(embeddings)
    store.add(design.documents)
    return store


def build_graph(
    llm: BaseChatModel,
    store: SpecStore | None = None,
    examples: list[FewShotExample] | None = None,
    settings: Settings | None = None,
    checkpointer: Any | None = None,
):
    """Compile the verification graph.

    ``llm`` and ``store`` are injected so the same graph runs against OpenAI in production
    and against fake models in tests.
    """
    settings = settings or get_settings()
    examples = examples if examples is not None else load_examples(settings.examples_dir)
    k = settings.retriever_k

    graph: StateGraph = StateGraph(VerificationState)
    graph.add_node(SUPERVISOR, supervisor_node(settings.max_iterations))
    graph.add_node(THREAT_MODEL, ThreatModelAgent(llm, store, examples, retriever_k=k))
    graph.add_node(VULN_DETECT, VulnerabilityAgent(llm, store, examples, retriever_k=k))
    graph.add_node(VALIDATE, ValidationAgent(llm, store, examples, retriever_k=k))

    graph.add_edge(START, SUPERVISOR)
    graph.add_conditional_edges(
        SUPERVISOR,
        lambda state: state["next_agent"],
        {THREAT_MODEL: THREAT_MODEL, VULN_DETECT: VULN_DETECT, VALIDATE: VALIDATE, END: END},
    )
    for agent in (THREAT_MODEL, VULN_DETECT, VALIDATE):
        graph.add_edge(agent, SUPERVISOR)

    return graph.compile(checkpointer=checkpointer or MemorySaver())


def run_verification(
    design: Design,
    llm: BaseChatModel,
    embeddings: Embeddings | None = None,
    settings: Settings | None = None,
    thread_id: str = "default",
) -> VerificationState:
    settings = settings or get_settings()
    store = build_store(design, embeddings) if embeddings is not None else None
    app = build_graph(llm, store, settings=settings)
    state = initial_state(design.name, design.spec_text, design.rtl_text)
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}
    return app.invoke(state, config=config)
