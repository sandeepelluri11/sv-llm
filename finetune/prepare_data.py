"""Turn verification runs into a chat-format JSONL dataset for LoRA fine-tuning.

Input: one or more report JSON files produced by ``sv-llm run --json-out`` whose findings
have been reviewed (the validator verdicts are used as labels). Confirmed findings become
positive targets; rejected ones are dropped so the model learns reviewed outputs only.

Usage:
    python finetune/prepare_data.py reports/*.json --out finetune/data/train.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from sv_llm.agents.vuln_detect import SYSTEM_PROMPT as DETECT_PROMPT
from sv_llm.retrieval.loader import load_design

REPO_ROOT = Path(__file__).resolve().parent.parent


def build_examples(report_path: Path, designs_dir: Path) -> list[dict]:
    report = json.loads(report_path.read_text())
    design = load_design(designs_dir / report["design_name"])
    verdicts = {
        v["finding_id"]: v["status"] for v in (report.get("validation") or {}).get("verdicts", [])
    }
    confirmed = [f for f in report["findings"] if verdicts.get(f["id"]) == "confirmed"]
    if not confirmed:
        return []

    threat_summary = "\n".join(
        f"- {t['id']}: {t['title']} (asset: {t['asset']}, entry: {t['entry_point']})"
        for t in report["threats"]
    )
    user = (
        f"Design under verification: {design.name}\n\n"
        f"Threat model:\n{threat_summary}\n\n"
        f"RTL under analysis:\n{design.rtl_text}\n\n"
        "Report the vulnerabilities you can substantiate as JSON."
    )
    return [
        {
            "messages": [
                {"role": "system", "content": DETECT_PROMPT},
                {"role": "user", "content": user},
                {"role": "assistant", "content": json.dumps({"findings": confirmed})},
            ]
        }
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reports", nargs="+", type=Path)
    parser.add_argument("--designs", type=Path, default=REPO_ROOT / "designs")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "finetune/data/train.jsonl")
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    examples: list[dict] = []
    for report in args.reports:
        examples.extend(build_examples(report, args.designs))

    random.Random(args.seed).shuffle(examples)
    n_val = int(len(examples) * args.val_fraction)
    val, train = examples[:n_val], examples[n_val:]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(e) + "\n" for e in train))
    val_path = args.out.with_name(args.out.stem.replace("train", "val") + ".jsonl")
    val_path.write_text("".join(json.dumps(e) + "\n" for e in val))
    print(f"wrote {len(train)} train / {len(val)} val examples")


if __name__ == "__main__":
    main()
