import importlib.util
import sys
from pathlib import Path

from sv_llm.report import build_report, render_markdown

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "finetune" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_report_orders_findings_by_severity():
    state = {
        "design_name": "d",
        "iteration": 1,
        "threats": [],
        "findings": [
            {
                "id": "F1",
                "title": "low",
                "severity": "low",
                "module": "m",
                "location": "l",
                "description": "d",
                "recommendation": "r",
            },
            {
                "id": "F2",
                "title": "crit",
                "severity": "critical",
                "module": "m",
                "location": "l",
                "description": "d",
                "recommendation": "r",
            },
        ],
        "validation": None,
        "trace": ["x"],
    }
    report = build_report(state)
    assert [f.id for f in report.findings] == ["F2", "F1"]
    md = render_markdown(report)
    assert md.index("### F2") < md.index("### F1")
    assert "Status: **unvalidated**" in md


def test_eval_scoring_matches_on_module_and_cwe_or_title():
    ev = _load("eval_finetuned")
    refs = [[{"module": "m", "cwe": "CWE-1231", "title": "Lock bit can be cleared"}]]

    by_cwe = [[{"module": "m", "cwe": "CWE-1231", "title": "something else entirely"}]]
    assert ev.score(by_cwe, refs)["f1"] == 1.0

    by_title = [[{"module": "m", "cwe": None, "title": "Lock bit can be cleared by sw"}]]
    assert ev.score(by_title, refs)["recall"] == 1.0

    wrong_module = [[{"module": "other", "cwe": "CWE-1231", "title": "Lock bit can be cleared"}]]
    metrics = ev.score(wrong_module, refs)
    assert metrics == {"tp": 0, "fp": 1, "fn": 1, "precision": 0.0, "recall": 0.0, "f1": 0.0}


def test_prepare_data_builds_chat_examples(tmp_path: Path):
    prep = _load("prepare_data")
    report = {
        "design_name": "aes_key_wrapper",
        "threats": [
            {"id": "T1", "title": "t", "asset": "key", "entry_point": "dbg"},
        ],
        "findings": [
            {"id": "F1", "title": "keep", "module": "aes_key_wrapper"},
            {"id": "F2", "title": "drop", "module": "aes_key_wrapper"},
        ],
        "validation": {
            "verdicts": [
                {"finding_id": "F1", "status": "confirmed"},
                {"finding_id": "F2", "status": "rejected"},
            ]
        },
    }
    path = tmp_path / "r.json"
    import json

    path.write_text(json.dumps(report))
    examples = prep.build_examples(path, REPO_ROOT / "designs")
    assert len(examples) == 1
    assistant = json.loads(examples[0]["messages"][-1]["content"])
    assert [f["id"] for f in assistant["findings"]] == ["F1"]
    assert "module aes_key_wrapper" in examples[0]["messages"][1]["content"]
