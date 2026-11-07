from pathlib import Path

import pytest

from sv_llm.retrieval.loader import chunk_rtl, chunk_spec, load_design

SPEC = """Intro paragraph.

# Overview
The block does things.

## Security requirements
- SR1. Reads return zero.
- SR2. Lock is sticky.
"""

RTL = """module a (input clk);
endmodule

module b (input clk, output reg q);
  always @(posedge clk) q <= 1'b1;
endmodule
"""


def test_chunk_spec_tags_sections():
    docs = chunk_spec(SPEC, "spec.md")
    sections = [d.metadata["section"] for d in docs]
    assert sections == ["", "Overview", "Security requirements"]
    assert all(d.metadata["kind"] == "spec" for d in docs)
    assert "SR2" in docs[-1].page_content


def test_chunk_rtl_tags_modules():
    docs = chunk_rtl(RTL, "top.v")
    assert [d.metadata["module"] for d in docs] == ["a", "b"]
    assert docs[1].page_content.startswith("module b")


def test_chunk_rtl_respects_budget():
    long_module = "module big ();\n" + "  wire w;\n" * 200 + "endmodule\n"
    docs = chunk_rtl(long_module, "big.v", budget=500)
    assert len(docs) > 1
    assert all(len(d.page_content) <= 500 for d in docs)
    assert {d.metadata["module"] for d in docs} == {"big"}


def test_load_design_from_repo(designs_dir: Path):
    design = load_design(designs_dir / "aes_key_wrapper")
    assert design.name == "aes_key_wrapper"
    assert "module aes_key_wrapper" in design.rtl_text
    assert "SR2" in design.spec_text
    kinds = {d.metadata["kind"] for d in design.documents}
    assert kinds == {"spec", "rtl"}


@pytest.mark.parametrize("name", ["aes_key_wrapper", "boot_rom_ctrl", "bus_arbiter"])
def test_every_shipped_design_loads(designs_dir: Path, name: str):
    design = load_design(designs_dir / name)
    assert design.documents


def test_load_design_rejects_empty_dir(tmp_path: Path):
    with pytest.raises(ValueError):
        load_design(tmp_path)
