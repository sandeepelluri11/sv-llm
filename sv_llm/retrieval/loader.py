"""Load a design directory into retrievable documents.

A design directory contains a ``spec.md`` (the security specification / threat model
inputs) and one or more ``*.v`` / ``*.sv`` RTL files. Spec files are split on Markdown
headings so each chunk carries its section title; RTL files are split per module and then
by line budget so each chunk carries ``module`` metadata the agents can cite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document

SPEC_SUFFIXES = {".md", ".txt"}
RTL_SUFFIXES = {".v", ".sv", ".svh"}

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
_MODULE = re.compile(r"^[ \t]*module\s+(\w+)", re.MULTILINE)


@dataclass(frozen=True)
class Design:
    name: str
    root: Path
    spec_text: str
    rtl_text: str
    documents: list[Document]


def _split_by_budget(text: str, budget: int) -> list[str]:
    """Split text into chunks of at most ``budget`` characters at line boundaries."""
    if len(text) <= budget:
        return [text] if text.strip() else []
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > budget and current:
            chunks.append("".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line)
    if current:
        chunks.append("".join(current))
    return [c for c in chunks if c.strip()]


def chunk_spec(text: str, source: str, budget: int = 1800) -> list[Document]:
    """Split a Markdown spec into heading-scoped chunks."""
    matches = list(_HEADING.finditer(text))
    if not matches:
        return [
            Document(page_content=c, metadata={"source": source, "kind": "spec", "section": ""})
            for c in _split_by_budget(text, budget)
        ]

    docs: list[Document] = []
    preamble = text[: matches[0].start()]
    for chunk in _split_by_budget(preamble, budget):
        docs.append(
            Document(page_content=chunk, metadata={"source": source, "kind": "spec", "section": ""})
        )
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section = match.group(2).strip()
        body = text[match.start() : end]
        for chunk in _split_by_budget(body, budget):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": source, "kind": "spec", "section": section},
                )
            )
    return docs


def chunk_rtl(text: str, source: str, budget: int = 1800) -> list[Document]:
    """Split RTL per module, then by line budget. Each chunk records its module name."""
    starts = [(m.start(), m.group(1)) for m in _MODULE.finditer(text)]
    if not starts:
        return [
            Document(page_content=c, metadata={"source": source, "kind": "rtl", "module": ""})
            for c in _split_by_budget(text, budget)
        ]

    docs: list[Document] = []
    for i, (start, module) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(text)
        body = text[start:end]
        for chunk in _split_by_budget(body, budget):
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": source, "kind": "rtl", "module": module},
                )
            )
    return docs


def load_design(root: Path, budget: int = 1800) -> Design:
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"design directory not found: {root}")

    spec_parts: list[str] = []
    rtl_parts: list[str] = []
    documents: list[Document] = []

    for path in sorted(root.iterdir()):
        if path.suffix in SPEC_SUFFIXES:
            text = path.read_text()
            spec_parts.append(text)
            documents.extend(chunk_spec(text, path.name, budget))
        elif path.suffix in RTL_SUFFIXES:
            text = path.read_text()
            rtl_parts.append(f"// ---- {path.name} ----\n{text}")
            documents.extend(chunk_rtl(text, path.name, budget))

    if not spec_parts and not rtl_parts:
        raise ValueError(f"no spec (.md/.txt) or RTL (.v/.sv) files found in {root}")

    return Design(
        name=root.name,
        root=root,
        spec_text="\n\n".join(spec_parts),
        rtl_text="\n\n".join(rtl_parts),
        documents=documents,
    )
