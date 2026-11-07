"""Score a fine-tuned adapter (or any OpenAI-compatible endpoint) on held-out examples.

The metric is finding-level recall/precision: a predicted finding matches a reference one
when they name the same module and share the same CWE or a sufficiently similar title.

Usage (local adapter):
    python finetune/eval_finetuned.py --val finetune/data/val.jsonl \
        --base Qwen/Qwen2.5-Coder-1.5B-Instruct --adapter finetune/adapters/detect-lora

Usage (served through vLLM or any OpenAI-compatible server):
    python finetune/eval_finetuned.py --val finetune/data/val.jsonl \
        --endpoint http://localhost:8000/v1 --model detect-lora
"""

from __future__ import annotations

import argparse
import json
from difflib import SequenceMatcher
from pathlib import Path

from sv_llm.agents.base import extract_json


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def match(pred: dict, ref: dict) -> bool:
    if pred.get("module") != ref.get("module"):
        return False
    if pred.get("cwe") and pred.get("cwe") == ref.get("cwe"):
        return True
    return similar(pred.get("title", ""), ref.get("title", "")) >= 0.6


def score(predictions: list[list[dict]], references: list[list[dict]]) -> dict:
    tp = fp = fn = 0
    for preds, refs in zip(predictions, references, strict=True):
        used = set()
        for p in preds:
            hit = next((i for i, r in enumerate(refs) if i not in used and match(p, r)), None)
            if hit is None:
                fp += 1
            else:
                used.add(hit)
                tp += 1
        fn += len(refs) - len(used)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def generate_local(messages: list[dict], base: str, adapter: str | None, max_new: int) -> str:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(base)
    model = AutoModelForCausalLM.from_pretrained(base, torch_dtype=torch.float32)
    if adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, adapter)
    ids = tokenizer.apply_chat_template(messages, add_generation_prompt=True, return_tensors="pt")
    out = model.generate(ids, max_new_tokens=max_new, do_sample=False)
    return tokenizer.decode(out[0][ids.shape[-1] :], skip_special_tokens=True)


def generate_remote(messages: list[dict], endpoint: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI(base_url=endpoint, api_key="unused")
    reply = client.chat.completions.create(model=model, messages=messages, temperature=0)
    return reply.choices[0].message.content or ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--val", type=Path, required=True)
    parser.add_argument("--base")
    parser.add_argument("--adapter")
    parser.add_argument("--endpoint")
    parser.add_argument("--model")
    parser.add_argument("--max-new-tokens", type=int, default=1024)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.val.read_text().splitlines() if line.strip()]
    predictions, references = [], []
    for row in rows:
        prompt, target = row["messages"][:-1], row["messages"][-1]["content"]
        if args.endpoint:
            raw = generate_remote(prompt, args.endpoint, args.model)
        else:
            raw = generate_local(prompt, args.base, args.adapter, args.max_new_tokens)
        try:
            predictions.append(extract_json(raw).get("findings", []))
        except ValueError:
            predictions.append([])
        references.append(json.loads(target)["findings"])

    metrics = score(predictions, references)
    print(json.dumps(metrics, indent=2))
    if args.out:
        args.out.write_text(json.dumps({"metrics": metrics, "predictions": predictions}, indent=2))


if __name__ == "__main__":
    main()
