from pathlib import Path

from langchain_core.documents import Document

from sv_llm.retrieval.examples import load_examples, select_examples
from sv_llm.retrieval.store import SpecStore, format_context


def _docs() -> list[Document]:
    return [
        Document(page_content="debug lock key read-back", metadata={"kind": "spec", "source": "s"}),
        Document(
            page_content="module x; assign dbg = key_q;",
            metadata={"kind": "rtl", "source": "x.v", "module": "x"},
        ),
    ]


def test_store_filters_by_kind(embeddings):
    store = SpecStore(embeddings)
    store.add(_docs())
    assert store.size == 2
    rtl_only = store.search("key", k=5, kind="rtl")
    assert len(rtl_only) == 1
    assert rtl_only[0].metadata["module"] == "x"


def test_store_round_trips_through_disk(embeddings, tmp_path: Path):
    store = SpecStore(embeddings)
    store.add(_docs())
    path = tmp_path / "index.json"
    store.save(path)

    loaded = SpecStore.load(path, embeddings)
    assert loaded.size == 2
    assert len(loaded.search("debug", k=2)) == 2


def test_format_context_labels_provenance():
    rendered = format_context(_docs())
    assert rendered[0].startswith("[spec s section=top]")
    assert rendered[1].startswith("[rtl x.v module=x]")


def test_examples_load_and_rank(settings):
    examples = load_examples(settings.examples_dir)
    agents = {e.agent for e in examples}
    assert {"threat_model", "vuln_detect", "validate"} <= agents

    chosen = select_examples(examples, "vuln_detect", "the debug_lock bit is write-once", limit=1)
    assert [e.name for e in chosen] == ["non-sticky-lock-register"]

    chosen = select_examples(examples, "vuln_detect", "rdata = priv ? secret : 0", limit=1)
    assert [e.name for e in chosen] == ["privilege-check-missing-on-read"]


def test_examples_missing_dir_is_empty(tmp_path: Path):
    assert load_examples(tmp_path / "nope") == []
