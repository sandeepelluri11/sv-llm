from pathlib import Path

from sv_llm.graph import build_graph, build_store, run_verification
from sv_llm.report import build_report, render_markdown
from sv_llm.retrieval.loader import load_design
from sv_llm.state import initial_state
from tests.conftest import ScriptedChatModel, findings_reply, threats_reply, validation_reply


def _scripts(revise_first: bool) -> dict[str, list[str]]:
    validations = (
        [
            validation_reply(["F1"], needs_revision=True, notes="T2 has no finding"),
            validation_reply(["F1", "F2"], needs_revision=False),
        ]
        if revise_first
        else [validation_reply(["F1"], needs_revision=False)]
    )
    return {
        "threat-modeling agent": [threats_reply(2)],
        "vulnerability-detection agent": [findings_reply(["F1"]), findings_reply(["F1", "F2"])],
        "validation agent": validations,
    }


def test_graph_runs_single_pass(settings, embeddings, designs_dir: Path):
    design = load_design(designs_dir / "aes_key_wrapper")
    llm = ScriptedChatModel(scripts=_scripts(revise_first=False))

    state = run_verification(design, llm, embeddings, settings)

    assert state["iteration"] == 1
    assert [t["id"] for t in state["threats"]] == ["T1", "T2"]
    assert [f["id"] for f in state["findings"]] == ["F1"]
    assert state["validation"]["needs_revision"] is False
    agents = [c["agent"] for c in llm.calls]
    assert agents == ["threat-modeling agent", "vulnerability-detection agent", "validation agent"]
    assert state["trace"][-1] == "supervisor: route -> finish"
    # retrieval populated context for the threat agent
    assert state["context"] and state["context"][0].startswith("[spec")


def test_graph_revises_then_converges(settings, embeddings, designs_dir: Path):
    design = load_design(designs_dir / "boot_rom_ctrl")
    llm = ScriptedChatModel(scripts=_scripts(revise_first=True))

    state = run_verification(design, llm, embeddings, settings)

    assert state["iteration"] == 2
    assert [f["id"] for f in state["findings"]] == ["F1", "F2"]
    agents = [c["agent"] for c in llm.calls]
    assert agents.count("vulnerability-detection agent") == 2
    assert agents.count("validation agent") == 2
    # the second detection prompt carried the validator's notes
    assert llm.calls[3]["agent"] == "vulnerability-detection agent"


def test_graph_stops_at_iteration_budget(settings, embeddings, designs_dir: Path):
    design = load_design(designs_dir / "bus_arbiter")
    llm = ScriptedChatModel(
        scripts={
            "threat-modeling agent": [threats_reply(1)],
            "vulnerability-detection agent": [findings_reply(["F1"])],
            "validation agent": [validation_reply(["F1"], needs_revision=True, notes="again")],
        }
    )
    settings.max_iterations = 3

    state = run_verification(design, llm, embeddings, settings)

    assert state["iteration"] == 3
    assert state["validation"]["needs_revision"] is True
    assert state["trace"][-1] == "supervisor: route -> finish"


def test_graph_without_store_uses_full_documents(settings, designs_dir: Path):
    design = load_design(designs_dir / "aes_key_wrapper")
    llm = ScriptedChatModel(scripts=_scripts(revise_first=False))
    app = build_graph(llm, store=None, settings=settings)

    state = app.invoke(
        initial_state(design.name, design.spec_text, design.rtl_text),
        config={"configurable": {"thread_id": "t"}},
    )
    assert state["context"] == []
    assert state["findings"]


def test_report_renders_markdown(settings, embeddings, designs_dir: Path):
    design = load_design(designs_dir / "aes_key_wrapper")
    store = build_store(design, embeddings)
    assert store.size == len(design.documents)

    llm = ScriptedChatModel(scripts=_scripts(revise_first=True))
    state = run_verification(design, llm, embeddings, settings)
    report = build_report(state)
    md = render_markdown(report)

    assert md.startswith("# SV-LLM security verification report: `aes_key_wrapper`")
    assert "| T1 | Threat 1 |" in md
    assert "### F1 - Finding F1" in md
    assert "Status: **confirmed**" in md
    assert "```systemverilog" in md
    assert "supervisor: route -> finish" in md
