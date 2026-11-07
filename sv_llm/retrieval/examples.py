"""Few-shot examples used for in-context learning.

Each YAML file in ``examples/few_shot`` describes one historical hardware weakness as a
pair of (design excerpt, expected agent output). Agents pick the examples whose ``tags``
overlap with the current design and splice them into their prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class FewShotExample:
    name: str
    agent: str
    tags: list[str]
    input: str
    output: str
    source: str = ""
    extra: dict = field(default_factory=dict)


def load_examples(directory: Path) -> list[FewShotExample]:
    directory = Path(directory)
    if not directory.is_dir():
        return []
    examples: list[FewShotExample] = []
    for path in sorted(directory.glob("*.yaml")):
        data = yaml.safe_load(path.read_text()) or {}
        examples.append(
            FewShotExample(
                name=data.get("name", path.stem),
                agent=data["agent"],
                tags=[t.lower() for t in data.get("tags", [])],
                input=data["input"].strip(),
                output=data["output"].strip(),
                source=data.get("source", ""),
            )
        )
    return examples


def select_examples(
    examples: list[FewShotExample], agent: str, text: str, limit: int = 2
) -> list[FewShotExample]:
    """Rank examples for ``agent`` by how many of their tags appear in ``text``."""
    haystack = text.lower()
    scored = []
    for ex in examples:
        if ex.agent != agent:
            continue
        hits = sum(1 for tag in ex.tags if tag in haystack)
        scored.append((hits, ex))
    scored.sort(key=lambda pair: (-pair[0], pair[1].name))
    return [ex for hits, ex in scored[:limit] if hits > 0 or limit >= len(scored)]


def render_examples(examples: list[FewShotExample]) -> str:
    if not examples:
        return ""
    blocks = []
    for ex in examples:
        blocks.append(
            f"### Example: {ex.name}\nInput:\n{ex.input}\n\nExpected output:\n{ex.output}"
        )
    return "\n\n".join(blocks)
